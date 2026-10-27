import json
import multiprocessing
import os
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

import efren_bot.worker as worker_module
from efren_bot.api import create_app
from efren_bot.classification import ASK_CONTEXT, REVIEW_REPLY
from efren_bot.config import Settings
from efren_bot.db import make_engine, session_factory
from efren_bot.fixtures import demo_fixtures
from efren_bot.ingestion import ingest
from efren_bot.models import Activity, Message, Outbox, Task, Thread, utcnow
from efren_bot.schemas import DemoEventInput
from efren_bot.worker import Worker, process_once

pytestmark = pytest.mark.integration


def due(database):
    with database.begin() as session:
        session.execute(
            update(Outbox)
            .where(Outbox.status == "pending")
            .values(available_at=utcnow() - timedelta(seconds=1))
        )


def counts(database):
    with database() as session:
        return tuple(
            session.scalar(select(func.count()).select_from(model))
            for model in (Message, Activity, Task)
        )


def test_canonical_flow_api_and_alias(database, pg_engine):
    fixtures = demo_fixtures()
    with TestClient(create_app(engine=pg_engine)) as client:
        assert client.get("/api/demo/fixtures").json() == [
            fixture.model_dump(mode="json") for fixture in fixtures
        ]
        source = ingest(database, fixtures[0].event)
        assert process_once(database).status == "processed"
        initial = client.get("/api/overview").json()
        assert initial["classifier"] == "deterministic_demo"
        task = initial["tasks"][0]
        assert task["state"] == "needs_context"
        assert task["next_action"] == ASK_CONTEXT
        assert task["source_event_id"] == str(source.id)
        assert task["has_new_reply"] is False
        for fixture in fixtures[1:]:
            ingest(database, fixture.event)
            assert process_once(database).status == "processed"
        for fixture in fixtures:
            assert ingest(database, fixture.event).status == "duplicate"
        alias_data = fixtures[0].event.model_dump() | {"event_id": "alias-after-projection"}
        alias = ingest(database, DemoEventInput.model_validate(alias_data))
        assert alias.status == "duplicate"
        assert process_once(database).status == "idle"
        final = client.get("/api/overview").json()
        assert final["counts"] == dict(
            tasks=1, needs_context=1, ready=0, updates=1, pending_events=0, failed_events=0
        )
        assert len(final["activities"]) == 3
        assert [a["intent"] for a in final["activities"]] == [
            "thread_reply",
            "acknowledgement",
            "task_request",
        ]
        updated = final["tasks"][0]
        assert updated["id"] == task["id"]
        assert updated["state"] == "needs_context"
        assert updated["source_event_id"] == str(source.id)
        assert updated["has_new_reply"] is True
        assert updated["next_action"] == REVIEW_REPLY
        assert updated["updated_at"] >= task["updated_at"]
        detail = client.get(f"/api/tasks/{task['id']}").json()
        assert set(detail) == {"task", "messages"}
        assert [m["text"] for m in detail["messages"]] == [
            fixtures[0].event.text,
            fixtures[2].event.text,
        ]
        assert detail["messages"][0]["event_id"] == str(source.id)
        assert client.get(f"/api/tasks/{task['id']}").json()["task"]["has_new_reply"] is True
    assert counts(database) == (3, 3, 1)


def test_reply_before_root_and_thread_scope(database):
    request, thanks, reply = [f.event for f in demo_fixtures()]
    ingest(database, reply)
    deferred = process_once(database)
    assert deferred.status == "deferred" and deferred.attempts == 0
    assert counts(database) == (1, 0, 0)
    due(database)
    # A poll after the backoff has elapsed must not keep selecting this reply
    # ahead of a later root forever (the production loop sleeps between polls).
    assert process_once(database).status == "idle"
    # Identical external thread ID in a different channel cannot become this task's reply.
    other_channel = DemoEventInput.model_validate(request.model_dump() | {"channel_id": "another"})
    ingest(database, other_channel)
    assert process_once(database).status == "processed"
    assert counts(database) == (2, 1, 0)
    ingest(database, request)
    due(database)
    assert process_once(database).status == "processed"
    with database() as session:
        task = session.scalar(select(Task))
        assert task.has_new_reply is True  # root preserves evidence already accepted
        assert task.next_action == REVIEW_REPLY
    due(database)
    assert process_once(database).status == "processed"
    assert counts(database) == (3, 3, 1)
    assert process_once(database).status == "idle"


def test_unknown_messages_are_evidence_not_semantic_merge(database, monkeypatch):
    def forbidden_fetch(*args, **kwargs):
        raise AssertionError("source_url must never be visited")

    monkeypatch.setattr(urllib.request, "urlopen", forbidden_fetch)
    request = demo_fixtures()[0].event
    ingest(database, request)
    process_once(database)
    another = DemoEventInput.model_validate(
        request.model_dump()
        | {
            "event_id": "another-event",
            "message_id": "another-request",
            "text": "@efren sube otro video",
            "source_url": "https://example.test/not-fetched",
        }
    )
    ingest(database, another)
    process_once(database)
    assert counts(database) == (2, 2, 1)
    with database() as session:
        assert session.scalar(select(Activity).where(Activity.intent == "ignored")) is not None
        task = session.scalar(select(Task))
        assert task.has_new_reply is False
        assert task.next_action == ASK_CONTEXT


def test_concurrent_workers_serialize_thread_and_skip_claims(database):
    for fixture in demo_fixtures():
        ingest(database, fixture.event)
    for _ in range(4):
        due(database)
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda _: process_once(database), range(6)))
    assert counts(database) == (3, 3, 1)
    with database() as session:
        assert session.scalar(select(Task)).has_new_reply is True
        assert session.scalar(select(func.count()).where(Outbox.status == "processed")) == 3


def test_locked_thread_defers_without_attempt(database):
    ingest(database, demo_fixtures()[0].event)
    with database.begin() as lock_session:
        lock_session.scalar(select(Thread).with_for_update())
        result = process_once(database)
        assert result.status == "deferred" and result.attempts == 0
        assert counts(database) == (1, 0, 0)
    due(database)
    assert process_once(database).status == "processed"


def test_projection_failure_savepoint_backoff_exhaustion(database, pg_engine, monkeypatch):
    ingest(database, demo_fixtures()[0].event)
    original = worker_module.project

    def failing_projection(session, event, message):
        original(session, event, message)
        raise RuntimeError("sensitive synthetic error text must not be stored")

    monkeypatch.setattr(worker_module, "project", failing_projection)
    for attempt in range(1, 6):
        before = utcnow()
        result = process_once(database)
        assert result.attempts == attempt
        assert result.status == ("failed" if attempt == 5 else "retry")
        assert counts(database) == (1, 0, 0)  # savepoint rolled back BOTH projections
        with database() as session:
            item = session.scalar(select(Outbox))
            assert item.last_error == "RuntimeError"
            assert item.available_at >= before + timedelta(seconds=2 ** (attempt - 1))
        assert process_once(database).status == "idle"  # backoff respected, not a busy retry
        if attempt < 5:
            due(database)  # advance test eligibility, never sleep in a projection
    with TestClient(create_app(engine=pg_engine)) as client:
        overview = client.get("/api/overview").json()
        assert overview["counts"]["failed_events"] == 1
        assert overview["counts"]["pending_events"] == 0


@pytest.mark.parametrize("error", ["python", "database"])
def test_retry_after_projection_failure_has_no_duplicate_effects(database, monkeypatch, error):
    ingest(database, demo_fixtures()[0].event)
    original = worker_module.project

    def fail_after_flush(session, event, message):
        original(session, event, message)
        if error == "database":
            session.add(
                Activity(
                    message_id=message.id,
                    event_id=message.canonical_event_id,
                    thread_pk=message.thread_pk,
                    intent="ignored",
                    summary="Deliberate duplicate to exercise PostgreSQL aborted savepoint",
                    occurred_at=message.occurred_at,
                )
            )
            session.flush()
        raise RuntimeError("test")

    monkeypatch.setattr(worker_module, "project", fail_after_flush)
    assert process_once(database).status == "retry"
    assert counts(database) == (1, 0, 0)
    with database() as session:
        assert session.scalar(select(Outbox)).last_error == (
            "IntegrityError" if error == "database" else "RuntimeError"
        )
    monkeypatch.setattr(worker_module, "project", original)
    due(database)
    assert process_once(database).status == "processed"
    assert counts(database) == (1, 1, 1)
    assert process_once(database).status == "idle"


def crash_child(url, connection):
    """Own child process: hold an uncommitted projection until the test kills it."""
    engine = make_engine(Settings(database_url=url))
    original = worker_module.project

    def project_and_wait(session, event, message):
        original(session, event, message)
        connection.send("projection-flushed-without-commit")
        connection.recv()  # test-only pause; production projection never waits

    worker_module.project = project_and_wait
    try:
        process_once(session_factory(engine))
    finally:
        engine.dispose()
        connection.close()


def test_real_process_kill_rolls_back_and_releases_claim(database, pg_engine):
    ingest(database, demo_fixtures()[0].event)
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(
        target=crash_child,
        args=(pg_engine.url.render_as_string(hide_password=False), child),
    )
    process.start()
    child.close()
    try:
        assert parent.poll(10), "child did not reach uncommitted projection"
        assert parent.recv() == "projection-flushed-without-commit"
        assert counts(database) == (1, 0, 0)  # uncommitted effects invisible
        assert process_once(database).status == "idle"  # SKIP LOCKED on claimed outbox
        process.kill()  # actual SIGKILL, ONLY the process created above
        process.join(5)
        assert not process.is_alive() and process.exitcode < 0
        deadline = time.monotonic() + 5
        while True:
            result = process_once(database)
            if result.status != "idle" or time.monotonic() >= deadline:
                break
            time.sleep(0.05)
        assert result.status == "processed" and result.attempts == 0
        assert counts(database) == (1, 1, 1)
        assert process_once(database).status == "idle"
    finally:
        if process.is_alive():
            process.kill()
            process.join(5)
        parent.close()


def test_cli_ingestion_does_not_process_and_worker_once_is_real(database, pg_engine):
    env = os.environ | {
        "APP_ENV": "local",
        "DATABASE_URL": pg_engine.url.render_as_string(hide_password=False),
    }
    demo = subprocess.run(
        [sys.executable, "-m", "efren_bot.demo"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    receipts = [json.loads(line) for line in demo.stdout.splitlines()[:-1]]
    assert len(receipts) == 3
    assert all(receipt["status"] == "accepted" for receipt in receipts)
    assert counts(database) == (3, 0, 0)  # CLI never runs the worker implicitly
    for _ in range(3):
        run = subprocess.run(
            [sys.executable, "-m", "efren_bot.worker", "--once"],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        assert json.loads(run.stdout)["status"] == "processed"
    assert counts(database) == (3, 3, 1)
    repeated = subprocess.run(
        [sys.executable, "-m", "efren_bot.demo"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    assert all(
        json.loads(line)["status"] == "duplicate" for line in repeated.stdout.splitlines()[:-1]
    )
    assert counts(database) == (3, 3, 1)


def test_loop_sleeps_after_returning_connection(database, pg_engine, monkeypatch):
    ingest(database, demo_fixtures()[0].event)
    worker = Worker(engine=pg_engine)

    def stop_after_poll(interval):
        assert interval == worker.settings.worker_poll_interval_seconds
        assert pg_engine.pool.checkedout() == 0
        assert counts(database) == (1, 1, 1)
        raise KeyboardInterrupt()

    monkeypatch.setattr(worker_module.time, "sleep", stop_after_poll)
    try:
        with pytest.raises(KeyboardInterrupt):
            worker.run()
    finally:
        worker.close()
