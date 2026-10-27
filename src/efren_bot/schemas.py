import json
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
)

OpaqueID = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=200)]


class DemoEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: OpaqueID
    workspace_id: OpaqueID
    channel_id: OpaqueID
    message_id: OpaqueID
    thread_id: OpaqueID
    actor_id: OpaqueID
    text: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=16000)]
    occurred_at: AwareDatetime
    source_url: Annotated[HttpUrl, Field(max_length=2048)] | None = None

    @field_validator(
        "event_id", "workspace_id", "channel_id", "message_id", "thread_id", "actor_id", "text"
    )
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        if "\x00" in value:
            raise ValueError("NUL characters cannot be persisted")
        return value  # opaque IDs and text are deliberately NOT stripped

    @field_validator("occurred_at", mode="before")
    @classmethod
    def iso_datetime(cls, value):
        if isinstance(value, str):
            try:
                datetime.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("must be an ISO 8601 datetime with timezone") from exc
        elif not isinstance(value, datetime):
            raise ValueError("must be an ISO 8601 datetime with timezone")
        return value

    @field_validator("occurred_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    def canonical_payload(self, *, message: bool = False) -> dict:
        data = self.model_dump(mode="json", exclude={"event_id"} if message else set())
        # A canonical representation, independent of key order / HTTP whitespace.
        return json.loads(json.dumps(data, sort_keys=True, ensure_ascii=False))


class Receipt(BaseModel):
    id: UUID
    status: Literal["accepted", "duplicate"]


class TaskView(BaseModel):
    id: UUID
    title: str
    state: Literal["needs_context", "ready"]
    next_action: str
    source_url: str | None
    source_event_id: UUID
    thread_id: str
    updated_at: AwareDatetime
    has_new_reply: bool


class ActivityView(BaseModel):
    id: UUID
    intent: str
    summary: str
    event_id: UUID
    thread_id: str
    occurred_at: AwareDatetime


class MessageView(BaseModel):
    event_id: UUID
    actor_id: str
    text: str
    occurred_at: AwareDatetime
    source_url: str | None


class TaskDetail(BaseModel):
    task: TaskView
    messages: list[MessageView]


class EventView(BaseModel):
    id: UUID
    provider: Literal["fixture"]
    owner_id: Literal["efren"]
    payload: DemoEventInput
    accepted_at: AwareDatetime


class Counts(BaseModel):
    tasks: int
    needs_context: int
    ready: int
    updates: int
    pending_events: int
    failed_events: int


class Overview(BaseModel):
    mode: Literal["local_demo"] = "local_demo"
    classifier: Literal["deterministic_demo"] = "deterministic_demo"
    database: Literal["ok"] = "ok"
    counts: Counts
    tasks: list[TaskView]
    activities: list[ActivityView]
    integrations: list = Field(default_factory=list)
