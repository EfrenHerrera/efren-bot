import json

import pytest
from pydantic import ValidationError

from efren_bot.config import Settings
from efren_bot.factory.contracts import JobPolicy, JobRepo, JobSource, JobSpec, RunRecord
from efren_bot.factory.profiles import ProfileRegistry
from efren_bot.factory.projects import Project
from efren_bot.factory.wiring import build_executor


def test_frontend_prefers_opencode_without_implicit_fallback():
    assert ProfileRegistry.load().get("frontend").executor == "opencode"
    policy = JobPolicy(allow_worktree=True, executor="opencode")
    assert policy.fallback_executors == []


def test_explicit_fallback_is_retained_in_project_policy_and_record():
    project = Project(
        name="pilot",
        profile="frontend",
        repo_path="/sandbox",
        executor="opencode",
        fallback_executors=["claude"],
    )
    policy = JobPolicy(executor=project.executor, fallback_executors=project.fallback_executors)
    assert policy.model_dump()["fallback_executors"] == ["claude"]
    record = RunRecord.model_validate(
        {
            "schema": "scraft.factory.run/1",
            "job_id": "pilot-a1",
            "status": "succeeded",
            "executor": "claude",
            "execution_attempts": [
                {
                    "executor": "opencode",
                    "phase": "build",
                    "status": "unavailable",
                    "reason": "quota_exhausted",
                    "log_ref": "/state/opencode.log",
                },
                {
                    "executor": "claude",
                    "phase": "build",
                    "status": "succeeded",
                    "log_ref": "/state/claude.log",
                },
            ],
        }
    )
    assert [attempt.executor for attempt in record.execution_attempts] == ["opencode", "claude"]
    assert len(record.model_dump(mode="json")["execution_attempts"]) == 2


@pytest.mark.parametrize(
    "values",
    [
        {"executor": "opencode", "fallback_executors": ["opencode"]},
        {"executor": "opencode", "fallback_executors": ["claude", "claude"]},
        {"executor": "opencode", "fallback_executors": ["fake"]},
        {"executor": "fake", "fallback_executors": ["claude"]},
        {"executor": "opencode", "fallback_executors": ["unknown"]},
        {"executor": "opencode", "model": "openai/pinned", "fallback_executors": ["claude"]},
        {"executor": "opencode", "effort": "high", "fallback_executors": ["claude"]},
    ],
)
def test_invalid_or_ambiguous_fallback_policy_fails_closed(values):
    with pytest.raises(ValidationError):
        JobPolicy.model_validate(values)


def test_host_fallback_is_explicit_not_a_global_subscription_default(monkeypatch):
    monkeypatch.delenv("FACTORY_AGENT_FALLBACKS", raising=False)
    assert Settings().factory_agent_fallbacks is None
    monkeypatch.setenv("FACTORY_AGENT_FALLBACKS", json.dumps(["claude"]))
    assert Settings().factory_agent_fallbacks == ["claude"]
    monkeypatch.setenv("FACTORY_AGENT_FALLBACKS", "[]")
    assert Settings().factory_agent_fallbacks == []


def test_empty_fallback_is_omitted_for_older_strict_execution_units():
    spec = JobSpec(
        job_id="legacy",
        source=JobSource(kind="manual"),
        role="development",
        profile="frontend",
        repo=JobRepo(path="/sandbox", base_ref="main"),
        brief="Change copy",
        policy=JobPolicy(executor="fake"),
    )
    assert "fallback_executors" not in spec.wire()["policy"]


def test_host_default_does_not_override_an_already_queued_executor_policy():
    executor = build_executor(Settings(factory_agent_executor="opencode"))
    assert "--executor" not in executor.command()
