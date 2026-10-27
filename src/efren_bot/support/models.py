from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from efren_bot.models import Base


class SupportControl(Base):
    __tablename__ = "support_control"
    __table_args__ = (CheckConstraint("id = 1", name="ck_support_singleton"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused: Mapped[bool] = mapped_column(default=True)
    runner_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    epoch: Mapped[int] = mapped_column(default=1)


class SupportCase(Base):
    __tablename__ = "support_cases"
    __table_args__ = (
        UniqueConstraint("source_scope", "channel_id", "conversation_id", name="uq_support_case"),
        CheckConstraint("revision > 0", name="ck_support_revision"),
        CheckConstraint(
            "status IN ('queued','analyzing','blocked','paused','dismissed','failed')",
            name="ck_support_status",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_scope: Mapped[str] = mapped_column(String(200))
    channel_id: Mapped[str] = mapped_column(String(200))
    conversation_id: Mapped[str] = mapped_column(String(200))
    anchor_id: Mapped[UUID] = mapped_column(ForeignKey("slack_collection_messages.id"))
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20))
    revision: Mapped[int] = mapped_column(default=1)
    context: Mapped[dict] = mapped_column(JSONB)
    report: Mapped[dict] = mapped_column(JSONB, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SupportIntake(Base):
    __tablename__ = "support_intakes"
    __table_args__ = (
        UniqueConstraint("source_scope", "channel_id", "message_id", name="uq_support_intake"),
        CheckConstraint(
            "status IN ('queued','running','ignored','support','failed')",
            name="ck_support_intake_status",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_scope: Mapped[str] = mapped_column(String(200))
    channel_id: Mapped[str] = mapped_column(String(200))
    message_id: Mapped[str] = mapped_column(String(200))
    variant_id: Mapped[UUID] = mapped_column(ForeignKey("slack_collection_messages.id"))
    status: Mapped[str] = mapped_column(String(20))
    decision: Mapped[dict] = mapped_column(JSONB, default=dict)
    case_id: Mapped[UUID | None] = mapped_column(ForeignKey("support_cases.id"))
    error_code: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SupportEntry(Base):
    __tablename__ = "support_entries"
    __table_args__ = (UniqueConstraint("case_id", "request_id", name="uq_support_entry_request"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(ForeignKey("support_cases.id"), index=True)
    request_id: Mapped[UUID] = mapped_column()
    kind: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="recorded")
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
