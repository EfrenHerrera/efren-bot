import json
import multiprocessing
import os
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import SQLAlchemyError

from efren_bot import work_worker
from efren_bot.api import create_app
from efren_bot.config import Settings
from efren_bot.db import make_engine, session_factory
from efren_bot.fixtures import demo_fixtures
from efren_bot.ingestion import ingest
from efren_bot.models import (
    Activity,
    Base,
    Task,
    WorkApproval,
    WorkArtifact,
    WorkHistory,
    WorkItem,
    WorkJob,
    utcnow,
)
from efren_bot.work import service
from efren_bot.work.contracts import CreateWork, Decision, WorkDetail
from efren_bot.work_worker import process_once
from efren_bot.worker import process_once as project_fixture

pytestmark = pytest.mark.integration
TABLES = (WorkItem, WorkJob, WorkHistory, WorkArtifact, WorkApproval)


def request(key=None, fixture="request_video"):
    return CreateWork(idempotency_key=key or uuid4(), fixture_id=fixture)


def counts(sessions):
    with sessions() as session:
        return tuple(session.scalar(select(func.count()).select_from(table)) for table in TABLES)


def read(sessions, work_id):
    with sessions.begin() as session:
        return service.detail(session, work_id)


def due(sessions):
    with sessions.begin() as session:
        for job in session.scalars(select(WorkJob).where(WorkJob.status == "queued")):
            job.available_at = utcnow() - timedelta(seconds=1)


def prepare(sessions):
    first = service.create(sessions, request()).detail
    assert process_once(sessions).status == "waiting_human"
    return read(sessions, first.work.id)


def decision(data, action="approve", reason="Revisión sintética explícita"):
    return Decision(decision=action, artifact_sha256=data.artifacts[0].sha256, reason=reason)


def decide(sessions, data, value=None):
    return service.decide(sessions, data.work.id, data.approvals[0].id, value or decision(data))


def test_schema_and_head(pg_engine):
    with pg_engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "0010_human_control"
        )
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []


def test_create_exact_source_and_idempotency(database):
    data = request()
    first = service.create(database, data)
    assert first.status == "accepted"
    assert (
        first.detail.work.source_snapshot.canonical_payload()
        == demo_fixtures()[0].event.canonical_payload()
    )
    assert first.detail.work.source_snapshot.event_id == "evt-request-video-001"
    assert first.detail.work.source_sha256 == service.digest(service.source())
    assert first.detail.work.created_at > first.detail.work.source_snapshot.occurred_at
    assert isinstance(first.detail.work.id, UUID)
    assert first.detail.work.created_at.utcoffset() == timedelta(0)
    repeated = service.create(database, data)
    assert repeated.status == "duplicate" and repeated.detail == first.detail
    assert counts(database) == (1, 1, 1, 0, 0)
    for fixture in ("thanks", "reply"):
        with pytest.raises(service.WorkError, match="idempotency_conflict"):
            service.create(database, request(data.idempotency_key, fixture))
        with pytest.raises(service.WorkError, match="unsupported_recipe"):
            service.create(database, request(fixture=fixture))
    assert counts(database) == (1, 1, 1, 0, 0)


def test_create_concurrency(database):
    data = request()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: service.create(database, data), range(4)))
    assert sorted(r.status for r in results) == ["accepted", "duplicate", "duplicate", "duplicate"]
    assert len({r.detail.work.id for r in results}) == 1
    assert counts(database) == (1, 1, 1, 0, 0)


@pytest.mark.parametrize("transition", ["prepare", "finalize"])
def test_create_replay_refreshes_stale_work_after_worker_commit(database, monkeypatch, transition):
    data = request()
    created = service.create(database, data).detail
    if transition == "finalize":
        assert process_once(database).status == "waiting_human"
        decide(database, read(database, created.work.id))
    before = read(database, created.work.id)
    original = service.replay

    def commit_between_lookup_and_replay(session, work, incoming):
        # create() already loaded this object. Another transaction now changes it,
        # leaving the replay session's identity map stale at READ COMMITTED.
        assert session.get(WorkItem, work.id) is work
        assert work.state == "active" and work.updated_at == before.work.updated_at
        result = process_once(database)
        assert result.status == ("waiting_human" if transition == "prepare" else "succeeded")
        return original(session, work, incoming)

    monkeypatch.setattr(service, "replay", commit_between_lookup_and_replay)
    replayed = service.create(database, data)
    after = read(database, created.work.id)
    assert replayed.status == "duplicate"
    assert replayed.detail == after  # all work/job/checkpoint/history/artifacts/approvals agree
    assert after.work.state == ("waiting" if transition == "prepare" else "delivered")
    assert after.job.checkpoint.phase == (
        "await_approval" if transition == "prepare" else "complete"
    )
    assert after.history[-1].kind == (
        "proposal_prepared" if transition == "prepare" else "simulation_finished"
    )


def test_create_replay_holds_job_lock_through_detail_reads(database, monkeypatch):
    data = request()
    created = service.create(database, data).detail
    original = service.detail

    def competing_worker_during_detail(session, work_id):
        assert process_once(database).status == "idle"  # SKIP LOCKED, not a timing assumption
        return original(session, work_id)

    monkeypatch.setattr(service, "detail", competing_worker_during_detail)
    replayed = service.create(database, data)
    assert replayed.detail == created
    assert process_once(database).status == "waiting_human"  # lock released on replay commit


def test_create_failure_atomic(database, monkeypatch):
    original = service.history

    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("synthetic insert failure")

    monkeypatch.setattr(service, "history", fail)
    with pytest.raises(RuntimeError):
        service.create(database, request())
    assert counts(database) == (0, 0, 0, 0, 0)


def test_proposal_waits_without_reclaim_or_connection(database, pg_engine):
    data = prepare(database)
    assert data.job.checkpoint.phase == "await_approval"
    assert data.job.checkpoint.next_action == "human_decision"
    assert data.job.attempt_count == 1 and data.job.failure_count == 0
    assert data.work.state == "waiting" and data.job.status == "waiting_human"
    assert data.artifacts[0].content.action == "ASK_CONTEXT"
    assert data.artifacts[0].content.missing_context == ["Qué video", "Destino de publicación"]
    assert data.artifacts[0].attempt_id == data.history[1].attempt_id
    assert data.approvals[0].artifact_sha256 == data.artifacts[0].sha256
    assert pg_engine.pool.checkedout() == 0
    assert process_once(database).status == "idle"
    assert read(database, data.work.id) == data


def test_decision_replay_conflicts_and_foreign_resource(database):
    data = prepare(database)
    foreign = prepare(database)  # both wait before either finalization enters the queue
    value = decision(data)
    recorded = decide(database, data, value)
    assert recorded.status == "recorded"
    assert recorded.detail.job.status == "queued"
    assert recorded.detail.job.checkpoint.phase == "finalize"
    assert decide(database, data, value).detail == recorded.detail
    for change in (
        {"decision": "reject"},
        {"reason": value.reason + " "},
        {"artifact_sha256": "b" * 64},
    ):
        with pytest.raises(service.WorkError) as error:
            decide(database, data, value.model_copy(update=change))
        assert error.value.status == 409
    with pytest.raises(service.WorkError) as error:
        service.decide(database, foreign.work.id, data.approvals[0].id, value)
    assert error.value.status == 404
    assert len(read(database, data.work.id).history) == 3


def test_concurrent_identical_decisions_serialize(database):
    data = prepare(database)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: decide(database, data), range(2)))
    assert sorted(r.status for r in results) == ["duplicate", "recorded"]
    assert len(read(database, data.work.id).history) == 3


def test_reject_never_finalizes(database):
    data = prepare(database)
    recorded = decide(database, data, decision(data, "reject", "No ejecutar simulación"))
    assert recorded.detail.job.status == "failed"
    assert recorded.detail.job.last_error_code == "approval_rejected"
    assert recorded.detail.job.checkpoint.phase == "rejected"
    assert recorded.detail.work.state == "waiting"
    assert process_once(database).status == "idle"
    assert counts(database) == (1, 1, 3, 1, 1)


def test_finalize_is_local_and_preserves_proposal(database):
    data = prepare(database)
    decide(database, data)
    assert process_once(database).status == "succeeded"
    final = read(database, data.work.id)
    assert final.work.state == "delivered" and final.job.status == "succeeded"
    assert final.job.attempt_count == 2 and final.job.failure_count == 0
    assert final.job.checkpoint.phase == "complete"
    assert final.job.checkpoint.final_artifact_id == final.artifacts[1].id
    assert final.artifacts[0] == data.artifacts[0]
    assert final.artifacts[1].content.action == "SIMULATION_COMPLETE"
    assert final.artifacts[1].content.no_external_effects
    assert all(c.status == "not_run" for c in final.artifacts[1].content.checks[1:])
    assert final.artifacts[1].content.missing_context == data.artifacts[0].content.missing_context
    assert [h.sequence for h in final.history] == [1, 2, 3, 4]
    assert process_once(database).status == "idle"
    assert decide(database, data).status == "duplicate"
    assert read(database, data.work.id) == final


@pytest.mark.parametrize("phase", ["prepare", "finalize"])
@pytest.mark.parametrize("error", ["python", "database"])
def test_partial_flush_rollback_retry(database, monkeypatch, phase, error):
    data = service.create(database, request()).detail if phase == "prepare" else prepare(database)
    if phase == "finalize":
        decide(database, data)
    original = work_worker.execute_step

    def fail(session, job, work, attempt_id):
        original(session, job, work, attempt_id)  # artifact + approval/checkpoint fully flushed
        if error == "database":
            session.add(
                WorkArtifact(
                    id=uuid4(),
                    job_id=job.id,
                    attempt_id=attempt_id,
                    version=1,
                    kind="proposal",
                    content={},
                    sha256="a" * 64,
                    created_at=utcnow(),
                )
            )  # duplicate version -> aborted savepoint, not just Python exception
            session.flush()
        raise RuntimeError("never persist this secret-like SQL payload")

    monkeypatch.setattr(work_worker, "execute_step", fail)
    before = counts(database)
    result = process_once(database)
    assert result.status == "retry" and result.error_code == "execution_failed"
    failed = read(database, data.work.id)
    assert counts(database) == (before[0], before[1], before[2] + 1, before[3], before[4])
    assert failed.job.checkpoint.phase == phase
    assert failed.job.failure_count == 1 and failed.job.available_at > utcnow()
    assert failed.history[-1].kind == "attempt_failed"
    assert "secret-like" not in failed.model_dump_json()
    assert process_once(database).status == "idle"  # actual eligibility backoff
    monkeypatch.setattr(work_worker, "execute_step", original)
    due(database)
    assert process_once(database).status == ("waiting_human" if phase == "prepare" else "succeeded")
    recovered = read(database, data.work.id)
    assert recovered.job.attempt_count == (2 if phase == "prepare" else 3)
    assert recovered.job.failure_count == 1
    attempts = [h.attempt_id for h in recovered.history if h.attempt_id]
    assert len(attempts) == len(set(attempts))


def test_retry_bound_and_history_evidence(database, monkeypatch):
    data = service.create(database, request()).detail

    def fail(*args):
        raise RuntimeError("payload must not be logged")

    monkeypatch.setattr(work_worker, "execute_step", fail)
    for number in range(1, 6):
        due(database)
        assert process_once(database).status == ("failed" if number == 5 else "retry")
        current = read(database, data.work.id)
        assert current.job.failure_count == current.job.attempt_count == number
    assert current.job.status == "failed" and current.work.state == "waiting"
    assert current.job.checkpoint.phase == "failed"
    assert [h.attempt_number for h in current.history[1:]] == [1, 2, 3, 4, 5]
    assert counts(database) == (1, 1, 6, 0, 0)
    assert process_once(database).status == "idle"


@pytest.mark.parametrize("model", [WorkArtifact, WorkApproval])
def test_failure_at_each_insert_flush_rolls_back_all_new_rows(database, model):
    data = service.create(database, request()).detail

    def fail(mapper, connection, target):
        raise RuntimeError("injected immediately after this individual row insert")

    event.listen(model, "after_insert", fail)
    try:
        assert process_once(database).status == "retry"
    finally:
        event.remove(model, "after_insert", fail)
    assert counts(database) == (1, 1, 2, 0, 0)
    assert read(database, data.work.id).job.checkpoint.phase == "prepare"
    due(database)
    assert process_once(database).status == "waiting_human"


@pytest.mark.parametrize(
    "corruption", ["snapshot", "digest", "phase", "version", "next_action", "proposal_id"]
)
def test_source_checkpoint_tampering_fails_closed(database, corruption):
    data = service.create(database, request()).detail
    with database.begin() as session:
        work = session.get(WorkItem, data.work.id)
        job = session.get(WorkJob, data.job.id)
        if corruption == "snapshot":
            work.source_snapshot = work.source_snapshot | {"text": "unexpected instruction"}
        elif corruption == "digest":
            work.source_sha256 = "a" * 64
        else:
            value = {
                "phase": "unexpected",
                "version": 2,
                "next_action": "run_finalize",
                "proposal_id": str(uuid4()),
            }[corruption]
            key = "proposal_artifact_id" if corruption == "proposal_id" else corruption
            job.checkpoint = job.checkpoint | {key: value}
    assert process_once(database).status == "failed"
    assert counts(database) == (1, 1, 2, 0, 0)
    with database() as session:
        assert session.get(WorkJob, data.job.id).last_error_code == "state_invalid"


@pytest.mark.parametrize("corruption", ["content", "hash", "both", "approval", "status"])
def test_finalize_rechecks_immutable_proposal_and_current_approval(database, corruption):
    data = prepare(database)
    decide(database, data)
    with database.begin() as session:
        artifact = session.get(WorkArtifact, data.artifacts[0].id)
        approval = session.get(WorkApproval, data.approvals[0].id)
        if corruption in {"content", "both"}:
            artifact.content = artifact.content | {"summary": "Pretend publication succeeded"}
        if corruption == "hash":
            artifact.sha256 = "a" * 64
        if corruption == "both":
            artifact.sha256 = service.digest(artifact.content)
            approval.artifact_sha256 = artifact.sha256
        if corruption == "approval":
            approval.artifact_sha256 = "a" * 64
        if corruption == "status":
            approval.status = "rejected"
    assert process_once(database).status == "failed"
    assert len(read(database, data.work.id).artifacts) == 1


def test_decision_checks_actual_content_before_accepting(database):
    data = prepare(database)
    with database.begin() as session:
        artifact = session.get(WorkArtifact, data.artifacts[0].id)
        artifact.content = artifact.content | {"title": "tampered"}
    with pytest.raises(service.WorkError, match="state_invalid"):
        decide(database, data)
    assert len(read(database, data.work.id).history) == 2


def test_workers_compete_one_proposal(database):
    service.create(database, request())
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: process_once(database).status, range(3)))
    assert sorted(results) == ["idle", "idle", "waiting_human"]
    assert counts(database) == (1, 1, 2, 1, 1)


def test_fake_step_has_no_socket_or_subprocess(database, monkeypatch):
    data = service.create(database, request()).detail

    def forbidden(*args, **kwargs):
        raise AssertionError("fake executor attempted external I/O")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    assert process_once(database).status == "waiting_human"
    decide(database, read(database, data.work.id))
    assert process_once(database).status == "succeeded"


def client(pg_engine):
    return TestClient(create_app(Settings(), engine=pg_engine))


def once_cli(pg_engine):
    env = os.environ | {
        "APP_ENV": "local",
        "DATABASE_URL": pg_engine.url.render_as_string(hide_password=False),
    }
    result = subprocess.run(
        [sys.executable, "-m", "efren_bot.work_worker", "--once"],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    assert "postgresql" not in result.stdout and not result.stderr
    return json.loads(result.stdout)


def test_http_restart_and_new_worker_processes(database, pg_engine):
    body = request().model_dump(mode="json")
    with client(pg_engine) as first:
        assert first.get("/api/work").json() == {
            "mode": "synthetic_work",
            "executor": "fake_db_v1",
            "works": [],
        }
        response = first.post("/api/work", json=body)
        assert response.status_code == 202
        initial = response.json()["detail"]
        assert first.post("/api/work", json=body).status_code == 200
    assert counts(database) == (1, 1, 1, 0, 0)
    assert once_cli(pg_engine)["status"] == "waiting_human"
    work_id = initial["work"]["id"]
    with client(pg_engine) as second:  # new app/session; no reset of DB between phases
        waiting = second.get("/api/work/" + work_id).json()
        assert waiting["job"]["id"] == initial["job"]["id"]
        assert waiting["history"][0] == initial["history"][0]
        approval = waiting["approvals"][0]
        path = f"/api/work/{work_id}/approvals/{approval['id']}/decision"
        value = {
            "decision": "approve",
            "artifact_sha256": approval["artifact_sha256"],
            "reason": "Revisión sintética después de reiniciar API",
        }
        recorded = second.post(path, json=value)
        assert recorded.status_code == 200 and recorded.json()["status"] == "recorded"
    assert once_cli(pg_engine)["status"] == "succeeded"  # another fresh OS process
    with client(pg_engine) as third:
        final = third.get("/api/work/" + work_id).json()
        assert final["work"]["state"] == "delivered"
        assert final["job"]["id"] == initial["job"]["id"]
        assert final["job"]["attempt_count"] == 2
        assert final["history"][:2] == waiting["history"]
        assert third.post(path, json=value).json()["status"] == "duplicate"
        assert third.get("/api/work/" + work_id).json() == final
        WorkDetail.model_validate(final)
    assert once_cli(pg_engine)["status"] == "idle"


def crash_child(url, connection):
    engine = make_engine(Settings(database_url=url))
    original = work_worker.execute_step

    def pause(session, job, work, attempt_id):
        original(session, job, work, attempt_id)
        connection.send("artifact-approval-checkpoint-flushed-uncommitted")
        connection.recv()

    work_worker.execute_step = pause
    try:
        process_once(session_factory(engine))
    finally:
        engine.dispose()
        connection.close()


def test_kill_only_owned_child_rolls_back_and_recovers(database, pg_engine):
    data = service.create(database, request()).detail
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(
        target=crash_child, args=(pg_engine.url.render_as_string(hide_password=False), child)
    )
    process.start()
    child.close()
    try:
        assert parent.poll(15), "child did not flush its own uncommitted step"
        assert parent.recv() == "artifact-approval-checkpoint-flushed-uncommitted"
        assert counts(database) == (1, 1, 1, 0, 0)
        assert process_once(database).status == "idle"
        process.kill()
        process.join(5)
        assert not process.is_alive() and process.exitcode < 0
        deadline = time.monotonic() + 5
        while True:
            result = process_once(database)
            if result.status != "idle" or time.monotonic() >= deadline:
                break
            time.sleep(0.05)
        assert result.status == "waiting_human"
        recovered = read(database, data.work.id)
        assert recovered.job.attempt_count == 1  # killed transaction never committed
        assert counts(database) == (1, 1, 2, 1, 1)
    finally:
        if process.is_alive():
            process.kill()
            process.join(5)
        parent.close()


def test_old_fixture_projection_unchanged(database):
    for fixture in demo_fixtures():
        ingest(database, fixture.event)
        assert project_fixture(database).status == "processed"
    data = prepare(database)
    decide(database, data)
    process_once(database)
    with database() as session:
        assert session.scalar(select(func.count()).select_from(Task)) == 1
        assert session.scalar(select(Task)).state == "needs_context"
        assert session.scalar(select(func.count()).select_from(Activity)) == 3


def test_http_closed_boundaries_missing_and_unavailable(database, pg_engine):
    with client(pg_engine) as api:
        data = request().model_dump(mode="json")
        assert api.post("/api/work", json=data | {"owner_id": "efren"}).status_code == 422
        assert api.post("/api/work", json=data | {"idempotency_key": "not-uuid"}).status_code == 422
        assert api.post("/api/work", json=data | {"fixture_id": "thanks"}).status_code == 422
        assert counts(database) == (0, 0, 0, 0, 0)
        assert api.get("/api/work/" + str(uuid4())).status_code == 404
        assert api.get("/api/work/not-uuid").status_code == 422
        created = api.post("/api/work", json=data).json()["detail"]
        assert api.post("/api/work", json=data | {"fixture_id": "reply"}).status_code == 409
        assert api.get("/api/work").json()["works"][0]["id"] == created["work"]["id"]


def test_detail_uses_repeatable_read(database, pg_engine):
    data = service.create(database, request()).detail
    observed = []

    def inspect_isolation(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("SELECT work_items"):
            observed.append(connection.get_isolation_level())

    event.listen(pg_engine, "before_cursor_execute", inspect_isolation)
    try:
        with client(pg_engine) as api:
            assert api.get("/api/work/" + str(data.work.id)).status_code == 200
    finally:
        event.remove(pg_engine, "before_cursor_execute", inspect_isolation)
    assert observed == ["REPEATABLE READ"]


def test_work_list_latest_50_stable_order(database, pg_engine):
    details = [service.create(database, request()).detail for _ in range(51)]
    with database.begin() as session:
        same_time = utcnow()
        for work in session.scalars(select(WorkItem)):
            work.created_at = same_time
    with client(pg_engine) as api:
        listing = api.get("/api/work").json()["works"]
    assert len(listing) == 50
    assert [w["id"] for w in listing] == sorted(str(d.work.id) for d in details)[:50]


def test_database_failure_sanitized(database, pg_engine):
    def fail(connection, cursor, statement, parameters, context, executemany):
        raise SQLAlchemyError("sensitive SQL connection credentials payload")

    event.listen(pg_engine, "before_cursor_execute", fail)
    try:
        with client(pg_engine) as api:
            response = api.get("/api/work")
    finally:
        event.remove(pg_engine, "before_cursor_execute", fail)
    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}


def test_worker_loop_sleeps_outside_transaction(database, pg_engine, monkeypatch):
    service.create(database, request())
    worker = work_worker.Worker(Settings(), engine=pg_engine)

    def sleep(seconds):
        assert pg_engine.pool.checkedout() == 0
        raise KeyboardInterrupt()

    monkeypatch.setattr(work_worker.time, "sleep", sleep)
    with pytest.raises(KeyboardInterrupt):
        worker.run()
    assert counts(database) == (1, 1, 2, 1, 1)


def test_wire_examples(database):
    initial = service.create(database, request()).detail
    assert process_once(database).status == "waiting_human"
    waiting = read(database, initial.work.id)
    # Safe synthetic examples only; pytest hides them unless explicitly requested.
    print("INITIAL_EXAMPLE=" + initial.model_dump_json())
    print("WAITING_EXAMPLE=" + waiting.model_dump_json())
