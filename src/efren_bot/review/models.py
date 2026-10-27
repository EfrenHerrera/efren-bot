from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from efren_bot.models import Base


class ReviewControl(Base):
    __tablename__ = "mr_review_control"
    __table_args__ = (CheckConstraint("id = 1", name="ck_mr_review_singleton"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused: Mapped[bool] = mapped_column(default=True)
    epoch: Mapped[int] = mapped_column(default=1)
    runner_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReviewRequest(Base):
    __tablename__ = "mr_review_requests"
    __table_args__ = (
        UniqueConstraint("source_scope", "channel_id", "message_id", name="uq_mr_review_source"),
        UniqueConstraint("request_key", name="uq_mr_review_request_key"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    request_key: Mapped[UUID] = mapped_column(default=uuid4)
    source_scope: Mapped[str] = mapped_column(String(200))
    channel_id: Mapped[str] = mapped_column(String(200))
    message_id: Mapped[str] = mapped_column(String(200))
    variant_id: Mapped[UUID] = mapped_column(ForeignKey("slack_collection_messages.id"))
    demo: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(20))
    context: Mapped[dict] = mapped_column(JSONB)
    decision: Mapped[dict] = mapped_column(JSONB, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReviewItem(Base):
    __tablename__ = "mr_review_items"
    __table_args__ = (
        UniqueConstraint("request_id", "project_path", "mr_iid", name="uq_mr_review_item"),
        CheckConstraint("revision > 0", name="ck_mr_review_revision"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    request_id: Mapped[UUID] = mapped_column(ForeignKey("mr_review_requests.id"), index=True)
    project_path: Mapped[str] = mapped_column(String(300))
    mr_iid: Mapped[str] = mapped_column(String(20))
    url: Mapped[str] = mapped_column(String(700))
    title: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20))
    phase: Mapped[str] = mapped_column(String(20))
    revision: Mapped[int] = mapped_column(default=1)
    snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    plan: Mapped[dict] = mapped_column(JSONB, default=dict)
    report: Mapped[dict] = mapped_column(JSONB, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReviewProposal(Base):
    __tablename__ = "mr_review_proposals"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    item_id: Mapped[UUID] = mapped_column(ForeignKey("mr_review_items.id"), index=True)
    revision: Mapped[int] = mapped_column()
    version: Mapped[int] = mapped_column(default=1)
    body: Mapped[str] = mapped_column(Text)
    finding: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="private")
    remote_id: Mapped[str | None] = mapped_column(String(100))


class ReviewEntry(Base):
    __tablename__ = "mr_review_entries"
    __table_args__ = (UniqueConstraint("item_id", "request_key", name="uq_mr_review_entry_key"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    item_id: Mapped[UUID] = mapped_column(ForeignKey("mr_review_items.id"), index=True)
    request_key: Mapped[UUID] = mapped_column(default=uuid4)
    kind: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
