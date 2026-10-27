from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from efren_bot.models import Base

ITEM_STATES = "'received','admitted','needs_context','needs_human','discarded'"
JOB_STATES = "'queued','running','paused','succeeded','failed','blocked','cancelled','superseded'"
EFFECT_STATES = (
    "'proposed','approved','executing','executed',"
    "'denied','failed','uncertain','superseded','expired'"
)


class FactoryItem(Base):
    """One exact version of one request from any source."""

    __tablename__ = "factory_items"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_factory_item_fingerprint"),
        CheckConstraint(f"status IN ({ITEM_STATES})", name="ck_factory_item_status"),
        Index("ix_factory_items_source", "source_kind", "external_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_kind: Mapped[str] = mapped_column(String(30))
    external_id: Mapped[str] = mapped_column(String(300))
    fingerprint: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(300), default="")
    text: Mapped[str] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(200))
    url: Mapped[str | None] = mapped_column(String(2048))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attrs: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="received")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FactoryAdmission(Base):
    """Append-only: every admission decision, by policy or by a person."""

    __tablename__ = "factory_admissions"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('admit','ask_context','inbox','discard')", name="ck_factory_decision"
        ),
        CheckConstraint("decided_by IN ('policy','human')", name="ck_factory_decided_by"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    item_id: Mapped[UUID] = mapped_column(ForeignKey("factory_items.id"), index=True)
    decision: Mapped[str] = mapped_column(String(20))
    decided_by: Mapped[str] = mapped_column(String(10))
    reasons: Mapped[list] = mapped_column(JSONB, default=list)
    policy_version: Mapped[str] = mapped_column(String(40))
    project: Mapped[str | None] = mapped_column(String(100))
    profile: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[str | None] = mapped_column(String(20))
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FactoryJob(Base):
    __tablename__ = "factory_jobs"
    __table_args__ = (
        UniqueConstraint("job_key", name="uq_factory_job_key"),
        CheckConstraint(f"status IN ({JOB_STATES})", name="ck_factory_job_status"),
        CheckConstraint("attempt_count >= 0", name="ck_factory_job_attempts"),
        Index("ix_factory_jobs_queue", "status", "available_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_key: Mapped[str] = mapped_column(String(60))
    item_id: Mapped[UUID] = mapped_column(ForeignKey("factory_items.id"), index=True)
    project: Mapped[str] = mapped_column(String(100))
    spec: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    attempt_id: Mapped[UUID | None] = mapped_column()
    attempt_count: Mapped[int] = mapped_column(default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    run_record: Mapped[dict | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(60))
    control_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FactoryEffect(Base):
    __tablename__ = "factory_effects"
    __table_args__ = (
        UniqueConstraint("job_id", "kind", name="uq_factory_effect_kind"),
        CheckConstraint(f"state IN ({EFFECT_STATES})", name="ck_factory_effect_state"),
        CheckConstraint("policy IN ('auto','human')", name="ck_factory_effect_policy"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("factory_jobs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    policy: Mapped[str] = mapped_column(String(10))
    state: Mapped[str] = mapped_column(String(15), default="proposed")
    payload: Mapped[dict] = mapped_column(JSONB)
    fingerprint: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[str | None] = mapped_column(String(100))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_text: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
