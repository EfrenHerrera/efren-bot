import json

import pytest
from factory_helpers import item, record
from sqlalchemy import select, text

from efren_bot.config import Settings
from efren_bot.db import session_factory
from efren_bot.factory.effects import RecordingGateway
from efren_bot.factory.executor import ScriptedExecutor
from efren_bot.factory.models import FactoryEffect, FactoryJob
from efren_bot.factory.wiring import build_service

pytestmark = pytest.mark.integration


@pytest.fixture
def fallback_service(pg_engine, tmp_path):
    with pg_engine.begin() as connection:
        assert connection.scalar(text("SELECT current_database()")) == "efren_bot_test"
        connection.execute(
            text("TRUNCATE factory_effects, factory_jobs, factory_admissions, factory_items")
        )
    sessions = session_factory(pg_engine)
    registry = tmp_path / "projects.json"
    registry.write_text(
        json.dumps(
            {
                "projects": [
                    {
                        "name": "pilot",
                        "profile": "frontend",
                        "repo_path": "/sandbox",
                        "fallback_executors": ["claude"],
                    }
                ]
            }
        )
    )

    def build(host_fallbacks=None, respond=None):
        def default_response(spec):
            attempts = [{"executor": "opencode", "phase": "build", "status": "succeeded"}]
            if spec.policy.fallback_executors:
                attempts = [
                    {
                        "executor": "opencode",
                        "phase": "build",
                        "status": "unavailable",
                        "reason": "not_installed",
                    },
                    {"executor": "claude", "phase": "build", "status": "succeeded"},
                ]
            return record(
                spec, executor=attempts[-1]["executor"], effects=[], execution_attempts=attempts
            )

        executor = ScriptedExecutor(respond or default_response)
        service = build_service(
            Settings(
                factory_projects_file=str(registry),
                factory_agent_executor="",
                factory_agent_fallbacks=host_fallbacks,
            ),
            sessions,
            executor=executor,
            gateway=RecordingGateway(),
        )
        return service, executor

    return sessions, build


@pytest.mark.parametrize(
    "host_fallbacks, expected", [(None, ["claude"]), ([], []), (["claude"], ["claude"])]
)
def test_fallback_config_reaches_queued_spec_and_persisted_receipts(
    fallback_service, host_fallbacks, expected
):
    sessions, build = fallback_service
    service, executor = build(host_fallbacks)
    admitted = service.ingest([item(project_hint="pilot")])[0]
    with sessions() as session:
        policy = session.get(FactoryJob, admitted.job_id).spec["policy"]
        assert policy["executor"] == "opencode"
        assert policy.get("fallback_executors", []) == expected
    service.process_one()
    assert executor.calls[0].policy.fallback_executors == expected
    with sessions() as session:
        result = session.get(FactoryJob, admitted.job_id)
        assert result.attempt_count == 1 and result.status == "succeeded"
        assert [a["executor"] for a in result.run_record["execution_attempts"]] == (
            ["opencode", "claude"] if expected else ["opencode"]
        )
        assert list(session.scalars(select(FactoryEffect))) == []


def test_stopped_job_never_accepts_late_fallback_result(fallback_service):
    sessions, build = fallback_service
    holder = {}

    def respond(spec):
        service.control_job(holder["job"], "stop")
        return record(
            spec,
            executor="claude",
            execution_attempts=[
                {"executor": "opencode", "phase": "build", "status": "unavailable"},
                {"executor": "claude", "phase": "build", "status": "succeeded"},
            ],
        )

    service, _ = build(respond=respond)
    holder["job"] = service.ingest([item(project_hint="pilot")])[0].job_id
    service.process_one()
    with sessions() as session:
        job = session.get(FactoryJob, holder["job"])
        assert job.status == "cancelled" and job.run_record is None
        assert list(session.scalars(select(FactoryEffect))) == []
    assert service.gateway.executed == []
