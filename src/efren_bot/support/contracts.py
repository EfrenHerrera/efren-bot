from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Classification(Closed):
    action: Literal["support", "ignore", "uncertain"]
    title: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=1200)
    evidence_ids: list[str] = Field(max_length=30)


class Report(Closed):
    reported: list[str] = Field(max_length=12)
    hypotheses: list[str] = Field(max_length=12)
    missing: list[str] = Field(max_length=12)
    evidence_ids: list[str] = Field(max_length=50)
    slack_draft: str = Field(min_length=1, max_length=6000)

    @field_validator("reported", "hypotheses", "missing")
    @classmethod
    def bounded(cls, values):
        if any(not text.strip() or len(text) > 1500 for text in values):
            raise ValueError("invalid report text")
        return values


class Answer(Closed):
    text: str = Field(min_length=1, max_length=6000)
    evidence_ids: list[str] = Field(max_length=50)


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID


class CaseAction(Selection):
    request_id: UUID
    action: Literal["ask", "redirect", "pause", "resume", "dismiss"]
    text: str = Field(default="", max_length=4000)

    @field_validator("text")
    @classmethod
    def clean(cls, value):
        if "\x00" in value:
            raise ValueError("invalid text")
        return value.strip()
