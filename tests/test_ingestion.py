from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, text

from efren_bot.api import create_app
from efren_bot.config import Settings
from efren_bot.db import make_engine
from efren_bot.ingestion import IdentityConflict, ingest
from efren_bot.models import Base, Event, Message, Outbox, Thread
from efren_bot.schemas import DemoEventInput

pytestmark = pytest.mark.integration


def changed(data, **changes):
    return DemoEventInput.model_validate(data.model_dump() | changes)


def row_counts(database):
    with database() as session:
        return tuple(
            session.scalar(select(func.count()).select_from(m))
            for m in (Event, Message, Outbox, Thread)
        )


def test_migration_and_vector(pg_engine):
    with pg_engine.connect() as connection:
        assert connection.scalar(text("SELECT '[1,2,3]'::vector <-> '[1,2,4]'::vector")) == 1
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []


def test_http_receipts_aliases_conflicts(database, pg_engine, event_input):
    with TestClient(create_app(engine=pg_engine)) as client:
        payload = event_input.model_dump(mode="json")
        accepted = client.post("/api/demo/events", json=payload)
        assert accepted.status_code == 202
        canonical = accepted.json()["id"]
        assert UUID(canonical)
        retry = client.post("/api/demo/events", json=payload)
        assert retry.status_code == 200
        assert retry.json() == {"id": canonical, "status": "duplicate"}
        alias = client.post("/api/demo/events", json=payload | {"event_id": "alias"})
        assert alias.status_code == 200
        assert alias.json()["id"] != canonical
        assert row_counts(database) == (2, 1, 1, 1)
        for patch in (
            {"text": "different"},
            {"event_id": "alias", "actor_id": "other"},
            {"event_id": "new", "thread_id": "another"},
        ):
            assert client.post("/api/demo/events", json=payload | patch).status_code == 409
        assert row_counts(database) == (2, 1, 1, 1)
        detail = client.get(f"/api/events/{canonical}").json()
        assert detail["provider"] == "fixture" and detail["owner_id"] == "efren"
        assert detail["payload"] == payload
        assert client.get(f"/api/events/{uuid4()}").status_code == 404
        assert client.get("/api/events/not-uuid").status_code == 422
        assert client.get(f"/api/tasks/{uuid4()}").status_code == 404
        overview = client.get("/api/overview").json()
        assert overview["counts"] == dict(
            tasks=0, needs_context=0, ready=0, updates=0, pending_events=1, failed_events=0
        )
        assert overview["tasks"] == overview["activities"] == overview["integrations"] == []
        assert client.get("/readyz").json() == {"status": "ok", "database": "ok"}


def test_concurrent_dedupe_and_aliases(database, event_input):
    inputs = [event_input] * 6 + [changed(event_input, event_id=f"alias-{i}") for i in range(6)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda item: ingest(database, item), inputs))
    assert sum(r.status == "accepted" for r in results) == 1
    assert row_counts(database) == (7, 1, 1, 1)


@pytest.mark.parametrize("case", ["event", "message", "event_other_thread"])
def test_concurrent_conflicting_event_and_message(database, event_input, case):
    def accept(item):
        try:
            return ingest(database, item).status
        except IdentityConflict:
            return "conflict"

    contender = {
        "event": changed(event_input, text="different"),
        "message": changed(event_input, event_id="other", text="different"),
        "event_other_thread": changed(event_input, message_id="another", thread_id="another"),
    }[case]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(accept, [event_input, contender]))
    assert sorted(results) == ["accepted", "conflict"]
    assert row_counts(database) == (1, 1, 1, 1)


def test_ingest_rollback_outbox_failure(database, pg_engine, event_input):
    def fail(connection, cursor, statement, parameters, context, many):
        if statement.startswith("INSERT INTO outbox"):
            raise RuntimeError("synthetic outbox failure")

    event.listen(pg_engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="synthetic"):
            ingest(database, event_input)
    finally:
        event.remove(pg_engine, "before_cursor_execute", fail)
    assert row_counts(database) == (0, 0, 0, 0)
    assert ingest(database, event_input).status == "accepted"


def test_composite_scope_and_exact_content(database, event_input):
    ingest(database, event_input)
    assert ingest(database, changed(event_input, channel_id="Other")).status == "accepted"
    assert ingest(database, changed(event_input, workspace_id="Other")).status == "accepted"
    for field, value in [
        ("actor_id", "other"),
        ("text", "@efren sube el video "),
        ("occurred_at", "2026-01-15T15:00:01Z"),
        ("source_url", "https://example.test/video"),
        ("thread_id", "different"),
    ]:
        with pytest.raises(IdentityConflict):
            ingest(database, changed(event_input, event_id=f"new-{field}", **{field: value}))
    assert row_counts(database) == (3, 3, 3, 3)


def test_unavailable_db_is_not_healthy():
    engine = make_engine(
        Settings(database_url="postgresql+psycopg://demo:demo@127.0.0.1:1/efren_bot_test")
    )
    try:
        with TestClient(create_app(engine=engine)) as client:
            assert client.get("/healthz").json() == {"status": "ok"}
            for path in ("/readyz", "/api/overview"):
                response = client.get(path)
                assert response.status_code == 503
                assert response.json() == {"detail": "database unavailable"}
    finally:
        engine.dispose()
