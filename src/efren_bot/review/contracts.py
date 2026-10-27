from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


Dimension = Literal[
    "architecture",
    "clean_code",
    "data_cost",
    "contracts",
    "business",
    "security",
    "tests",
    "integration",
]


class Detection(Closed):
    requested: bool = Field(strict=True)
    reason: str = Field(min_length=1, max_length=1500)
    context_urls: list[str] = Field(default_factory=list, max_length=50)


class FileRead(Closed):
    item_id: str
    path: str = Field(min_length=1, max_length=500)
    side: Literal["head", "base"] = "head"
    start: int = Field(default=1, ge=1, le=100000, strict=True)
    end: int = Field(default=250, ge=1, le=100000, strict=True)
    reason: str = Field(min_length=1, max_length=800)


class Plan(Closed):
    objective: str = Field(min_length=1, max_length=2000)
    reads: list[FileRead] = Field(max_length=24)
    hypotheses: list[str] = Field(max_length=12)


class Citation(Closed):
    source_id: str
    quote: str = Field(min_length=5, max_length=1000)


class Check(Closed):
    dimension: Dimension
    status: Literal["reviewed", "limited", "not_applicable"]
    conclusion: str = Field(min_length=1, max_length=1800)
    evidence: list[Citation] = Field(max_length=8)


class Finding(Closed):
    dimension: Dimension
    path: str = Field(min_length=1, max_length=500)
    line: int = Field(ge=1, le=1000000, strict=True)
    severity: Literal["high", "medium", "low"]
    confidence: int = Field(ge=80, le=100, strict=True)
    problem: str = Field(min_length=1, max_length=1800)
    scenario: str = Field(min_length=1, max_length=1800)
    impact: str = Field(min_length=1, max_length=1800)
    alternative: str = Field(min_length=1, max_length=1800)
    comment: str = Field(min_length=1, max_length=5000)
    evidence: list[Citation] = Field(min_length=1, max_length=8)


class Previous(Closed):
    discussion_id: str
    assessment: str = Field(min_length=1, max_length=1800)
    status: Literal["addressed_in_code", "accepted_followup", "needs_validation", "still_applies"]
    evidence: list[Citation] = Field(max_length=8)


class Report(Closed):
    summary: str = Field(min_length=1, max_length=3000)
    checks: list[Check] = Field(min_length=8, max_length=8)
    findings: list[Finding] = Field(max_length=12)
    previous: list[Previous] = Field(max_length=40)
    pending: list[str] = Field(max_length=20)


class Answer(Closed):
    text: str = Field(min_length=1, max_length=6000)
    evidence: list[Citation] = Field(max_length=10)


class Selection(Closed):
    id: UUID


class Action(Selection):
    request_id: UUID
    action: Literal["ask", "redirect", "pause", "resume", "discard", "edit", "publish"]
    revision: int = Field(ge=1, strict=True)
    proposal_id: UUID | None = None
    proposal_version: int | None = Field(default=None, ge=1, strict=True)
    text: str = Field(default="", max_length=5000)


class DemoInput(Closed):
    request_id: UUID
