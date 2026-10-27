from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from efren_bot.collection.models import CollectionCapture, CollectionMessage, CollectionRun
from efren_bot.support.contracts import CaseAction
from efren_bot.support.models import SupportCase, SupportIntake
from efren_bot.support.service import SupportService

pytestmark = pytest.mark.integration


def message(db, at, *, mid=None, root=None, historical=False, trigger="manual", stored=None):
    with db.begin() as s:
        run = CollectionRun(
            trigger=trigger,
            status="succeeded",
            created_at=at,
            window_start=at,
            window_end=at,
            coverage=[],
        )
        s.add(run)
        s.flush()
        cap = CollectionCapture(
            run_id=run.id, operation="history", arguments={}, response={}, observed_at=at
        )
        s.add(cap)
        s.flush()
        row = CollectionMessage(
            capture_id=cap.id,
            source_scope="synthetic",
            channel_id="C-SYNTH",
            channel_name="synthetic",
            message_id=mid or str(uuid4()),
            thread_id=root,
            actor_id=None,
            text="Synthetic support report: error for loan 42",
            occurred_at=at,
            observed_at=at,
            stored_at=stored or datetime.now(UTC),
            sha256=uuid4().hex * 2,
            is_historical=historical,
        )
        s.add(row)
        s.flush()
        return row.id


def test_activation_excludes_history_imports_and_old_replies(database):
    service = SupportService(database)
    before = datetime.now(UTC) - timedelta(days=1)
    message(database, before)
    service.command("activate")
    now = datetime.now(UTC)
    message(database, now, historical=True)
    message(database, now, trigger="import")
    message(database, before, stored=now)
    message(database, now, root="ancient-thread")
    assert service.scan() == 1
    assert service.scan() == 0
    with database() as s:
        assert len(s.scalars(select(SupportIntake)).all()) == 1


def test_variants_and_replays_do_not_reactivate_support(database):
    service = SupportService(database)
    service.command("activate")
    at = datetime.now(UTC)
    message(database, at, mid="same")
    assert service.scan() == 1
    message(database, at, mid="same")
    assert service.scan() == 0


def test_intake_analysis_and_chat_with_real_boundaries(database):
    service = SupportService(database)
    service.command("activate")
    identifier = message(database, datetime.now(UTC))
    service.scan()
    from efren_bot.support.runner import tick

    calls = []

    def generate(kind, payload):
        calls.append(kind)
        if kind == "classify":
            return {
                "action": "support",
                "title": "Synthetic case",
                "reason": "new report",
                "evidence_ids": [str(identifier)],
            }
        if kind == "analyze":
            return {
                "reported": ["Error reported in Slack"],
                "hypotheses": [],
                "missing": ["CloudWatch scope"],
                "evidence_ids": [str(identifier)],
                "slack_draft": "Preliminary: awaiting log access; cause unconfirmed.",
            }
        return {
            "text": "No logs read; only the report is available.",
            "evidence_ids": [str(identifier)],
        }

    assert tick(service, generate)
    assert tick(service, generate)
    case = service.list()["cases"][0]
    assert case["status"] == "blocked" and case["error_code"] == "source_scope_pending"
    service.act(
        CaseAction(id=case["id"], request_id=uuid4(), action="ask", text="What did you find?")
    )
    assert tick(service, generate)
    assert service.detail(case["id"])["entries"][-1]["kind"] == "answer"
    assert calls == ["classify", "analyze", "chat"]


def test_pause_during_generation_discards_stale_analysis(database):
    service = SupportService(database)
    service.command("activate")
    identifier = message(database, datetime.now(UTC))
    service.scan()
    from efren_bot.support.runner import tick

    tick(
        service,
        lambda *_: {
            "action": "support",
            "title": "Case",
            "reason": "reported",
            "evidence_ids": [str(identifier)],
        },
    )
    case = service.list()["cases"][0]

    def pause(*_):
        service.act(CaseAction(id=case["id"], request_id=uuid4(), action="pause"))
        return {
            "reported": [],
            "hypotheses": [],
            "missing": [],
            "evidence_ids": [],
            "slack_draft": "stale",
        }

    tick(service, pause)
    current = service.detail(case["id"])["case"]
    assert current["status"] == "paused" and current["report"] == {}


def test_invalid_evidence_fails_closed_and_preserves_originals(database):
    service = SupportService(database)
    service.command("activate")
    message(database, datetime.now(UTC))
    service.scan()
    from efren_bot.support.runner import tick

    tick(
        service,
        lambda *_: {
            "action": "support",
            "title": "Invented",
            "reason": "fabricated",
            "evidence_ids": [str(uuid4())],
        },
    )
    with database() as s:
        assert s.scalar(select(SupportIntake)).status == "failed"
        assert s.scalar(select(SupportCase)) is None


def test_global_pause_prevents_generation_and_preserves_activation_cut(database):
    service = SupportService(database)
    cut = service.command("activate")["activated_at"]
    message(database, datetime.now(UTC))
    service.scan()
    service.command("pause")
    from efren_bot.support.runner import tick

    assert not tick(service, lambda *_: pytest.fail("paused model called"))
    assert service.command("resume")["activated_at"] == cut


def test_human_annotation_prevents_automatic_reclassification(database):
    from efren_bot.collection.models import CollectionAnnotation

    service = SupportService(database)
    service.command("activate")
    message(database, datetime.now(UTC), mid="manual")
    with database.begin() as s:
        s.add(
            CollectionAnnotation(
                source_scope="synthetic",
                channel_id="C-SYNTH",
                message_id="manual",
                category="information",
                attention="not_required",
                updated_at=datetime.now(UTC),
            )
        )
    service.scan()
    from efren_bot.support.runner import tick

    tick(service, lambda *_: pytest.fail("human classification bypassed"))
    assert service.list()["cases"] == []
    assert service.list()["intakes"][0]["decision"]["action"] == "manual"


def test_new_support_updates_same_case_but_thanks_does_not(database):
    service = SupportService(database)
    service.command("activate")
    from efren_bot.support.runner import tick

    def support(kind, payload):
        return {
            "action": "support",
            "title": "Case",
            "reason": "new evidence",
            "evidence_ids": [payload["trigger_id"]],
        }

    message(database, datetime.now(UTC), mid="first", root="old-thread")
    service.scan()
    tick(service, support)
    case = service.list()["cases"][0]
    service.act(CaseAction(id=case["id"], request_id=uuid4(), action="dismiss"))
    message(database, datetime.now(UTC), mid="second", root="old-thread")
    service.scan()
    tick(service, support)
    assert len(service.list()["cases"]) == 1
    assert service.list()["cases"][0]["status"] == "dismissed"
    revision = service.list()["cases"][0]["revision"]
    message(database, datetime.now(UTC), mid="thanks", root="old-thread")
    service.scan()
    tick(
        service,
        lambda *_: {
            "action": "ignore",
            "title": "Thanks",
            "reason": "No new problem",
            "evidence_ids": [],
        },
    )
    assert service.list()["cases"][0]["revision"] == revision


def test_redirect_invalidates_inflight_result_and_question_is_idempotent(database):
    service = SupportService(database)
    service.command("activate")
    message(database, datetime.now(UTC))
    service.scan()
    from efren_bot.support.runner import tick

    tick(
        service,
        lambda _, p: {
            "action": "support",
            "title": "Case",
            "reason": "New report",
            "evidence_ids": [p["trigger_id"]],
        },
    )
    job = service.claim()
    case = service.list()["cases"][0]
    ask = CaseAction(id=case["id"], request_id=uuid4(), action="ask", text="Progress?")
    assert service.act(ask) == service.act(ask)
    assert service.detail(case["id"])["case"]["revision"] == 1
    service.act(
        CaseAction(id=case["id"], request_id=uuid4(), action="redirect", text="Use new timeframe")
    )
    service.finish(job, result={"slack_draft": "stale"})
    assert service.detail(case["id"])["case"]["report"] == {}
    assert service.claim()["kind"] == "chat"


def test_recovery_records_interruption_without_false_success(database):
    service = SupportService(database)
    service.command("activate")
    message(database, datetime.now(UTC))
    service.scan()
    service.claim()
    service.recover()
    assert service.list()["intakes"][0]["error_code"] == "runner_interrupted"


def test_unconfirmed_session_cleanup_pauses_further_model_calls(database):
    from efren_bot.collection.transport import TransportError
    from efren_bot.support.runner import tick

    service = SupportService(database)
    service.command("activate")
    message(database, datetime.now(UTC))
    service.scan()

    def broken(*_):
        raise TransportError("support_cleanup_unconfirmed")

    tick(service, broken)
    state = service.list()
    assert state["control"]["paused"]
    assert state["intakes"][0]["error_code"] == "support_cleanup_unconfirmed"


def test_support_http_is_closed_and_requires_local_capability(database, pg_engine):
    from fastapi.testclient import TestClient

    from efren_bot.api import create_app

    headers = {"Host": "127.0.0.1:8000", "Origin": "http://127.0.0.1:5173", "X-Efren-Local": "1"}
    with TestClient(create_app(engine=pg_engine)) as client:
        token = client.get("/api/collection/session", headers=headers).json()["token"]
        assert (
            client.post("/api/collection/support/list", headers=headers, json={}).status_code == 401
        )
        headers = {**headers, "X-Collection-Token": token}
        assert (
            client.post("/api/collection/support/list", headers=headers, json={}).json()["cases"]
            == []
        )
        invalid = client.post(
            "/api/collection/support/act", headers=headers, json={"secret": "private-body"}
        )
        assert invalid.status_code == 422 and "private-body" not in invalid.text
        assert (
            client.post("/api/collection/support/activate", headers=headers, json={}).status_code
            == 200
        )
        assert client.post(
            "/api/collection/support/act",
            headers=headers,
            content='{"id":"duplicate","id":"duplicate"}',
        ).status_code in {415, 422}
