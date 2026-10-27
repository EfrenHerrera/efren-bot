"""Host-only, bounded text processing. No AWS/GitLab/repository capabilities yet."""

import signal
import threading

from sqlalchemy import text

from efren_bot.collection.transport import TransportError
from efren_bot.config import Settings
from efren_bot.db import make_engine, session_factory
from efren_bot.support.model import generate, validate
from efren_bot.support.service import SupportService

RUNNER_LOCK = 771061104


def tick(service, generator=generate):
    job = service.claim()
    if job is None:
        return False
    try:
        service.require_current(job)
        manual = job["payload"].get("human_categories", [])
        if job["kind"] == "classify" and manual and manual != ["support"]:
            raw = {
                "action": "ignore",
                "title": "Clasificación humana",
                "reason": "Se conserva la clasificación humana.",
                "evidence_ids": [],
            }
        else:
            raw = generator(job["kind"], job["payload"])
        result = validate(job["kind"], job["payload"], raw)
    except TransportError as error:
        code = (
            "support_cleanup_unconfirmed"
            if str(error) == "support_cleanup_unconfirmed"
            else "model_or_evidence_failed"
        )
        service.finish(job, error=code)
        if code == "support_cleanup_unconfirmed":
            service.command("pause")
    except Exception:
        service.finish(job, error="model_or_evidence_failed")
    else:
        service.finish(job, result=result)
    return True


def main():
    engine = make_engine(Settings())
    service = SupportService(session_factory(engine))
    stop = threading.Event()
    for name in (signal.SIGINT, signal.SIGTERM):
        signal.signal(name, lambda *_: stop.set())
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as lock:
        if not lock.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": RUNNER_LOCK}):
            raise SystemExit("Support runner already active")
        service.recover()

        def pulse():
            while not stop.is_set():
                try:
                    service.heartbeat()
                except Exception:
                    pass
                stop.wait(10)

        heartbeat = threading.Thread(target=pulse, daemon=True)
        heartbeat.start()
        try:
            while not stop.is_set():
                try:
                    service.scan()
                    tick(service)
                except Exception:
                    print("support_tick_failed", flush=True)
                stop.wait(2)
        finally:
            stop.set()
            heartbeat.join(timeout=12)
            lock.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": RUNNER_LOCK})
    engine.dispose()


if __name__ == "__main__":
    main()
