"""Host MR worker: allowlisted GitLab GETs + transient text, never executes MR code."""

import copy
import signal
import threading

from sqlalchemy import text

from efren_bot.collection.transport import TransportError
from efren_bot.config import Settings
from efren_bot.db import make_engine, session_factory
from efren_bot.review.gitlab import Gitlab, GitlabError, links, source
from efren_bot.review.model import MAX_CONTEXT, generate, input_text, validate
from efren_bot.review.publish import publish_comment
from efren_bot.review.service import ReviewService

RUNNER_LOCK = 771061105
CONTEXT_RESERVE = 16000


def read_context(job, client_factory):
    snapshot = copy.deepcopy(job["payload"]["snapshot"])
    related = {r["item_id"]: r for r in job["payload"]["related"]}
    budget = 65000
    seen = set()
    dependencies = {}
    snapshot["dependencies"] = []
    for read in job["payload"]["plan"]["reads"]:
        target = related[read["item_id"]]
        dependencies[read["item_id"]] = target
        snapshot["dependencies"] = list(dependencies.values())
        if budget <= 0:
            snapshot["limitations"].append("Presupuesto de contexto agotado: " + read["path"])
            continue
        sha = target["refs"]["head_sha" if read["side"] == "head" else "base_sha"]
        key = (target["project"], read["path"], sha, read["start"], read["end"])
        if key in seen:
            continue
        seen.add(key)
        client = client_factory(target["project"], target["iid"])
        try:
            body = client.file(read["path"], sha, start=read["start"], end=read["end"])
        except GitlabError:
            snapshot["limitations"].append("Archivo no disponible: " + read["path"])
            continue
        excerpt = body[: max(0, budget)]
        budget -= len(excerpt)
        if body != excerpt:
            snapshot["limitations"].append("Archivo truncado: " + read["path"])
        if excerpt:
            source(
                snapshot["sources"],
                "file",
                excerpt,
                path=read["path"],
                sha=sha,
                project=target["project"],
                reason=read["reason"],
                line_start=read["start"],
                line_end=read["end"],
            )
            candidate = snapshot["sources"][-1]
            bounded_text = candidate["text"]
            payload = {**job["payload"], "snapshot": snapshot}
            low, high = 0, len(bounded_text)
            while low < high:
                middle = (low + high + 1) // 2
                candidate["text"] = bounded_text[:middle]
                if len(input_text(payload)) <= MAX_CONTEXT - CONTEXT_RESERVE:
                    low = middle
                else:
                    high = middle - 1
            candidate["text"] = bounded_text[:low]
            if low < len(bounded_text):
                snapshot["limitations"].append("Presupuesto total de contexto: " + read["path"])
                budget = 0
            if not low:
                snapshot["sources"].pop()
    snapshot["limitations"] = sorted(set(snapshot["limitations"]))
    snapshot["dependencies"] = list(dependencies.values())
    return snapshot


def tick(service, generator=generate, client_factory=Gitlab, publisher=publish_comment):
    job = service.claim()
    if job is None:
        return False
    kind = job["kind"]
    try:
        service.require_current(job)
        original_factory = client_factory

        def checked_factory(project, iid):
            service.require_read(job, project, iid)
            client = original_factory(project, iid)
            client.before_read = lambda: service.require_read(job, project, iid)
            return client

        client_factory = checked_factory
        if kind == "publish":
            current = client_factory(job["project"], job["iid"]).metadata()
            if service.admit_publish(job, current):
                try:
                    remote_id = publisher(
                        job["project"], job["iid"], job["payload"]["approved"], str(job["id"])
                    )
                except Exception:
                    service.finish_publish(job)
                else:
                    service.finish_publish(job, remote_id)
        elif kind == "detect":
            context = job["payload"]
            text = "\n".join(m["text"] for m in context["messages"])
            manual = context.get("human_categories", [])
            if not links(text) or (manual and "code_review" not in manual):
                raw = {
                    "requested": False,
                    "reason": "Sin MR o clasificación humana conservada.",
                    "context_urls": [],
                }
            else:
                service.require_current(job)
                raw = generator(kind, context)
            result = validate(kind, context, raw)
            service.finish_detection(job, result)
        elif kind == "capture":
            result = client_factory(job["project"], job["iid"]).capture()
            service.finish_item(job, result, next_phase="plan")
        elif kind == "context":
            service.finish_item(job, read_context(job, client_factory), next_phase="analyze")
        else:
            service.require_current(job)
            result = validate(kind, job["payload"], generator(kind, job["payload"]))
            if kind == "chat":
                service.finish_chat(job, result)
            else:
                if kind == "analyze":
                    current = client_factory(job["project"], job["iid"]).metadata()
                    if current.get("diff_refs") != job["payload"]["snapshot"]["refs"]:
                        service.finish_item(job, error="mr_changed_during_review")
                        return True
                    for dependency in job["payload"]["snapshot"].get("dependencies", []):
                        if dependency["item_id"] == job["payload"]["item_id"]:
                            continue
                        current = client_factory(
                            dependency["project"], dependency["iid"]
                        ).metadata()
                        if current.get("diff_refs") != dependency["refs"]:
                            service.finish_item(job, error="related_mr_changed_during_review")
                            return True
                service.finish_item(job, result, next_phase="context" if kind == "plan" else None)
    except Exception as error:
        code = "review_stage_failed"
        if isinstance(error, GitlabError):
            code = str(error)
        if isinstance(error, ValueError):
            code = (
                str(error)
                if str(error)
                in {
                    "review_context_budget",
                    "review_output_budget",
                    "review_range_invalid",
                    "review_ref_outside_request",
                    "review_coverage_missing",
                    "review_evidence_invalid",
                    "review_unsubstantiated_check",
                    "review_line_not_changed",
                    "review_missing_changed_evidence",
                    "review_discussion_invalid",
                    "review_correction_not_verified",
                }
                else "review_output_invalid"
            )
        if kind == "publish":
            service.fail_publish_before_send(job)
        elif kind == "detect":
            service.finish_detection(job, error=code)
        elif kind == "chat":
            service.finish_chat(job, error=code)
        else:
            service.finish_item(job, error=code)
        if isinstance(error, TransportError) and str(error) == "mr_review_cleanup_unconfirmed":
            service.command("pause")
    return True


def main():
    engine = make_engine(Settings())
    service = ReviewService(session_factory(engine))
    stop = threading.Event()
    for name in (signal.SIGINT, signal.SIGTERM):
        signal.signal(name, lambda *_: stop.set())
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as lock:
        if not lock.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": RUNNER_LOCK}):
            raise SystemExit("MR review runner already active")
        service.recover()

        def pulse():
            while not stop.is_set():
                try:
                    service.heartbeat()
                except Exception:
                    pass
                stop.wait(10)

        thread = threading.Thread(target=pulse, daemon=True)
        thread.start()
        try:
            while not stop.is_set():
                try:
                    service.scan()
                    tick(service)
                except Exception:
                    print("mr_review_tick_failed", flush=True)
                stop.wait(2)
        finally:
            stop.set()
            thread.join(timeout=12)
            lock.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": RUNNER_LOCK})
    engine.dispose()


if __name__ == "__main__":
    main()
