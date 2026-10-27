import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from bridge_helpers import (
    THREAD_URL,
    TOKEN,
    URL,
    profile_data,
    result_data,
    thread_profile_data,
    write_profile,
)
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from efren_bot.api import create_app
from efren_bot.bridge.capability import assess
from efren_bot.bridge.contracts import ClaimInput, CompleteInput, CreateRun, LeaseInput
from efren_bot.bridge.processes import HostLock
from efren_bot.bridge.profile import load_profile
from efren_bot.bridge.proof import seal
from efren_bot.bridge.runner import BridgeClient, Runner
from efren_bot.bridge.service import BridgeError, BridgeService
from efren_bot.bridge.supervisor import Supervisor
from efren_bot.config import Settings
from efren_bot.models import Base, BridgePresence, BridgeRun, Event, utcnow

pytestmark = pytest.mark.integration


@pytest.fixture
def bridge(database, tmp_path):
    path = write_profile(tmp_path)
    settings = Settings(claude_bridge_enabled=True, claude_bridge_profile_file=str(path))
    service = BridgeService(settings, database)
    profile = load_profile(path, host=True)
    claim = ClaimInput(
        runner_id=uuid4(),
        profile_fingerprint=profile.fingerprint,
        cli_version=profile.cli.verified_version,
        cli_sha256=profile.cli.verified_sha256,
        policy_verified=True,
    )
    assert service.claim(claim) is None
    return service, claim, path


def create(service, key=None, url=URL):
    return service.create(CreateRun(idempotency_key=key or uuid4(), requested_slack_permalink=url))


def lease(claim, runner):
    return LeaseInput(
        runner_id=runner.runner_id,
        lease_token=claim["lease_token"],
        profile_fingerprint=runner.profile_fingerprint,
    )


def complete_input(data, outcome="succeeded"):
    return CompleteInput.from_json(
        {
            **data.model_dump(mode="json"),
            "outcome": outcome,
            "result": result_data() if outcome == "succeeded" else None,
            "error_code": "cli_failed" if outcome == "failed" else None,
        }
    )


def test_migration_matches_models(pg_engine):
    with pg_engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []


def test_idempotency_and_no_fixture_mutation(bridge, database):
    service, runner, _ = bridge
    key = uuid4()
    first, new = create(service, key)
    replay, new_replay = create(service, key)
    assert new and not new_replay and first == replay
    assert first.id.version == 4 and first.deadline_at - first.created_at == timedelta(seconds=120)
    with pytest.raises(BridgeError, match="idempotency_conflict"):
        create(service, key, URL + "0")
    claim = service.claim(runner)
    done = service.lease(first.id, complete_input(lease(claim, runner)), complete=True)["run"]
    assert done.status == "succeeded" and done.result.evidence_refs == [URL]
    assert create(service, key)[0].id == first.id
    with database() as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 0
        assert session.scalar(select(func.count()).select_from(BridgeRun)) == 1


def test_concurrent_create_and_claim(bridge):
    service, runner, _ = bridge
    key = uuid4()
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda _: create(service, key), range(5)))
    assert len({r.id for r, _ in results}) == 1
    assert sum(int(new) for _, new in results) == 1
    create(service)
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims = list(pool.map(lambda _: service.claim(runner), range(4)))
    assert sum(c is not None for c in claims) == 1


def test_fencing_cancel_and_terminal_not_overwritten(bridge):
    service, runner, _ = bridge
    run, _ = create(service)
    claim = service.claim(runner)
    data = lease(claim, runner)
    wrong = data.model_copy(update={"lease_token": uuid4()})
    with pytest.raises(BridgeError, match="lease_lost"):
        service.lease(run.id, wrong)
    assert service.read(run.id, cancel=True).cancel_requested
    assert service.lease(run.id, data)["cancel_requested"]
    final = service.lease(run.id, complete_input(data), complete=True)["run"]
    assert final.status == "cancelled" and final.result is None and final.error_code is None
    with pytest.raises(BridgeError, match="run_terminal"):
        service.lease(run.id, complete_input(data), complete=True)
    assert service.read(run.id, cancel=True) == final


@pytest.mark.parametrize(
    "cancel,deadline,expected",
    [
        (False, False, "interrupted"),
        (False, True, "timeout"),
        (True, False, None),
    ],
)
def test_expiry_commits_even_on_rejected_complete(bridge, database, cancel, deadline, expected):
    service, runner, _ = bridge
    run, _ = create(service)
    claim = service.claim(runner)
    with database.begin() as session:
        stored = session.get(BridgeRun, run.id)
        stored.cancel_requested = cancel
        stored.lease_expires_at = utcnow() - timedelta(seconds=1)
        if deadline:
            stored.deadline_at = utcnow() - timedelta(seconds=1)
    with pytest.raises(BridgeError, match="run_terminal"):
        service.lease(run.id, complete_input(lease(claim, runner)), complete=True)
    with database() as session:
        stored = session.get(BridgeRun, run.id)
        assert stored.status == ("cancelled" if cancel else "failed")
        assert stored.error_code == expected
    assert service.claim(runner) is None  # no requeue


def test_queued_cancel_timeout_and_presence_expiry(bridge, database):
    service, runner, _ = bridge
    run, _ = create(service)
    assert service.read(run.id, cancel=True).status == "cancelled"
    run, _ = create(service)
    with database.begin() as session:
        session.get(BridgeRun, run.id).deadline_at = utcnow() - timedelta(seconds=1)
        session.get(BridgePresence, 1).seen_at = utcnow() - timedelta(seconds=16)
    assert service.read(run.id).error_code == "timeout"
    with pytest.raises(BridgeError, match="runner_unavailable"):
        create(service)
    assert service.claim(runner) is None


def test_profile_drift_admission_claim_and_complete(bridge, database):
    service, runner, path = bridge
    run, _ = create(service)
    claim = service.claim(runner)
    profile = profile_data()
    profile["profile_version"] = 2
    write_profile(path.parent, profile)
    with pytest.raises(BridgeError, match="profile_mismatch"):
        service.claim(runner)
    with pytest.raises(BridgeError, match="idempotency_conflict"):
        with database() as session:
            key = session.get(BridgeRun, run.id).idempotency_key
        create(service, key)
    with pytest.raises(BridgeError, match="profile_mismatch"):
        service.lease(run.id, complete_input(lease(claim, runner)), complete=True)
    assert service.read(run.id).status == "running"


def test_invalid_result_rollback_and_cancel_complete_race(bridge):
    service, runner, _ = bridge
    run, _ = create(service)
    claim = service.claim(runner)
    payload = complete_input(lease(claim, runner)).model_dump(mode="json")
    payload["result"]["evidence_refs"] = [URL + "1"]
    with pytest.raises(BridgeError, match="invalid_result"):
        service.lease(run.id, CompleteInput.from_json(payload), complete=True)
    assert service.read(run.id).status == "running"
    with ThreadPoolExecutor(max_workers=2) as pool:
        cancel = pool.submit(service.read, run.id, cancel=True)
        complete = pool.submit(
            service.lease, run.id, complete_input(lease(claim, runner)), complete=True
        )
        cancelled = cancel.result()
        completed = complete.result()["run"]
    assert service.read(run.id).status in {"cancelled", "succeeded"}
    if cancelled.cancel_requested:
        assert completed.status == "cancelled"


def test_capability_mismatch_never_creates_presence(bridge, database):
    service, runner, _ = bridge
    with database.begin() as session:
        session.delete(session.get(BridgePresence, 1))
    for update in ({"cli_sha256": "c" * 64}, {"cli_version": "2.1.308"}):
        with pytest.raises(BridgeError, match="capability_unavailable"):
            service.claim(runner.model_copy(update=update))
    with database() as session:
        assert session.get(BridgePresence, 1) is None


def test_http_protocol_real_postgres(bridge, pg_engine):
    service, runner, path = bridge
    token = path.parent / "token"
    token.write_text(TOKEN + "\n")
    token.chmod(0o600)
    settings = service.settings.model_copy(update={"claude_bridge_token_file": str(token)})
    browser = {"Origin": "http://127.0.0.1:5173", "Authorization": "Bearer " + TOKEN}
    host = {"Authorization": "Bearer " + TOKEN}
    with TestClient(
        create_app(settings, engine=pg_engine), base_url="http://127.0.0.1:8000"
    ) as client:
        assert client.get("/api/bridge/status", headers=browser).json()["configuration"] == "ready"
        data = {"idempotency_key": str(uuid4()), "requested_slack_permalink": URL}
        response = client.post("/api/bridge/runs", json=data, headers=browser)
        assert response.status_code == 202
        run = response.json()["run"]
        assert client.post("/api/bridge/runs", json=data, headers=browser).status_code == 200
        claim = client.post(
            "/api/bridge/runner/claim", headers=host, json=runner.model_dump(mode="json")
        ).json()["claim"]
        payload = {
            "runner_id": str(runner.runner_id),
            "lease_token": claim["lease_token"],
            "profile_fingerprint": runner.profile_fingerprint,
        }
        base = "/api/bridge/runner/runs/" + run["id"]
        assert client.post(base + "/heartbeat", headers=host, json=payload).status_code == 200
        payload.update(outcome="succeeded", result=result_data(), error_code=None)
        final = client.post(base + "/complete", headers=host, json=payload)
        assert final.json()["run"]["status"] == "succeeded"
        assert client.get("/api/bridge/runs/" + run["id"], headers=browser).json() == final.json()
        assert set(final.json()["run"]) == set(run)
        for forbidden in ("lease_token", "runner_id", "idempotency_key", "stdout", TOKEN):
            assert forbidden not in final.text


@pytest.mark.parametrize("mode,status", [("success", "succeeded"), ("wrongurl", "failed")])
@pytest.mark.parametrize("binding", [1, 2])
def test_runner_supervisor_fake_cli_api_postgres(
    bridge, pg_engine, monkeypatch, mode, status, binding
):
    """Protocol integration, NOT native policy/Slack evidence. All files synthetic."""
    service, _, path = bridge
    directory = path.parent
    url = THREAD_URL if binding == 2 else URL
    if binding == 2:
        write_profile(directory, thread_profile_data())
    token = directory / "token"
    token.write_text(TOKEN + "\n")
    token.chmod(0o600)
    profile = load_profile(path, host=True)
    synthetic_identity = {"profile_fingerprint": profile.fingerprint, "cli_sha256": "b" * 64}
    monkeypatch.setattr("efren_bot.bridge.proof.identity", lambda *a: synthetic_identity)
    observations = {
        case: {
            "attempts": n,
            "executed": 5 if case == "allowed" else 0,
            "hook_events": n,
            "native_init": True,
        }
        for case, n in (("allowed", 5), ("wrong_scope", 2), ("failures", 5))
    }
    seal(profile, directory, observations, synthetic_identity)
    monkeypatch.setattr(
        "efren_bot.bridge.capability.probe_binary", lambda *a: ("2.1.309", "b" * 64)
    )
    runs = directory / "runs"
    runs.mkdir(mode=0o700)
    capability = assess(profile, runs)
    settings = service.settings.model_copy(update={"claude_bridge_token_file": str(token)})
    browser = {"Origin": "http://127.0.0.1:5173", "Authorization": "Bearer " + TOKEN}
    launched = []

    def launch(argv, **kwargs):
        fake = Path(__file__).parent / "fakes" / "bridge_cli.py"
        process = subprocess.Popen([sys.executable, str(fake), mode, *argv[1:]], **kwargs)
        launched.append(process)
        return process

    with TestClient(
        create_app(settings, engine=pg_engine), base_url="http://127.0.0.1:8000"
    ) as api:

        def transport(request):
            response = api.request(
                request.method,
                str(request.url),
                content=request.content,
                headers=dict(request.headers),
            )
            return httpx.Response(response.status_code, content=response.content)

        client = BridgeClient(TOKEN, _transport=httpx.MockTransport(transport))
        try:
            with HostLock(directory) as lock:
                supervisor = Supervisor(
                    runs, path, lock, _launch=launch, _probe=lambda *a: ("2.1.309", "b" * 64)
                )
                runner = Runner(client, supervisor, path)
                assert runner.once(profile, capability) is False
                data = {"idempotency_key": str(uuid4()), "requested_slack_permalink": url}
                response = api.post("/api/bridge/runs", headers=browser, json=data)
                assert response.status_code == 202
                run = response.json()["run"]
                assert runner.once(profile, capability) is True
                final = api.get("/api/bridge/runs/" + run["id"], headers=browser).json()["run"]
                assert final["status"] == status
                assert (final["result"] is not None) == (status == "succeeded")
                assert final["requested_slack_permalink"] == url
                if status == "succeeded":
                    assert final["result"]["evidence_refs"] == [url]
                    assert "RAW_SLACK_SECRET" not in str(final)
                    if binding == 2:
                        assert any("100 mensajes" in w for w in final["result"]["warnings"])
                assert api.post("/api/bridge/runs", headers=browser, json=data).status_code == 200
                assert runner.once(profile, capability) is False
                assert len(launched) == 1 and launched[0].poll() is not None
                assert not lock.journal.exists() and list(runs.iterdir()) == []
        finally:
            client.close()
