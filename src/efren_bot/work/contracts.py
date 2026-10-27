"""Frozen, closed wire DTOs for synthetic work (not the platform DRAFT)."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

from efren_bot.schemas import DemoEventInput

Digest = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")]
JobStatus = Literal["queued", "waiting_human", "succeeded", "failed"]


def valid_reason(value: str) -> str:
    if not value.strip() or "\x00" in value:
        raise ValueError("reason must be nonblank without NUL")
    value.encode("utf-8")
    return value


Reason = Annotated[
    str, StringConstraints(strict=True, min_length=1, max_length=500), AfterValidator(valid_reason)
]


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class CreateWork(Closed):
    idempotency_key: UUID
    fixture_id: Literal["request_video", "thanks", "reply"]


class Decision(Closed):
    decision: Literal["approve", "reject"]
    artifact_sha256: Digest
    reason: Reason


class Check(Closed):
    name: str
    status: Literal["passed", "failed", "not_run"]
    detail: str


class Checkpoint(Closed):
    version: Literal[1] = 1
    phase: Literal["prepare", "await_approval", "finalize", "complete", "rejected", "failed"]
    source_sha256: Digest
    proposal_artifact_id: UUID | None = None
    approval_id: UUID | None = None
    final_artifact_id: UUID | None = None
    next_action: Literal["run_prepare", "human_decision", "run_finalize", "none"]

    @field_validator("version", mode="before")
    @classmethod
    def exact_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("unsupported checkpoint version")
        return value


class HistoryData(Closed):
    reason: str
    alternatives: list[str]
    checks: list[Check]
    pending: list[str]
    source_fixture_id: Literal["request_video"] = "request_video"
    source_sha256: Digest
    artifact_id: UUID | None = None
    approval_id: UUID | None = None
    error_code: str | None = None


class ArtifactContent(Closed):
    title: str
    summary: str
    action: Literal["ASK_CONTEXT", "SIMULATION_COMPLETE"]
    missing_context: list[str]
    checks: list[Check]
    pending: list[str]
    source_fixture_id: Literal["request_video"] = "request_video"
    source_sha256: Digest
    no_external_effects: Literal[True] = True


class WorkSummary(Closed):
    id: UUID
    fixture_id: Literal["request_video"]
    recipe_version: Literal[1]
    owner_id: Literal["efren"]
    state: Literal["active", "waiting", "delivered"]
    job_status: JobStatus
    created_at: AwareDatetime
    updated_at: AwareDatetime


class WorkView(WorkSummary):
    source_snapshot: DemoEventInput
    source_sha256: Digest


class JobView(Closed):
    id: UUID
    work_id: UUID
    status: JobStatus
    checkpoint: Checkpoint
    attempt_count: Annotated[int, Field(ge=0)]
    failure_count: Annotated[int, Field(ge=0, le=5)]
    available_at: AwareDatetime
    last_error_code: str | None


class HistoryView(Closed):
    id: UUID
    sequence: Annotated[int, Field(gt=0)]
    kind: Literal[
        "work_created",
        "proposal_prepared",
        "approval_recorded",
        "simulation_finished",
        "attempt_failed",
    ]
    actor_id: Literal["efren"]
    occurred_at: AwareDatetime
    attempt_id: UUID | None
    attempt_number: Annotated[int, Field(gt=0)] | None
    data: HistoryData


class ArtifactView(Closed):
    id: UUID
    job_id: UUID
    attempt_id: UUID
    version: Annotated[int, Field(gt=0)]
    kind: Literal["proposal", "result"]
    content: ArtifactContent
    sha256: Digest
    created_at: AwareDatetime


class ApprovalView(Closed):
    id: UUID
    job_id: UUID
    artifact_id: UUID
    artifact_sha256: Digest
    status: Literal["pending", "approved", "rejected"]
    decision_reason: Reason | None
    decided_by: Literal["efren"] | None
    created_at: AwareDatetime
    decided_at: AwareDatetime | None


class WorkDetail(Closed):
    work: WorkView
    job: JobView
    history: list[HistoryView]
    artifacts: list[ArtifactView]
    approvals: list[ApprovalView]


class WorkList(Closed):
    mode: Literal["synthetic_work"] = "synthetic_work"
    executor: Literal["fake_db_v1"] = "fake_db_v1"
    works: list[WorkSummary]


class CreateReceipt(Closed):
    status: Literal["accepted", "duplicate"]
    detail: WorkDetail


class DecisionReceipt(Closed):
    status: Literal["recorded", "duplicate"]
    detail: WorkDetail
