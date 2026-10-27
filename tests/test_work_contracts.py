import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from efren_bot.work.contracts import ArtifactContent, Checkpoint, CreateWork, Decision, WorkDetail


@pytest.mark.parametrize("field", ["owner_id", "source_url", "command", "state", "source_snapshot"])
def test_create_forbids_client_control(field):
    with pytest.raises(ValidationError):
        CreateWork.model_validate(
            {"idempotency_key": str(uuid4()), "fixture_id": "request_video", field: "forbidden"}
        )


@pytest.mark.parametrize("reason", ["", " \n", "x\x00y", "x" * 501, 42])
def test_decision_reason_closed(reason):
    with pytest.raises(ValidationError):
        Decision(decision="approve", artifact_sha256="a" * 64, reason=reason)


@pytest.mark.parametrize("digest", ["a" * 63, "A" * 64, "z" * 64, "sha256:" + "a" * 64])
def test_digest_is_exact_hex(digest):
    with pytest.raises(ValidationError):
        Decision(decision="approve", artifact_sha256=digest, reason="Synthetic review")


def test_worker_local_guard_before_engine(monkeypatch):
    from efren_bot import work_worker

    def forbidden(settings):
        pytest.fail("nonlocal mode reached engine")

    monkeypatch.setattr(work_worker, "make_engine", forbidden)
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(ValidationError):
        work_worker.Worker()


@pytest.mark.parametrize("field", ["command", "owner_id", "status", "source_url"])
def test_decision_forbids_extras(field):
    with pytest.raises(ValidationError):
        Decision.model_validate(
            {
                "decision": "approve",
                "artifact_sha256": "a" * 64,
                "reason": "Synthetic only",
                field: "forbidden",
            }
        )


@pytest.mark.parametrize("version", [True, 1.0, "1", 2])
def test_checkpoint_version_is_closed(version):
    with pytest.raises(ValidationError):
        Checkpoint(
            version=version, phase="prepare", source_sha256="a" * 64, next_action="run_prepare"
        )


def test_recipe_unknown_and_artifact_content_closed():
    from efren_bot.models import WorkItem
    from efren_bot.work import service

    with pytest.raises(service.InvalidState):
        service.validate_source(WorkItem(fixture_id="request_video", recipe_version=2))
    payload = service.content(service.digest(service.source())).model_dump(mode="json")
    for change in (
        {"no_external_effects": False},
        {"command": "forbidden"},
        {"action": "PUBLISH"},
    ):
        with pytest.raises(ValidationError):
            ArtifactContent.model_validate(payload | change)


def test_documented_real_wire_examples_match_closed_dtos_and_hashes():
    from efren_bot.work import service

    document = Path("docs/synthetic-work.md").read_text()
    blocks = [part.split("```", 1)[0] for part in document.split("```json\n")[1:]]
    assert len(blocks) == 2
    initial, waiting = [WorkDetail.model_validate(json.loads(block)) for block in blocks]
    assert initial.work.id == waiting.work.id
    assert initial.job.id == waiting.job.id
    assert initial.history == waiting.history[:1]
    assert initial.job.checkpoint.phase == "prepare"
    assert waiting.job.checkpoint.phase == "await_approval"
    assert initial.work.source_sha256 == service.digest(service.source())
    assert waiting.artifacts[0].sha256 == service.digest(
        waiting.artifacts[0].content.model_dump(mode="json")
    )
    assert waiting.approvals[0].artifact_sha256 == waiting.artifacts[0].sha256


@pytest.mark.parametrize("app_env", ["local", "production"])
def test_cli_rejected_settings_sanitized_before_engine_or_network(app_env):
    invalid_url = "postgresql+psycopg://synthetic:PASSWORDNOTREAL@invalid.example/not_local"
    script = """
import socket
import sys
from efren_bot import work_worker

def forbidden(*args, **kwargs):
    print("FORBIDDEN_ENGINE_OR_NETWORK", file=sys.stderr, flush=True)
    raise AssertionError("engine/network must not be reached")

work_worker.make_engine = forbidden
socket.create_connection = forbidden
raise SystemExit(work_worker.main(["--once"]))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=os.environ | {"APP_ENV": app_env, "DATABASE_URL": invalid_url},
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "FORBIDDEN_ENGINE_OR_NETWORK" not in output
    assert "PASSWORDNOTREAL" not in output
    assert invalid_url not in output
    assert "Traceback" not in output
    assert result.stdout == "Invalid local configuration\n"
    assert result.stderr == ""
