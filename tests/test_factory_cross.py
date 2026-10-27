"""Rehearsal with the REAL scraft-ops binary and a fake agent: no model, no network, no creds.

Set SCRAFT_OPS_BIN to a built ``scraft-ops``; without it these tests skip. This is the contract
test between the plant (this repo) and the execution unit (scraft-ops).
"""

import json
import os
import subprocess
from datetime import timedelta
from pathlib import Path

import pytest
from factory_helpers import POLICY, PROFILES, item
from sqlalchemy import select, text

from efren_bot.factory import effects as fx
from efren_bot.factory.contracts import JobPolicy, JobRepo, JobSource, JobSpec
from efren_bot.factory.executor import ScraftOpsExecutor
from efren_bot.factory.models import FactoryEffect, FactoryJob
from efren_bot.factory.profiles import DEFAULT_DIR
from efren_bot.factory.projects import Project, ProjectRegistry
from efren_bot.factory.service import FactoryService

BIN = os.environ.get("SCRAFT_OPS_BIN", "")
needs_binary = pytest.mark.skipif(not BIN, reason="SCRAFT_OPS_BIN not set")


def git(repo, *args):
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    return subprocess.run(
        ["git", *args], cwd=repo, env=env, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "landing"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    (path / "README.md").write_text("landing\n")
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "init")
    return path


@pytest.fixture
def profile_dir(tmp_path):
    """Override ``frontend`` with a shell check so the rehearsal does not need npm."""
    directory = tmp_path / "profiles"
    directory.mkdir()
    profile = json.loads((DEFAULT_DIR / "frontend.json").read_text())
    profile["checks"] = [
        {
            "name": "smoke",
            "command": ["sh", "-c", "exit 0"],
            "mandatory": True,
            "timeout_seconds": 30,
        }
    ]
    (directory / "frontend.json").write_text(json.dumps(profile))
    return directory


def prune(value):
    """Go omits empty optional fields (omitempty); compare what carries information."""
    if isinstance(value, dict):
        pruned = {k: prune(v) for k, v in value.items()}
        return {k: v for k, v in pruned.items() if v not in ([], {}, "", None)}
    if isinstance(value, list):
        return [prune(v) for v in value]
    return value


@needs_binary
def test_bundled_profiles_match_the_ones_scraft_ops_ships():
    for name in PROFILES.names():
        out = subprocess.run(
            [BIN, "factory", "profiles", name], capture_output=True, text=True, check=True
        )
        mine = json.loads((DEFAULT_DIR / f"{name}.json").read_text())
        assert prune(json.loads(out.stdout)) == prune(mine), (
            f"{name}: the plant and scraft-ops disagree; copy internal/factory/profiles/*.json"
        )


def spec_for(repo, job_id, files):
    return JobSpec(
        job_id=job_id,
        source=JobSource(kind="notion", ref="page-1"),
        role="development",
        profile="frontend",
        repo=JobRepo(path=str(repo), base_ref="main"),
        brief="Cambiar el botón de la landing a verde",
        policy=JobPolicy(allow_worktree=True, allow_commit=True, run_review=True, executor="fake"),
        mock={"files": files},
    )


@needs_binary
def test_the_real_execution_unit_returns_a_record_the_plant_understands(
    tmp_path, repo, profile_dir
):
    exe = ScraftOpsExecutor(BIN, state_dir=str(tmp_path / "state"), profile_dir=str(profile_dir))
    rec = exe.run(spec_for(repo, "x-1", {"src/button.css": ".b{color:green}\n"}))
    assert rec.status == "succeeded" and rec.risk.tier == "passive" and not rec.requires_human
    assert rec.effect_policy("open_pr") == "auto" and rec.effect_policy("merge") == "forbidden"
    assert rec.head_sha and Path(rec.worktree).is_dir()
    assert git(repo, "status", "--porcelain") == ""  # the owner's checkout was never touched


@needs_binary
def test_a_blocked_run_is_data_not_an_exception(tmp_path, repo, profile_dir):
    exe = ScraftOpsExecutor(BIN, state_dir=str(tmp_path / "state"), profile_dir=str(profile_dir))
    spec = spec_for(repo, "x-2", {"a.txt": "x\n"})
    spec.policy.allow_worktree = False
    rec = exe.run(spec)
    assert rec.status == "blocked" and rec.requires_human


@pytest.mark.integration
@needs_binary
def test_full_stack_notion_task_to_a_gated_pull_request(pg_engine, tmp_path, repo, profile_dir):
    from efren_bot.db import session_factory

    with pg_engine.begin() as connection:
        assert connection.scalar(text("SELECT current_database()")) == "efren_bot_test"
        connection.execute(
            text("TRUNCATE factory_effects, factory_jobs, factory_admissions, factory_items")
        )
    sessions = session_factory(pg_engine)
    gateway = fx.RecordingGateway()
    registry = ProjectRegistry(
        [
            Project(
                name="landing",
                profile="frontend",
                repo_path=str(repo),
                keywords=["landing"],
                notion_projects=["Landing Web"],
            )
        ]
    )
    service = FactoryService(
        sessions,
        projects=registry,
        profiles=PROFILES,
        policy=POLICY,
        executor=ScraftOpsExecutor(
            BIN, state_dir=str(tmp_path / "state"), profile_dir=str(profile_dir), executor="fake"
        ),
        gateway=gateway,
        agent_executor="fake",
        effect_ttl=timedelta(hours=1),
    )
    safe = item(project_hint="Landing Web", mock={"files": {"src/button.css": ".b{color:green}\n"}})
    risky = item(
        text="Actualizar dependencias de la landing",
        external_id="ext-2",
        project_hint="Landing Web",
        mock={"files": {"package.json": "{}\n"}},
    )
    assert [r.decision for r in service.ingest([safe, risky])] == ["admit", "admit"]
    while service.process_one() is not None:
        pass
    with sessions() as session:
        jobs = {j.spec["source"]["ref"]: j for j in session.scalars(select(FactoryJob))}
        assert {j.status for j in jobs.values()} == {"succeeded"}
        by_job = {}
        for effect in session.scalars(select(FactoryEffect)):
            by_job.setdefault(effect.job_id, {})[effect.kind] = effect
    safe_effects, risky_effects = by_job[jobs["ext-1"].id], by_job[jobs["ext-2"].id]
    assert safe_effects["open_pr"].state == "executed"  # passive + profile says auto
    assert risky_effects["open_pr"].state == "proposed"  # package.json forces a human
    assert jobs["ext-2"].run_record["risk"]["tier"] == "high"
    assert [k for k, _, _ in gateway.executed] == ["open_pr"]
    done = service.decide_effect(
        risky_effects["open_pr"].id, "approve", fingerprint=risky_effects["open_pr"].fingerprint
    )
    assert done.state == "approved" and len(gateway.executed) == 1
    assert service.run_approved_effects() == 1 and len(gateway.executed) == 2
