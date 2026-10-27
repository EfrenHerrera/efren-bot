from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Thread(Base):
    __tablename__ = "threads"
    __table_args__ = (
        UniqueConstraint("provider", "workspace_id", "channel_id", "thread_id", name="uq_thread"),
        CheckConstraint("provider = 'fixture'", name="ck_thread_provider"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(20))
    workspace_id: Mapped[str] = mapped_column(String(200))
    channel_id: Mapped[str] = mapped_column(String(200))
    thread_id: Mapped[str] = mapped_column(String(200))


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("provider", "workspace_id", "channel_id", "message_id", name="uq_message"),
        CheckConstraint("provider = 'fixture'", name="ck_message_provider"),
        Index("ix_messages_thread", "thread_pk", "occurred_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(20))
    workspace_id: Mapped[str] = mapped_column(String(200))
    channel_id: Mapped[str] = mapped_column(String(200))
    message_id: Mapped[str] = mapped_column(String(200))
    thread_pk: Mapped[UUID] = mapped_column(ForeignKey("threads.id"))
    canonical_event_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "events.id",
            name="fk_message_canonical_event",
            use_alter=True,
            deferrable=True,
            initially="DEFERRED",
        ),
        unique=True,
    )
    payload: Mapped[dict] = mapped_column(JSONB)
    actor_id: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_url: Mapped[str | None] = mapped_column(String(2048))


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("provider", "workspace_id", "channel_id", "event_id", name="uq_event"),
        CheckConstraint("provider = 'fixture'", name="ck_event_provider"),
        CheckConstraint("owner_id = 'efren'", name="ck_event_owner"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(20))
    owner_id: Mapped[str] = mapped_column(String(200))
    workspace_id: Mapped[str] = mapped_column(String(200))
    channel_id: Mapped[str] = mapped_column(String(200))
    event_id: Mapped[str] = mapped_column(String(200))
    message_pk: Mapped[UUID] = mapped_column(ForeignKey("messages.id"))
    payload: Mapped[dict] = mapped_column(JSONB)
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )


class Outbox(Base):
    __tablename__ = "outbox"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'processed', 'failed')", name="ck_outbox_status"),
        CheckConstraint("attempts BETWEEN 0 AND 5", name="ck_outbox_attempts"),
        Index("ix_outbox_poll", "status", "available_at", "created_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(ForeignKey("events.id"), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(200))


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (CheckConstraint("state IN ('needs_context', 'ready')", name="ck_task_state"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_message_id: Mapped[UUID] = mapped_column(ForeignKey("messages.id"), unique=True)
    source_event_id: Mapped[UUID] = mapped_column(ForeignKey("events.id"), unique=True)
    thread_pk: Mapped[UUID] = mapped_column(ForeignKey("threads.id"), index=True)
    title: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(20))
    next_action: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    has_new_reply: Mapped[bool] = mapped_column(default=False, server_default="false")


class Activity(Base):
    __tablename__ = "activities"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    message_id: Mapped[UUID] = mapped_column(ForeignKey("messages.id"), unique=True)
    event_id: Mapped[UUID] = mapped_column(ForeignKey("events.id"), unique=True)
    thread_pk: Mapped[UUID] = mapped_column(ForeignKey("threads.id"), index=True)
    intent: Mapped[str] = mapped_column(String(40))
    summary: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BridgeRun(Base):
    __tablename__ = "bridge_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_bridge_status",
        ),
        Index("ix_bridge_queue", "status", "created_at", "id"),
        # Defense in depth; claims also hold the global transaction advisory lock.
        Index(
            "uq_bridge_running", "status", unique=True, postgresql_where=text("status = 'running'")
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    idempotency_key: Mapped[UUID] = mapped_column(unique=True)
    requested_slack_permalink: Mapped[str] = mapped_column(String(2048))
    profile_id: Mapped[str] = mapped_column(String(64))
    profile_version: Mapped[int]
    profile_fingerprint: Mapped[str] = mapped_column(String(71))
    status: Mapped[str] = mapped_column(String(20))
    cancel_requested: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    runner_id: Mapped[UUID | None]
    lease_token: Mapped[UUID | None]
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(40))


class BridgePresence(Base):
    """Singleton capability heartbeat, separate from runs (including idle runner)."""

    __tablename__ = "bridge_presence"
    __table_args__ = (CheckConstraint("id = 1", name="ck_bridge_presence_singleton"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    runner_id: Mapped[UUID]
    profile_fingerprint: Mapped[str] = mapped_column(String(71))
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorkItem(Base):
    __tablename__ = "work_items"
    __table_args__ = (
        CheckConstraint("state IN ('active', 'waiting', 'delivered')", name="ck_work_state"),
        CheckConstraint("fixture_id = 'request_video'", name="ck_work_fixture"),
        CheckConstraint("recipe_version = 1", name="ck_work_recipe"),
        CheckConstraint("owner_id = 'efren'", name="ck_work_owner"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    idempotency_key: Mapped[UUID] = mapped_column(unique=True)
    fixture_id: Mapped[str] = mapped_column(String(40))
    recipe_version: Mapped[int]
    owner_id: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(20))
    source_snapshot: Mapped[dict] = mapped_column(JSONB)
    source_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorkJob(Base):
    __tablename__ = "work_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'waiting_human', 'succeeded', 'failed')",
            name="ck_work_job_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_work_job_attempts"),
        CheckConstraint("failure_count BETWEEN 0 AND 5", name="ck_work_job_failures"),
        Index("ix_work_job_queue", "status", "available_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    work_id: Mapped[UUID] = mapped_column(ForeignKey("work_items.id"), unique=True)
    status: Mapped[str] = mapped_column(String(20))
    checkpoint: Mapped[dict] = mapped_column(JSONB)
    attempt_count: Mapped[int]
    failure_count: Mapped[int]
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(40))


class WorkHistory(Base):
    __tablename__ = "work_history"
    __table_args__ = (
        UniqueConstraint("job_id", "sequence", name="uq_work_history_sequence"),
        CheckConstraint("sequence > 0", name="ck_work_history_sequence"),
        CheckConstraint(
            "attempt_number IS NULL OR attempt_number > 0", name="ck_work_history_attempt"
        ),
        CheckConstraint(
            "kind IN ('work_created', 'proposal_prepared', 'approval_recorded', "
            "'simulation_finished', 'attempt_failed')",
            name="ck_work_history_kind",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("work_jobs.id"))
    sequence: Mapped[int]
    kind: Mapped[str] = mapped_column(String(40))
    actor_id: Mapped[str] = mapped_column(String(200))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempt_id: Mapped[UUID | None] = mapped_column(unique=True)
    attempt_number: Mapped[int | None]
    data: Mapped[dict] = mapped_column(JSONB)


class WorkArtifact(Base):
    __tablename__ = "work_artifacts"
    __table_args__ = (
        UniqueConstraint("job_id", "version", name="uq_work_artifact_version"),
        CheckConstraint("version > 0", name="ck_work_artifact_version"),
        CheckConstraint("kind IN ('proposal', 'result')", name="ck_work_artifact_kind"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("work_jobs.id"))
    attempt_id: Mapped[UUID] = mapped_column(ForeignKey("work_history.attempt_id"))
    version: Mapped[int]
    kind: Mapped[str] = mapped_column(String(20))
    content: Mapped[dict] = mapped_column(JSONB)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorkApproval(Base):
    __tablename__ = "work_approvals"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')", name="ck_work_approval_status"
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("work_jobs.id"))
    artifact_id: Mapped[UUID] = mapped_column(ForeignKey("work_artifacts.id"), unique=True)
    artifact_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20))
    decision_reason: Mapped[str | None] = mapped_column(String(500))
    decided_by: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
