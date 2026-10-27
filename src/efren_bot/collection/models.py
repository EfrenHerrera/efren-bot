from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    text as sql_text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from efren_bot.models import Base


class CollectionControl(Base):
    __tablename__ = "slack_collection_control"
    __table_args__ = (CheckConstraint("id = 1", name="ck_collection_singleton"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused: Mapped[bool] = mapped_column(default=True)
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    watermark: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    runner_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    progress: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=sql_text("'{}'::jsonb")
    )
    sources: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=sql_text("'{}'::jsonb")
    )


class CollectionRun(Base):
    __tablename__ = "slack_collection_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','succeeded','partial','failed')",
            name="ck_collection_run_status",
        ),
        CheckConstraint("trigger IN ('manual','automatic','import')", name="ck_collection_trigger"),
        Index(
            "uq_collection_active",
            sql_text("(1)"),
            unique=True,
            postgresql_where=sql_text("status IN ('queued','running')"),
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    trigger: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    added_count: Mapped[int] = mapped_column(default=0)
    page_count: Mapped[int] = mapped_column(default=0)
    error_code: Mapped[str | None] = mapped_column(String(40))
    coverage: Mapped[list] = mapped_column(JSONB, default=list)
    sources: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=sql_text("'{}'::jsonb")
    )


class CollectionCapture(Base):
    __tablename__ = "slack_collection_captures"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("slack_collection_runs.id"), index=True)
    operation: Mapped[str] = mapped_column(String(20))
    arguments: Mapped[dict] = mapped_column(JSONB)
    response: Mapped[dict] = mapped_column(JSONB)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CollectionMessage(Base):
    __tablename__ = "slack_collection_messages"
    __table_args__ = (
        UniqueConstraint(
            "source_scope", "channel_id", "message_id", "sha256", name="uq_collection_variant"
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    capture_id: Mapped[UUID] = mapped_column(ForeignKey("slack_collection_captures.id"))
    source_scope: Mapped[str] = mapped_column(String(200))
    channel_id: Mapped[str] = mapped_column(String(200))
    channel_name: Mapped[str] = mapped_column(String(200))
    message_id: Mapped[str] = mapped_column(String(200))
    thread_id: Mapped[str | None] = mapped_column(String(200))
    actor_id: Mapped[str | None] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sha256: Mapped[str] = mapped_column(String(64))
    is_historical: Mapped[bool] = mapped_column(default=False, server_default=sql_text("false"))
    provenance: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=sql_text("'{}'::jsonb")
    )
    stored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CollectionAnnotation(Base):
    __tablename__ = "slack_collection_annotations"
    source_scope: Mapped[str] = mapped_column(String(200), primary_key=True)
    channel_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    message_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attention: Mapped[str] = mapped_column(String(20), default="undecided")
    category: Mapped[str] = mapped_column(String(30), default="unclassified")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(
            "attention IN ('undecided','required','not_required')", name="ck_collection_attention"
        ),
        CheckConstraint(
            "category IN ('unclassified','support','code_review','coordination','information')",
            name="ck_collection_category",
        ),
    )


class CollectionConversationSeen(Base):
    __tablename__ = "slack_collection_conversation_seen"
    source_scope: Mapped[str] = mapped_column(String(200), primary_key=True)
    channel_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    conflicting: Mapped[bool] = mapped_column(primary_key=True)
    seen_through: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CollectionFollowup(Base):
    __tablename__ = "slack_collection_followups"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    request_id: Mapped[UUID] = mapped_column(unique=True)
    source_scope: Mapped[str] = mapped_column(String(200))
    channel_id: Mapped[str] = mapped_column(String(200))
    anchor_message_id: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(30))
    attention: Mapped[str] = mapped_column(String(20))
    revision: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("revision > 0", name="ck_followup_revision"),
        CheckConstraint(
            "category IN ('unclassified','support','code_review','coordination','information')",
            name="ck_followup_category",
        ),
        CheckConstraint(
            "attention IN ('undecided','required','not_required')", name="ck_followup_attention"
        ),
    )


class CollectionFollowupMessage(Base):
    __tablename__ = "slack_collection_followup_messages"
    followup_id: Mapped[UUID] = mapped_column(
        ForeignKey("slack_collection_followups.id"), primary_key=True
    )
    message_id: Mapped[str] = mapped_column(String(200), primary_key=True)
