"""Wire contracts shared with ``scraft-ops factory run`` (JobSpec in, RunRecord out)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

JOB_SCHEMA = "scraft.factory.job/1"
RUN_SCHEMA = "scraft.factory.run/1"

ROLES = ("development", "review", "support", "research")
EFFECT_KINDS = ("open_pr", "publish_comment", "update_notion", "post_slack", "merge", "deploy")
Policy = Literal["auto", "human", "forbidden"]
FallbackExecutor = Literal["opencode", "claude"]


class JobSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    ref: str = ""
    url: str = ""


class JobRepo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    base_ref: str


class JobPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allow_worktree: bool = False
    allow_commit: bool = False
    timeout_seconds: int = Field(default=0, ge=0)
    executor: str = ""
    fallback_executors: list[FallbackExecutor] = Field(default_factory=list, max_length=1)
    model: str = ""
    effort: str = ""
    run_review: bool = False

    @model_validator(mode="after")
    def authorized_fallback(self):
        if self.fallback_executors and (
            self.executor not in {"", "opencode", "claude"}
            or self.executor in self.fallback_executors
            or self.model
            or self.effort
        ):
            raise ValueError(
                "fallback requires a different real executor without pinned model/effort"
            )
        return self


class JobMock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    files: dict[str, str] = Field(default_factory=dict)
    fail: bool = False
    review_output: str = ""


class JobSpec(BaseModel):
    """Strict on purpose: the Go side rejects unknown fields too."""

    model_config = ConfigDict(extra="forbid")
    schema_: str = Field(default=JOB_SCHEMA, alias="schema")
    job_id: str
    source: JobSource
    role: Literal["development", "review", "support", "research"]
    profile: str
    repo: JobRepo
    brief: str
    quotes: list[str] = Field(default_factory=list)
    policy: JobPolicy
    mock: JobMock | None = None

    def wire(self) -> dict:
        data = self.model_dump(by_alias=True, exclude_none=True)
        data["schema"] = JOB_SCHEMA
        if not data["policy"]["fallback_executors"]:
            data["policy"].pop("fallback_executors")
        return data


class RunStep(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    detail: str = ""
    log_ref: str = ""


class RunCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    command: list[str] = Field(default_factory=list)
    mandatory: bool = False
    status: str
    exit_code: int = 0
    duration_ms: int = 0
    log_ref: str = ""
    detail: str = ""


class RunRisk(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tier: Literal["passive", "medium", "high"]
    review_mode: str = ""
    reasons: list[str] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    changed_lines: int = 0


class RunReview(BaseModel):
    model_config = ConfigDict(extra="ignore")
    mode: str = ""
    status: str = ""
    verdict: str = ""
    summary: str = ""


class RunEffect(BaseModel):
    model_config = ConfigDict(extra="ignore")
    kind: str
    policy: Policy
    reason: str = ""


class ExecutionAttempt(BaseModel):
    model_config = ConfigDict(extra="ignore")
    executor: str
    phase: str
    status: str
    reason: str = ""
    log_ref: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None


class RunRecord(BaseModel):
    """Tolerant on purpose: new fields from a newer scraft-ops must not break the plant."""

    model_config = ConfigDict(extra="ignore")
    schema_: str = Field(alias="schema")
    job_id: str
    profile: str = ""
    role: str = ""
    status: Literal["succeeded", "failed", "blocked", "timeout"]
    started_at: datetime | None = None
    completed_at: datetime | None = None
    executor: str = ""
    execution_attempts: list[ExecutionAttempt] = Field(default_factory=list)
    branch: str = ""
    worktree: str = ""
    base_ref: str = ""
    head_sha: str = ""
    steps: list[RunStep] = Field(default_factory=list)
    checks: list[RunCheck] = Field(default_factory=list)
    risk: RunRisk | None = None
    review: RunReview | None = None
    requires_human: bool = False
    human_reasons: list[str] = Field(default_factory=list)
    effects: list[RunEffect] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    def valid_schema(self) -> bool:
        return self.schema_ == RUN_SCHEMA

    def effect_policy(self, kind: str) -> Policy:
        for effect in self.effects:
            if effect.kind == kind:
                return effect.policy
        return "forbidden"
