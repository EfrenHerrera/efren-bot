from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domain: Literal["support", "review"]
    id: UUID
    request_id: UUID
    revision: int = Field(ge=1, strict=True)
    control_revision: int = Field(ge=0, strict=True)
    action: Literal[
        "attend", "continue", "redirect", "pause", "ignore", "delegate", "stop", "approve", "deny"
    ]
    text: str = Field(default="", max_length=4000)
    proposal_id: UUID | None = None
    fingerprint: str | None = Field(default=None, max_length=64, min_length=64)


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domain: Literal["support", "review"]
    id: UUID
