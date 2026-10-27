"""Factory plant against a real (separate) PostgreSQL: funnel, jobs, fencing, effect gate."""

from datetime import timedelta
from uuid import uuid4

import pytest
from factory_helpers import POLICY, PROFILES, item, projects, record
from sqlalchemy import select, text, update

from efren_bot.factory import effects as fx
from efren_bot.factory.executor import ExecutorError, ScriptedExecutor
from efren_bot.factory.models import FactoryAdmission, FactoryEffect, FactoryItem, FactoryJob
from efren_bot.factory.service import FactoryError, FactoryService, now

pytestmark = pytest.mark.integration

FACTORY_TABLES = "factory_effects, factory_jobs, factory_admissions, factory_items"


@pytest.fixture
def sessions(pg_engine):
    from efren_bot.db import session_factory

    with pg_engine.begin() as connection:
        assert connection.scalar(text("SELECT current_database()")) == "efren_bot_test"
        connection.execute(text(f"TRUNCATE {FACTORY_TABLES}"))
    return session_factory(pg_engine)


def make(sessions, respond=None, *, gateway=None, ttl=timedelta(hours=24)):
    executor = ScriptedExecutor(respond or (lambda spec: record(spec)))
    gateway = gateway or fx.RecordingGateway()
    service = FactoryService(
        sessions,
        projects=projects(),
        profiles=PROFILES,
        policy=POLICY,
        executor=executor,
        gateway=gateway,
        effect_ttl=ttl,
    )
    return service, executor, gateway


def admit(service, **kw):
    result = service.ingest([item(project_hint="Landing Web", **kw)])[0]
    assert result.decision == "admit", result
    return result


def effects_of(sessions, job_id):
    with sessions() as session:
        rows = session.scalars(select(FactoryEffect).where(FactoryEffect.job_id == job_id)).all()
        return {e.kind: e for e in rows}


def test_ingest_admits_creates_a_job_and_dedupes_the_same_version(sessions):
    service, _, _ = make(sessions)
    first = admit(service)
    again = service.ingest([item(project_hint="Landing Web")])[0]
    assert first.job_id and again.duplicate and again.item_id == first.item_id
    with sessions() as session:
        assert len(session.scalars(select(FactoryJob)).all()) == 1
        admission = session.scalar(select(FactoryAdmission))
        assert admission.decided_by == "policy" and admission.policy_version == POLICY.version


def test_a_changed_version_after_admission_waits_for_a_person(sessions):
    service, _, _ = make(sessions)
    admit(service)
    changed = service.ingest(
        [item(text="Cambiar el botón de la landing a rojo", project_hint="Landing Web")]
    )[0]
    assert changed.decision == "inbox" and changed.job_id is None


def test_discarded_and_context_items_never_get_jobs(sessions):
    service, _, _ = make(sessions)
    results = service.ingest(
        [
            item("slack", "haz algo por favor", human_flagged=False, external_id="s1"),
            item(text="Implementar el reporte mensual de ventas", external_id="n2"),
        ]
    )
    assert [r.decision for r in results] == ["discard", "ask_context"]
    assert all(r.job_id is None for r in results)


def test_passive_run_opens_the_pr_automatically_and_proposes_the_rest_to_a_human(sessions):
    service, executor, gateway = make(sessions)
    job_id = admit(service).job_id
    assert service.process_one() == job_id
    with sessions() as session:
        job = session.get(FactoryJob, job_id)
        assert job.status == "succeeded" and job.run_record["risk"]["tier"] == "passive"
    found = effects_of(sessions, job_id)
    assert found["open_pr"].state == "executed" and found["open_pr"].decided_by == "policy:auto"
    assert found["update_notion"].state == "proposed" and found["update_notion"].policy == "human"
    assert [k for k, _, _ in gateway.executed] == ["open_pr"]
    assert "merge" not in found and "deploy" not in found
    assert executor.calls[0].job_id.endswith("-a1")


def test_a_run_that_needs_a_human_downgrades_auto_effects_to_proposed(sessions):
    service, _, gateway = make(sessions, lambda s: record(s, requires_human=True))
    job_id = admit(service).job_id
    service.process_one()
    assert effects_of(sessions, job_id)["open_pr"].state == "proposed"
    assert gateway.executed == []


def test_forbidden_effects_are_never_even_proposed(sessions):
    def respond(spec):
        return record(spec, effects=[{"kind": "open_pr", "policy": "forbidden"}])

    service, _, _ = make(sessions, respond)
    job_id = admit(service).job_id
    service.process_one()
    assert effects_of(sessions, job_id) == {}


def test_failed_and_blocked_runs_propose_nothing(sessions):
    service, _, _ = make(sessions, lambda s: record(s, status="failed"))
    job_id = admit(service).job_id
    service.process_one()
    with sessions() as session:
        assert session.get(FactoryJob, job_id).status == "failed"
    assert effects_of(sessions, job_id) == {}


def test_executor_errors_retry_with_a_fresh_job_id_then_give_up(sessions):
    calls = []

    def boom(spec):
        calls.append(spec.job_id)
        raise ExecutorError("unit down")

    service, _, _ = make(sessions, boom)
    job_id = admit(service).job_id
    for _ in range(3):
        with sessions.begin() as session:  # skip the exponential backoff
            session.execute(update(FactoryJob).values(available_at=now() - timedelta(seconds=1)))
        service.process_one()
    assert [c.rsplit("-a", 1)[1] for c in calls] == ["1", "2", "3"]  # worktrees are single-use
    with sessions() as session:
        job = session.get(FactoryJob, job_id)
        assert job.status == "failed" and job.error_code == "execution_unit_error"
    assert service.process_one() is None


def test_a_stop_during_a_run_fences_its_late_result_out(sessions):
    holder = {}

    def respond(spec):
        service.control_job(holder["id"], "stop")  # the owner stops it while it runs
        return record(spec)

    service, _, gateway = make(sessions, respond)
    holder["id"] = admit(service).job_id
    service.process_one()
    with sessions() as session:
        assert session.get(FactoryJob, holder["id"]).status == "cancelled"
    assert effects_of(sessions, holder["id"]) == {} and gateway.executed == []


def test_pause_blocks_the_queue_and_continue_releases_it(sessions):
    service, _, _ = make(sessions)
    job_id = admit(service).job_id
    service.control_job(job_id, "pause")
    assert service.process_one() is None
    service.control_job(job_id, "continue")
    assert service.process_one() == job_id


def test_redirect_supersedes_the_job_and_keeps_both_quotes_verbatim(sessions):
    service, _, _ = make(sessions)
    old = admit(service).job_id
    service.control_job(old, "redirect", "Mejor en azul, no en verde")
    with sessions() as session:
        jobs = session.scalars(select(FactoryJob).order_by(FactoryJob.created_at)).all()
    assert [j.status for j in jobs] == ["superseded", "queued"]
    new = jobs[1].spec
    assert (
        "Mejor en azul, no en verde" in new["brief"]
        and new["quotes"][-1] == "Mejor en azul, no en verde"
    )
    with pytest.raises(FactoryError) as excinfo:
        service.control_job(jobs[1].id, "redirect", "  ")
    assert excinfo.value.status == 422


def test_control_rejects_actions_that_do_not_fit_the_state(sessions):
    service, _, _ = make(sessions)
    job_id = admit(service).job_id
    with pytest.raises(FactoryError):
        service.control_job(job_id, "continue")  # not paused
    with pytest.raises(FactoryError) as excinfo:
        service.control_job(uuid4(), "stop")
    assert excinfo.value.status == 404


# ------------------------------------------------------------ human gates


def test_a_person_can_admit_an_inbox_item_into_a_project(sessions):
    service, _, _ = make(sessions)
    sensitive = service.ingest(
        [item(text="Cambiar permisos IAM en producción de la landing", project_hint="Landing Web")]
    )[0]
    assert sensitive.decision == "inbox"
    decided = service.decide_admission(sensitive.item_id, "admit", note="revisado")
    assert decided.job_id is not None
    with sessions() as session:
        rows = session.scalars(
            select(FactoryAdmission).where(FactoryAdmission.item_id == sensitive.item_id)
        ).all()
        assert sorted(r.decided_by for r in rows) == ["human", "policy"]
        assert session.get(FactoryItem, sensitive.item_id).status == "admitted"
    with pytest.raises(FactoryError):
        service.decide_admission(sensitive.item_id, "discard")  # already decided


def test_context_items_need_a_project_choice_and_unknown_ones_are_refused(sessions):
    service, _, _ = make(sessions)
    ctx = service.ingest([item(text="Implementar el reporte mensual de ventas")])[0]
    with pytest.raises(FactoryError) as excinfo:
        service.decide_admission(ctx.item_id, "admit")
    assert excinfo.value.code == "project_required"
    with pytest.raises(FactoryError):
        service.decide_admission(ctx.item_id, "admit", project="ghost")
    assert service.decide_admission(ctx.item_id, "admit", project="etl-lambdas").job_id


def first_human_effect(sessions, service):
    job_id = admit(service).job_id
    service.process_one()
    return job_id, effects_of(sessions, job_id)["update_notion"]


def test_approval_is_recorded_by_the_api_and_performed_once_by_the_worker(sessions):
    service, _, gateway = make(sessions)
    _, effect = first_human_effect(sessions, service)
    done = service.decide_effect(effect.id, "approve", fingerprint=effect.fingerprint, text="ok")
    assert done.state == "approved" and done.decided_by == "owner"
    assert "update_notion" not in [k for k, _, _ in gateway.executed]  # the API never performs it
    assert service.run_approved_effects() == 1
    assert effects_of(sessions, effect.job_id)["update_notion"].state == "executed"
    assert "update_notion" in [k for k, _, _ in gateway.executed]
    assert service.run_approved_effects() == 0
    with pytest.raises(FactoryError) as excinfo:
        service.decide_effect(effect.id, "approve", fingerprint=effect.fingerprint)
    assert excinfo.value.code == "effect_not_pending"  # a second click cannot repeat it


def test_a_wrong_fingerprint_is_refused_and_changes_nothing(sessions):
    service, _, gateway = make(sessions)
    _, effect = first_human_effect(sessions, service)
    with pytest.raises(FactoryError) as excinfo:
        service.decide_effect(effect.id, "approve", fingerprint="0" * 64)
    assert excinfo.value.code == "fingerprint_mismatch"
    assert effects_of(sessions, effect.job_id)["update_notion"].state == "proposed"
    assert "update_notion" not in [k for k, _, _ in gateway.executed]


def test_deny_is_final(sessions):
    service, _, _ = make(sessions)
    _, effect = first_human_effect(sessions, service)
    assert (
        service.decide_effect(effect.id, "deny", fingerprint=effect.fingerprint).state == "denied"
    )
    with pytest.raises(FactoryError):
        service.decide_effect(effect.id, "approve", fingerprint=effect.fingerprint)


def test_an_expired_approval_is_refused_and_the_state_persists(sessions):
    service, _, gateway = make(sessions, ttl=timedelta(seconds=-1))
    job_id = admit(service).job_id
    service.process_one()
    effect = effects_of(sessions, job_id)["update_notion"]
    with pytest.raises(FactoryError) as excinfo:
        service.decide_effect(effect.id, "approve", fingerprint=effect.fingerprint)
    assert excinfo.value.code == "effect_expired"
    assert effects_of(sessions, job_id)["update_notion"].state == "expired"  # not rolled back
    assert gateway.executed == []  # even the auto effect expired before it could run


def test_an_approval_for_an_outdated_run_is_superseded(sessions):
    service, _, gateway = make(sessions)
    old, effect = first_human_effect(sessions, service)
    with sessions.begin() as session:  # a newer run exists for the SAME request
        job = session.get(FactoryJob, old)
        newer = FactoryJob(
            job_key="fj-newer",
            item_id=job.item_id,
            project=job.project,
            spec=job.spec,
            status="queued",
            attempt_count=0,
            available_at=now(),
            control_note="",
            created_at=now() + timedelta(seconds=5),
            updated_at=now(),
        )
        session.add(newer)
    with pytest.raises(FactoryError) as excinfo:
        service.decide_effect(effect.id, "approve", fingerprint=effect.fingerprint)
    assert excinfo.value.code == "effect_superseded"
    assert "update_notion" not in [k for k, _, _ in gateway.executed]


def test_an_uncertain_gateway_outcome_is_never_retried_blindly(sessions):
    class Flaky:
        def execute(self, kind, payload, key):
            raise fx.EffectUncertain("timed out")

    service, _, _ = make(sessions, gateway=Flaky())
    job_id = admit(service).job_id
    service.process_one()
    found = effects_of(sessions, job_id)
    assert found["open_pr"].state == "uncertain"  # auto effect, outcome unknown
    with pytest.raises(FactoryError):
        service.decide_effect(
            found["open_pr"].id, "approve", fingerprint=found["open_pr"].fingerprint
        )


def test_a_definite_gateway_failure_is_recorded_as_failed(sessions):
    service, _, _ = make(sessions, gateway=fx.RecordingGateway(fail_kinds={"open_pr"}))
    job_id = admit(service).job_id
    service.process_one()
    assert effects_of(sessions, job_id)["open_pr"].state == "failed"


def test_reclaim_returns_stale_running_jobs_and_marks_stuck_effects_uncertain(sessions):
    service, _, _ = make(sessions)
    job_id = admit(service).job_id
    service._claim()  # a worker claims it and then vanishes
    with sessions.begin() as session:
        session.execute(update(FactoryJob).values(started_at=now() - timedelta(hours=3)))
    assert service.reclaim_stale() == 1
    with sessions() as session:
        job = session.get(FactoryJob, job_id)
        assert job.status == "queued" and job.error_code == "stale_attempt"
    assert service.process_one() == job_id


def test_stuck_executing_effects_become_uncertain(sessions):
    service, _, _ = make(sessions)
    job_id = admit(service).job_id
    service.process_one()
    effect = effects_of(sessions, job_id)["update_notion"]
    with sessions.begin() as session:
        session.execute(
            update(FactoryEffect)
            .where(FactoryEffect.id == effect.id)
            .values(state="executing", updated_at=now() - timedelta(hours=1))
        )
    assert service.reclaim_stale() == 1
    assert effects_of(sessions, job_id)["update_notion"].state == "uncertain"


def test_expire_effects_only_touches_proposals_past_their_deadline(sessions):
    service, _, _ = make(sessions)
    job_id = admit(service).job_id
    service.process_one()
    assert service.expire_effects() == 0
    with sessions.begin() as session:
        session.execute(update(FactoryEffect).values(expires_at=now() - timedelta(minutes=1)))
    assert service.expire_effects() >= 1
    assert effects_of(sessions, job_id)["update_notion"].state == "expired"


def test_an_approved_effect_that_becomes_stale_before_the_worker_runs_it_is_not_performed(sessions):
    service, _, gateway = make(sessions)
    _, effect = first_human_effect(sessions, service)
    service.decide_effect(effect.id, "approve", fingerprint=effect.fingerprint)
    with sessions.begin() as session:
        session.execute(update(FactoryEffect).values(expires_at=now() - timedelta(minutes=1)))
    assert service.run_approved_effects() == 0
    assert effects_of(sessions, effect.job_id)["update_notion"].state == "expired"
    assert "update_notion" not in [k for k, _, _ in gateway.executed]


def test_an_effect_approved_for_a_newer_run_supersedes_in_flight_work(sessions):
    service, _, gateway = make(sessions)
    old, effect = first_human_effect(sessions, service)
    service.decide_effect(effect.id, "approve", fingerprint=effect.fingerprint)
    with sessions.begin() as session:
        job = session.get(FactoryJob, old)
        session.add(
            FactoryJob(
                job_key="fj-later",
                item_id=job.item_id,
                project=job.project,
                spec=job.spec,
                status="queued",
                attempt_count=0,
                available_at=now(),
                control_note="",
                created_at=now() + timedelta(seconds=5),
                updated_at=now(),
            )
        )
    assert service.run_approved_effects() == 0
    assert effects_of(sessions, old)["update_notion"].state == "superseded"
    assert "update_notion" not in [k for k, _, _ in gateway.executed]


def test_a_manual_submission_goes_through_the_same_criteria(sessions):
    from efren_bot.factory.submit import submit

    service, _, _ = make(sessions)
    ok = submit(service, "Cambiar el botón de la landing a verde", "landing", "m1")
    assert ok["decision"] == "admit" and ok["job_id"] and not ok["duplicate"]
    assert submit(service, "Cambiar el botón de la landing a verde", "landing", "m1")["duplicate"]
    risky = submit(service, "Borrar la tabla de pagos de producción", "landing", "m2")
    assert risky["decision"] == "inbox" and risky["job_id"] is None  # sensitive: a person decides


def test_admission_only_ticks_decide_but_run_and_perform_nothing(sessions):
    from efren_bot.factory.intake import FixtureAdapter
    from efren_bot.factory.worker import tick

    service, executor, gateway = make(sessions)
    adapters = {"fixture": FixtureAdapter([item(project_hint="Landing Web")])}
    out = tick(service, adapters, ["fixture"], admission_only=True)
    assert out["pulled"] == {"fixture": 1} and out["ran"] == 0
    assert executor.calls == [] and gateway.executed == []
    with sessions() as session:
        assert session.scalar(select(FactoryJob.status)) == "queued"
    assert tick(service, adapters, ["fixture"])["ran"] == 1  # a normal tick does run it
