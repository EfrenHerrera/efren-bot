"""The plant: funnel -> admission -> jobs -> run records -> gated effects.

Concurrency model: claims are short transactions (``FOR UPDATE SKIP LOCKED``); the execution
unit runs *outside* any transaction; the result is accepted only if the attempt id still
matches (fencing), so a worker that lost its claim cannot overwrite the successor's result.
Each attempt gets its own execution-unit job id, because worktrees are single-use.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from efren_bot.factory import effects as fx
from efren_bot.factory.contracts import JobPolicy, JobRepo, JobSource, JobSpec, RunRecord
from efren_bot.factory.executor import Executor, ExecutorError
from efren_bot.factory.intake import IntakeItem
from efren_bot.factory.models import (
    FactoryAdmission,
    FactoryEffect,
    FactoryItem,
    FactoryJob,
)
from efren_bot.factory.profiles import ProfileRegistry
from efren_bot.factory.projects import Project, ProjectRegistry
from efren_bot.factory.triage import Admission, AdmissionPolicy, PriorVersion, triage

MAX_ATTEMPTS = 3
STALE_RUNNING = timedelta(hours=2)
STALE_EFFECT = timedelta(minutes=10)


class FactoryError(Exception):
    def __init__(self, code: str, status: int = 409):
        super().__init__(code)
        self.code = code
        self.status = status


def now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class IngestResult:
    item_id: UUID
    external_id: str
    decision: str
    duplicate: bool
    job_id: UUID | None = None


class FactoryService:
    def __init__(
        self,
        sessions: sessionmaker,
        *,
        projects: ProjectRegistry,
        profiles: ProfileRegistry,
        policy: AdmissionPolicy,
        executor: Executor,
        gateway: fx.EffectGateway,
        agent_executor: str = "",
        effect_ttl: timedelta = timedelta(hours=24),
    ):
        self.sessions = sessions
        self.projects = projects
        self.profiles = profiles
        self.policy = policy
        self.executor = executor
        self.gateway = gateway
        self.agent_executor = agent_executor
        self.effect_ttl = effect_ttl

    # ------------------------------------------------------------ intake

    def ingest(self, items: list[IntakeItem]) -> list[IngestResult]:
        return [self._ingest_one(item) for item in items]

    def _ingest_one(self, item: IntakeItem) -> IngestResult:
        fingerprint = item.fingerprint()
        with self.sessions.begin() as session:
            existing = session.scalar(
                select(FactoryItem).where(FactoryItem.fingerprint == fingerprint)
            )
            if existing is not None:
                return IngestResult(existing.id, item.external_id, existing.status, True)
            prior = self._prior_version(session, item)
            row = FactoryItem(
                source_kind=item.source_kind,
                external_id=item.external_id,
                fingerprint=fingerprint,
                title=item.title,
                text=item.text,
                author=item.author,
                url=item.url,
                occurred_at=item.occurred_at,
                attrs=item.attrs,
                status="received",
                created_at=now(),
                updated_at=now(),
            )
            session.add(row)
            try:
                session.flush()
            except IntegrityError:  # lost a race on the same fingerprint
                session.rollback()
                raise
            admission = triage(
                item,
                policy=self.policy,
                projects=self.projects,
                profiles=self.profiles,
                prior=prior,
            )
            job = self._apply(session, row, admission, decided_by="policy", note="")
            return IngestResult(
                row.id, item.external_id, admission.decision, False, job.id if job else None
            )

    def _prior_version(self, session: Session, item: IntakeItem) -> PriorVersion | None:
        earlier = session.scalars(
            select(FactoryItem).where(
                FactoryItem.source_kind == item.source_kind,
                FactoryItem.external_id == item.external_id,
            )
        ).all()
        if not earlier:
            return None
        admitted = any(
            session.scalar(select(FactoryJob.id).where(FactoryJob.item_id == e.id).limit(1))
            for e in earlier
        )
        return PriorVersion(admitted=admitted)

    def _apply(
        self,
        session: Session,
        row: FactoryItem,
        admission: Admission,
        *,
        decided_by: str,
        note: str,
    ) -> FactoryJob | None:
        session.add(
            FactoryAdmission(
                item_id=row.id,
                decision=admission.decision,
                decided_by=decided_by,
                reasons=admission.reasons,
                policy_version=admission.policy_version or self.policy.version,
                project=admission.project,
                profile=admission.profile,
                role=admission.role,
                note=note,
                created_at=now(),
            )
        )
        row.status = {
            "admit": "admitted",
            "ask_context": "needs_context",
            "inbox": "needs_human",
            "discard": "discarded",
        }[admission.decision]
        row.updated_at = now()
        if admission.decision != "admit":
            return None
        project = self.projects.get(admission.project or "")
        if project is None:
            raise FactoryError("unknown_project")
        return self._enqueue(session, row, project, admission.role or "development")

    def _enqueue(
        self, session: Session, row: FactoryItem, project: Project, role: str
    ) -> FactoryJob:
        key = f"fj-{uuid.uuid4().hex[:12]}"
        spec = JobSpec(
            job_id=key,
            source=JobSource(kind=row.source_kind, ref=row.external_id, url=row.url or ""),
            role=role,
            profile=project.profile,
            repo=JobRepo(path=project.repo_path, base_ref=project.base_ref),
            brief=row.text,
            quotes=[row.text],
            policy=JobPolicy(
                allow_worktree=True,
                allow_commit=True,
                run_review=True,
                executor=self.agent_executor or project.executor,
                model=project.model,
                effort=project.effort,
            ),
            mock=row.attrs.get("mock") if self.agent_executor == "fake" else None,
        )
        job = FactoryJob(
            job_key=key,
            item_id=row.id,
            project=project.name,
            spec=spec.wire(),
            status="queued",
            attempt_count=0,
            available_at=now(),
            control_note="",
            created_at=now(),
            updated_at=now(),
        )
        session.add(job)
        session.flush()
        return job

    # ------------------------------------------------- human admission gate

    def decide_admission(
        self, item_id: UUID, action: str, *, project: str | None = None, note: str = ""
    ) -> IngestResult:
        if action not in {"admit", "discard"}:
            raise FactoryError("invalid_action", 422)
        with self.sessions.begin() as session:
            row = session.get(FactoryItem, item_id, with_for_update=True)
            if row is None:
                raise FactoryError("item_not_found", 404)
            if row.status not in {"needs_human", "needs_context"}:
                raise FactoryError("item_not_awaiting_decision")
            if action == "discard":
                admission = Admission("discard", ["discarded by a person"], policy_version="human")
                self._apply(session, row, admission, decided_by="human", note=note)
                return IngestResult(row.id, row.external_id, "discard", False)
            last = session.scalar(
                select(FactoryAdmission)
                .where(FactoryAdmission.item_id == row.id)
                .order_by(FactoryAdmission.created_at.desc())
                .limit(1)
            )
            name = project or (last.project if last else None)
            chosen = self.projects.get(name or "")
            if chosen is None:
                raise FactoryError("project_required", 422)
            role = (last.role if last and last.role else None) or "development"
            admission = Admission(
                "admit",
                [f"admitted by a person for project {chosen.name!r}"],
                project=chosen.name,
                profile=chosen.profile,
                role=role,
                policy_version="human",
            )
            job = self._apply(session, row, admission, decided_by="human", note=note)
            return IngestResult(row.id, row.external_id, "admit", False, job.id if job else None)

    # ------------------------------------------------------------ jobs

    def process_one(self) -> UUID | None:
        """Claim and run one queued job. Returns its id, or None when idle."""
        claimed = self._claim()
        if claimed is None:
            return None
        job_id, attempt_id, spec = claimed
        try:
            record = self.executor.run(spec)
            error = None
        except ExecutorError as exc:
            record, error = None, str(exc)
        for effect_id in self._finish(job_id, attempt_id, record, error):
            self._dispatch(effect_id, decided_by="policy:auto")
        return job_id

    def _claim(self) -> tuple[UUID, UUID, JobSpec] | None:
        with self.sessions.begin() as session:
            job = session.scalar(
                select(FactoryJob)
                .where(FactoryJob.status == "queued", FactoryJob.available_at <= now())
                .order_by(FactoryJob.available_at, FactoryJob.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if job is None:
                return None
            job.status = "running"
            job.attempt_id = uuid.uuid4()
            job.attempt_count += 1
            job.started_at = now()
            job.updated_at = now()
            spec = JobSpec.model_validate(
                {**job.spec, "job_id": f"{job.job_key}-a{job.attempt_count}"}
            )
            return job.id, job.attempt_id, spec

    def _finish(
        self, job_id: UUID, attempt_id: UUID, record: RunRecord | None, error: str | None
    ) -> list[UUID]:
        """Store the result; return the auto effects to dispatch AFTER this commit."""
        with self.sessions.begin() as session:
            job = session.get(FactoryJob, job_id, with_for_update=True)
            if job is None or job.attempt_id != attempt_id or job.status != "running":
                return []  # fenced: someone else owns this job now (stopped, reclaimed, redirected)
            job.finished_at = now()
            job.updated_at = now()
            if record is None:
                job.error_code = "execution_unit_error"
                job.status = "failed" if job.attempt_count >= MAX_ATTEMPTS else "queued"
                job.available_at = now() + timedelta(seconds=2**job.attempt_count)
                job.run_record = {"error": error}
                return []
            job.run_record = record.model_dump(mode="json", by_alias=True)
            job.status = {
                "succeeded": "succeeded",
                "failed": "failed",
                "blocked": "blocked",
                "timeout": "failed",
            }[record.status]
            job.error_code = None if record.status == "succeeded" else record.status
            return self._propose_effects(session, job, record)

    def _propose_effects(self, session: Session, job: FactoryJob, record: RunRecord) -> list[UUID]:
        item = session.get(FactoryItem, job.item_id)
        project = self.projects.get(job.project)
        built = fx.build_effects(
            record,
            source_kind=item.source_kind,
            source_ref=item.external_id,
            brief=item.text,
            job_key=job.job_key,
            repo_path=project.repo_path if project else "",
        )
        auto: list[UUID] = []
        for kind, payload in built:
            policy = record.effect_policy(kind)
            if policy == "forbidden":
                continue  # never even proposed
            if record.requires_human and policy == "auto":
                policy = "human"
            row = FactoryEffect(
                job_id=job.id,
                kind=kind,
                policy=policy,
                state="proposed",
                payload=payload,
                fingerprint=fx.fingerprint(kind, payload),
                expires_at=now() + self.effect_ttl,
                decision_text="",
                created_at=now(),
                updated_at=now(),
            )
            session.add(row)
            session.flush()
            if policy == "auto":
                auto.append(row.id)
        return auto

    def reclaim_stale(self) -> int:
        """Return running jobs whose worker vanished to the queue (bounded by MAX_ATTEMPTS)."""
        cutoff = now() - STALE_RUNNING
        with self.sessions.begin() as session:
            stale = session.scalars(
                select(FactoryJob)
                .where(FactoryJob.status == "running", FactoryJob.started_at < cutoff)
                .with_for_update(skip_locked=True)
            ).all()
            for job in stale:
                job.attempt_id = None
                job.status = "failed" if job.attempt_count >= MAX_ATTEMPTS else "queued"
                job.error_code = "stale_attempt"
                job.updated_at = now()
            stuck = session.scalars(
                select(FactoryEffect)
                .where(
                    FactoryEffect.state == "executing",
                    FactoryEffect.updated_at < now() - STALE_EFFECT,
                )
                .with_for_update(skip_locked=True)
            ).all()
            for effect in stuck:  # outcome unknowable: a person reconciles, never a blind retry
                effect.state = "uncertain"
                effect.result = {"error": "worker vanished while executing"}
                effect.updated_at = now()
            return len(stale) + len(stuck)

    # ------------------------------------------------- human job control

    def control_job(self, job_id: UUID, action: str, text: str = "") -> None:
        """continue / pause / stop / redirect, mirroring the inbox verbs."""
        if action not in {"pause", "continue", "stop", "redirect"}:
            raise FactoryError("invalid_action", 422)
        with self.sessions.begin() as session:
            job = session.get(FactoryJob, job_id, with_for_update=True)
            if job is None:
                raise FactoryError("job_not_found", 404)
            if action == "pause" and job.status == "queued":
                job.status = "paused"
            elif action == "continue" and job.status == "paused":
                job.status = "queued"
                job.available_at = now()
            elif action == "stop" and job.status in {"queued", "paused", "running"}:
                job.status = "cancelled"
                job.attempt_id = None  # fences a running attempt out
            elif action == "redirect" and job.status in {"queued", "paused", "running"}:
                if not text.strip():
                    raise FactoryError("redirect_needs_text", 422)
                self._redirect(session, job, text)
            else:
                raise FactoryError("invalid_state_for_action")
            job.control_note = (job.control_note + f"\n[{action}] {text}").strip()
            job.updated_at = now()

    def _redirect(self, session: Session, job: FactoryJob, text: str) -> None:
        item = session.get(FactoryItem, job.item_id)
        project = self.projects.get(job.project)
        if project is None:
            raise FactoryError("unknown_project")
        job.status = "superseded"
        job.attempt_id = None
        new = self._enqueue(session, item, project, job.spec["role"])
        spec = dict(new.spec)
        spec["brief"] = f"{item.text}\n\nCorrection from the owner, verbatim: {text}"
        spec["quotes"] = [item.text, text]
        new.spec = spec

    # ------------------------------------------------------------ effects

    def decide_effect(
        self,
        effect_id: UUID,
        action: str,
        *,
        fingerprint: str,
        decided_by: str = "owner",
        text: str = "",
    ) -> FactoryEffect:
        """Approve or deny one exact payload. A stale or altered one is refused."""
        if action not in {"approve", "deny"}:
            raise FactoryError("invalid_action", 422)
        refusal: str | None = None
        with self.sessions.begin() as session:
            effect = session.get(FactoryEffect, effect_id, with_for_update=True)
            if effect is None:
                raise FactoryError("effect_not_found", 404)
            if effect.state != "proposed":
                raise FactoryError("effect_not_pending")
            if effect.fingerprint != fingerprint:
                raise FactoryError("fingerprint_mismatch")
            effect.decided_by, effect.decided_at, effect.decision_text = decided_by, now(), text
            effect.updated_at = now()
            if action == "deny":
                effect.state = "denied"
            else:
                refusal = self._stale_reason(session, effect)
                # The API only records the decision. A host worker performs approved effects:
                # credentials and git access never live in the web-facing process.
                effect.state = {"effect_expired": "expired", "effect_superseded": "superseded"}.get(
                    refusal or "", "approved"
                )
        if refusal:  # raised after the commit so the new state persists
            raise FactoryError(refusal)
        return self._load_effect(effect_id)

    def _stale_reason(self, session: Session, effect: FactoryEffect) -> str | None:
        if effect.expires_at <= now():
            return "effect_expired"
        job = session.get(FactoryJob, effect.job_id)
        if job.status != "succeeded" or self._newer_run_exists(session, job):
            return "effect_superseded"
        return None

    def run_approved_effects(self, limit: int = 20) -> int:
        """Host-worker step: perform effects a person approved, re-checking vigency first."""
        done = 0
        for _ in range(limit):
            with self.sessions.begin() as session:
                effect = session.scalar(
                    select(FactoryEffect)
                    .where(FactoryEffect.state == "approved")
                    .order_by(FactoryEffect.decided_at)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
                if effect is None:
                    return done
                stale = self._stale_reason(session, effect)
                if stale:
                    effect.state = "expired" if stale == "effect_expired" else "superseded"
                    effect.updated_at = now()
                    continue
                effect.state, effect.updated_at = "executing", now()
                effect_id = effect.id
            self._run_effect(effect_id)
            done += 1
        return done

    def _newer_run_exists(self, session: Session, job: FactoryJob) -> bool:
        return (
            session.scalar(
                select(FactoryJob.id).where(
                    FactoryJob.item_id == job.item_id,
                    FactoryJob.created_at > job.created_at,
                    FactoryJob.status.notin_(["cancelled"]),
                )
            )
            is not None
        )

    def _load_effect(self, effect_id: UUID) -> FactoryEffect:
        with self.sessions() as session:
            return session.get(FactoryEffect, effect_id)

    def _dispatch(self, effect_id: UUID, *, decided_by: str) -> None:
        """Claim a proposed effect (auto policy) and run it, never inside a transaction."""
        with self.sessions.begin() as session:
            effect = session.get(FactoryEffect, effect_id, with_for_update=True)
            if effect is None or effect.state != "proposed":
                return
            if effect.expires_at <= now():
                effect.state = "expired"
                return
            effect.state, effect.decided_by, effect.decided_at = "executing", decided_by, now()
            effect.updated_at = now()
        self._run_effect(effect_id)

    def _run_effect(self, effect_id: UUID) -> FactoryEffect:
        """Phase 2 and 3: call the gateway outside any transaction, then record the outcome."""
        with self.sessions() as session:
            effect = session.get(FactoryEffect, effect_id)
            kind, payload = effect.kind, dict(effect.payload)
        try:
            result, state = self.gateway.execute(kind, payload, str(effect_id)), "executed"
        except fx.EffectUncertain as exc:
            result, state = {"error": str(exc)}, "uncertain"
        except fx.EffectFailed as exc:
            result, state = {"error": str(exc)}, "failed"
        except Exception as exc:  # noqa: BLE001 - an unknown outcome is uncertain, not failed
            result, state = {"error": type(exc).__name__}, "uncertain"
        with self.sessions.begin() as session:
            effect = session.get(FactoryEffect, effect_id, with_for_update=True)
            if effect.state == "executing":
                effect.state, effect.result, effect.updated_at = state, result, now()
        return self._load_effect(effect_id)

    def expire_effects(self) -> int:
        with self.sessions.begin() as session:
            result = session.execute(
                update(FactoryEffect)
                .where(FactoryEffect.state == "proposed", FactoryEffect.expires_at <= now())
                .values(state="expired", updated_at=now())
            )
            return result.rowcount or 0
