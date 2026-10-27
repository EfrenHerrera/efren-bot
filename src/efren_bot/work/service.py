"""Short PostgreSQL transactions only. No network, commands, models or source fetches."""

import hashlib
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from efren_bot.bridge.contracts import canonical
from efren_bot.config import OWNER_ID
from efren_bot.fixtures import demo_fixtures
from efren_bot.models import WorkApproval, WorkArtifact, WorkHistory, WorkItem, WorkJob, utcnow
from efren_bot.schemas import DemoEventInput
from efren_bot.work.contracts import (
    ApprovalView,
    ArtifactContent,
    ArtifactView,
    Check,
    Checkpoint,
    CreateReceipt,
    CreateWork,
    Decision,
    DecisionReceipt,
    HistoryData,
    HistoryView,
    JobView,
    WorkDetail,
    WorkSummary,
    WorkView,
)


class WorkError(Exception):
    def __init__(self, status: int, code: str):
        self.status = status
        self.code = code
        super().__init__(code)


class InvalidState(Exception):
    """Fail closed with a fixed error code, never exception text or SQL."""


def digest(data: dict) -> str:
    # Existing canonical JSON helper + standard hashlib, not authentication/signing.
    return hashlib.sha256(canonical(data)).hexdigest()


def source() -> dict:
    return next(f.event.canonical_payload() for f in demo_fixtures() if f.id == "request_video")


def check(name: str, status: str, detail: str) -> Check:
    return Check(name=name, status=status, detail=detail)


def content(source_sha256: str, *, final: bool = False) -> ArtifactContent:
    return ArtifactContent(
        title="Simulación local completada" if final else "Pedir contexto del video (sintético)",
        summary=(
            "Se registró una entrega sintética local. "
            "No se subió ningún video ni se cerró la fuente."
            if final
            else "ASK_CONTEXT: pedir qué video debe subirse y a qué destino. No publicar."
        ),
        action="SIMULATION_COMPLETE" if final else "ASK_CONTEXT",
        missing_context=["Qué video", "Destino de publicación"],
        checks=[
            check(
                "canonical_fixture", "passed", "Snapshot y digest coinciden con request_video v1."
            ),
            check("external_publication", "not_run", "Sin conector ni publicación externa."),
            check("real_tests", "not_run", "Este ejecutor no ejecuta pruebas ni comandos."),
        ],
        pending=["Obtener contexto real fuera de esta simulación", "No cerrar la fuente"],
        source_sha256=source_sha256,
    )


def history(
    session: Session,
    job: WorkJob,
    kind: str,
    reason: str,
    *,
    attempt_id: UUID | None = None,
    artifact_id: UUID | None = None,
    approval_id: UUID | None = None,
    error_code: str | None = None,
) -> None:
    # All callers own the job lock (or its uncommitted insertion).
    sequence = 1 + (
        session.scalar(select(func.max(WorkHistory.sequence)).where(WorkHistory.job_id == job.id))
        or 0
    )
    data = HistoryData(
        reason=reason,
        alternatives=["No ejecutar efectos externos", "Conservar la fuente sin cerrar"],
        checks=[
            check(
                "local_step",
                "failed" if error_code else "passed",
                "Paso revertido; sin efectos parciales."
                if error_code
                else "Paso DB local registrado.",
            )
        ],
        pending=["Publicación externa no implementada", "Identidad humana no autenticada"],
        source_sha256=digest(source()),
        artifact_id=artifact_id,
        approval_id=approval_id,
        error_code=error_code,
    )
    session.add(
        WorkHistory(
            id=uuid4(),
            job_id=job.id,
            sequence=sequence,
            kind=kind,
            actor_id=OWNER_ID,
            occurred_at=utcnow(),
            attempt_id=attempt_id,
            attempt_number=job.attempt_count if attempt_id else None,
            data=data.model_dump(mode="json"),
        )
    )
    # Attempt exists before the artifact FK is flushed; failure rolls both back.
    session.flush()


def summary(work: WorkItem, job: WorkJob) -> WorkSummary:
    return WorkSummary(
        id=work.id,
        fixture_id=work.fixture_id,
        recipe_version=work.recipe_version,
        owner_id=work.owner_id,
        state=work.state,
        job_status=job.status,
        created_at=work.created_at,
        updated_at=work.updated_at,
    )


def detail(session: Session, work_id: UUID) -> WorkDetail:
    work = session.get(WorkItem, work_id)
    if work is None:
        raise WorkError(404, "work_not_found")
    job = session.scalar(select(WorkJob).where(WorkJob.work_id == work_id))
    return WorkDetail(
        work=WorkView(
            **summary(work, job).model_dump(),
            source_snapshot=work.source_snapshot,
            source_sha256=work.source_sha256,
        ),
        job=JobView.model_validate(job),
        history=[
            HistoryView.model_validate(row)
            for row in session.scalars(
                select(WorkHistory)
                .where(WorkHistory.job_id == job.id)
                .order_by(WorkHistory.sequence)
            )
        ],
        artifacts=[
            ArtifactView.model_validate(row)
            for row in session.scalars(
                select(WorkArtifact)
                .where(WorkArtifact.job_id == job.id)
                .order_by(WorkArtifact.version)
            )
        ],
        approvals=[
            ApprovalView.model_validate(row)
            for row in session.scalars(
                select(WorkApproval)
                .where(WorkApproval.job_id == job.id)
                .order_by(WorkApproval.created_at, WorkApproval.id)
            )
        ],
    )


def replay(session: Session, work: WorkItem, data: CreateWork) -> CreateReceipt:
    # Lookup may predate a worker commit at READ COMMITTED. Serialize on the job
    # first, then refresh the identity-mapped work while that lock stabilizes all
    # dependent detail reads (the same job-first order as decisions and worker).
    job = session.scalar(
        select(WorkJob)
        .where(WorkJob.work_id == work.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if job is None:
        raise WorkError(409, "state_invalid")
    session.refresh(work)
    if work.fixture_id != data.fixture_id:
        raise WorkError(409, "idempotency_conflict")
    return CreateReceipt(status="duplicate", detail=detail(session, work.id))


def create(sessions: sessionmaker, data: CreateWork) -> CreateReceipt:
    with sessions.begin() as session:
        existing = session.scalar(
            select(WorkItem).where(WorkItem.idempotency_key == data.idempotency_key)
        )
        if existing is not None:
            return replay(session, existing, data)
        if data.fixture_id != "request_video":
            raise WorkError(422, "unsupported_recipe")
        snapshot = source()
        now = utcnow()
        work_id = session.scalar(
            insert(WorkItem)
            .values(
                id=uuid4(),
                idempotency_key=data.idempotency_key,
                fixture_id=data.fixture_id,
                recipe_version=1,
                owner_id=OWNER_ID,
                state="active",
                source_snapshot=snapshot,
                source_sha256=digest(snapshot),
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=[WorkItem.idempotency_key])
            .returning(WorkItem.id)
        )
        if work_id is None:
            existing = session.scalar(
                select(WorkItem).where(WorkItem.idempotency_key == data.idempotency_key)
            )
            return replay(session, existing, data)
        job = WorkJob(
            id=uuid4(),
            work_id=work_id,
            status="queued",
            attempt_count=0,
            failure_count=0,
            available_at=now,
            last_error_code=None,
            checkpoint=Checkpoint(
                phase="prepare", source_sha256=digest(snapshot), next_action="run_prepare"
            ).model_dump(mode="json"),
        )
        session.add(job)
        session.flush()
        history(
            session, job, "work_created", "Solicitud explícita de simulación con fixture canónico."
        )
        return CreateReceipt(status="accepted", detail=detail(session, work_id))


def validate_source(work: WorkItem) -> None:
    expected = source()
    if (
        work.fixture_id != "request_video"
        or work.recipe_version != 1
        or work.owner_id != OWNER_ID
        or DemoEventInput.model_validate(work.source_snapshot).canonical_payload() != expected
        or work.source_snapshot != expected
        or work.source_sha256 != digest(expected)
    ):
        raise InvalidState()


def validate_checkpoint(work: WorkItem, job: WorkJob, phase: str) -> Checkpoint:
    validate_source(work)
    cp = Checkpoint.model_validate(job.checkpoint)
    action = {
        "prepare": "run_prepare",
        "await_approval": "human_decision",
        "finalize": "run_finalize",
    }[phase]
    if (
        cp.phase != phase
        or cp.next_action != action
        or cp.source_sha256 != work.source_sha256
        or cp.final_artifact_id is not None
    ):
        raise InvalidState()
    if phase == "prepare":
        if cp.proposal_artifact_id is not None or cp.approval_id is not None:
            raise InvalidState()
    elif cp.proposal_artifact_id is None or cp.approval_id is None:
        raise InvalidState()
    return cp


def validate_proposal(session: Session, job: WorkJob, cp: Checkpoint) -> WorkApproval:
    artifact = session.get(WorkArtifact, cp.proposal_artifact_id)
    approval = session.get(WorkApproval, cp.approval_id)
    expected = content(cp.source_sha256).model_dump(mode="json")
    if (
        artifact is None
        or approval is None
        or artifact.job_id != job.id
        or approval.job_id != job.id
        or approval.artifact_id != artifact.id
        or artifact.kind != "proposal"
        or artifact.version != 1
        or artifact.content != expected
        or artifact.sha256 != digest(expected)
        or approval.artifact_sha256 != artifact.sha256
    ):
        raise InvalidState()
    return approval


def decide(
    sessions: sessionmaker, work_id: UUID, approval_id: UUID, data: Decision
) -> DecisionReceipt:
    with sessions.begin() as session:
        # Same lock order as worker: job first, then work/artifact/approval.
        job = session.scalar(select(WorkJob).where(WorkJob.work_id == work_id).with_for_update())
        if job is None:
            raise WorkError(404, "work_not_found")
        approval = session.scalar(
            select(WorkApproval).where(
                WorkApproval.id == approval_id, WorkApproval.job_id == job.id
            )
        )
        if approval is None:
            raise WorkError(404, "approval_not_found")
        wanted = "approved" if data.decision == "approve" else "rejected"
        if approval.artifact_sha256 != data.artifact_sha256:
            raise WorkError(409, "approval_conflict")
        if approval.status != "pending":
            if approval.status != wanted or approval.decision_reason != data.reason:
                raise WorkError(409, "approval_conflict")
            return DecisionReceipt(status="duplicate", detail=detail(session, work_id))
        work = session.get(WorkItem, work_id)
        try:
            cp = validate_checkpoint(work, job, "await_approval")
            if (
                job.status != "waiting_human"
                or work.state != "waiting"
                or cp.approval_id != approval.id
                or validate_proposal(session, job, cp).id != approval.id
            ):
                raise InvalidState()
        except (ValueError, InvalidState) as exc:
            raise WorkError(409, "state_invalid") from exc
        approval.status = wanted
        approval.decision_reason = data.reason  # exact: whitespace is not silently normalized
        approval.decided_by = OWNER_ID  # demo actor, NOT authenticated human identity
        approval.decided_at = utcnow()
        approved = wanted == "approved"
        job.status = "queued" if approved else "failed"
        job.last_error_code = None if approved else "approval_rejected"
        job.available_at = utcnow()
        cp.phase = "finalize" if approved else "rejected"
        cp.next_action = "run_finalize" if approved else "none"
        job.checkpoint = cp.model_dump(mode="json")
        work.state = "active" if approved else "waiting"
        work.updated_at = utcnow()
        history(
            session,
            job,
            "approval_recorded",
            data.reason,
            artifact_id=approval.artifact_id,
            approval_id=approval.id,
        )
        return DecisionReceipt(status="recorded", detail=detail(session, work_id))


def execute_step(session: Session, job: WorkJob, work: WorkItem, attempt_id: UUID) -> None:
    """The entire fake executor: fixed data + DB inserts under caller's savepoint."""
    phase = job.checkpoint.get("phase") if isinstance(job.checkpoint, dict) else None
    if phase not in {"prepare", "finalize"}:
        raise InvalidState()
    cp = validate_checkpoint(work, job, phase)
    if work.state != "active":
        raise InvalidState()
    final = phase == "finalize"
    if final:
        approval = validate_proposal(session, job, cp)
        if (
            approval.status != "approved"
            or approval.decided_by != OWNER_ID
            or approval.decided_at is None
            or not approval.decision_reason
        ):
            raise InvalidState()
        Decision(
            decision="approve",
            artifact_sha256=approval.artifact_sha256,
            reason=approval.decision_reason,
        )
    elif session.scalar(select(WorkArtifact.id).where(WorkArtifact.job_id == job.id)) is not None:
        raise InvalidState()
    artifact_id, approval_id = uuid4(), cp.approval_id if final else uuid4()
    payload = content(work.source_sha256, final=final).model_dump(mode="json")
    history(
        session,
        job,
        "simulation_finished" if final else "proposal_prepared",
        "Entrega sintética DB local; fuente sin cerrar."
        if final
        else "Falta contexto: propuesta ASK_CONTEXT, esperar decisión simulada.",
        attempt_id=attempt_id,
        artifact_id=artifact_id,
        approval_id=approval_id,
    )
    session.add(
        WorkArtifact(
            id=artifact_id,
            job_id=job.id,
            attempt_id=attempt_id,
            version=2 if final else 1,
            kind="result" if final else "proposal",
            content=payload,
            sha256=digest(payload),
            created_at=utcnow(),
        )
    )
    session.flush()
    if final:
        cp.final_artifact_id = artifact_id
        cp.phase, cp.next_action = "complete", "none"
        job.status, work.state = "succeeded", "delivered"
    else:
        session.add(
            WorkApproval(
                id=approval_id,
                job_id=job.id,
                artifact_id=artifact_id,
                artifact_sha256=digest(payload),
                status="pending",
                decision_reason=None,
                decided_by=None,
                created_at=utcnow(),
                decided_at=None,
            )
        )
        session.flush()
        cp.proposal_artifact_id, cp.approval_id = artifact_id, approval_id
        cp.phase, cp.next_action = "await_approval", "human_decision"
        job.status, work.state = "waiting_human", "waiting"
    job.checkpoint = cp.model_dump(mode="json")
    job.last_error_code = None
    work.updated_at = utcnow()
    session.flush()
