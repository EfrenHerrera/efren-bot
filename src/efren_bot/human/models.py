from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from efren_bot.models import Base

IDENTITY_CHECK = (
    "(domain = 'support' AND case_id IS NOT NULL AND source_scope IS NULL "
    "AND project_path IS NULL AND mr_iid IS NULL) OR (domain = 'review' AND case_id IS NULL "
    "AND source_scope IS NOT NULL AND project_path IS NOT NULL AND mr_iid IS NOT NULL)"
)


class HumanControl(Base):
    __tablename__ = "human_controls"
    __table_args__ = (
        UniqueConstraint("case_id", name="uq_human_case"),
        UniqueConstraint("source_scope", "project_path", "mr_iid", name="uq_human_mr"),
        CheckConstraint(IDENTITY_CHECK, name="ck_human_identity"),
        CheckConstraint(
            "state IN ('active','paused','ignored','delegated','stopped')", name="ck_human_state"
        ),
        CheckConstraint("revision >= 0", name="ck_human_revision"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    domain: Mapped[str] = mapped_column(String(20))
    case_id: Mapped[UUID | None] = mapped_column(ForeignKey("support_cases.id"))
    source_scope: Mapped[str | None] = mapped_column(String(200))
    project_path: Mapped[str | None] = mapped_column(String(300))
    mr_iid: Mapped[str | None] = mapped_column(String(20))
    state: Mapped[str] = mapped_column(String(20), default="active")
    revision: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class HumanDecision(Base):
    __tablename__ = "human_decisions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    control_id: Mapped[UUID] = mapped_column(ForeignKey("human_controls.id"), index=True)
    request_id: Mapped[UUID] = mapped_column(unique=True)
    case_id: Mapped[UUID | None] = mapped_column(ForeignKey("support_cases.id"))
    item_id: Mapped[UUID | None] = mapped_column(ForeignKey("mr_review_items.id"))
    payload: Mapped[dict] = mapped_column(JSONB)
    result: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
