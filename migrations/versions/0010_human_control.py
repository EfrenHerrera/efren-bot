"""Human dispositions and immutable decisions over existing domains."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0010_human_control"
down_revision = "0009_mr_review"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "human_controls",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("domain", sa.String(20), nullable=False),
        sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("support_cases.id")),
        sa.Column("source_scope", sa.String(200)),
        sa.Column("project_path", sa.String(300)),
        sa.Column("mr_iid", sa.String(20)),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("case_id", name="uq_human_case"),
        sa.UniqueConstraint("source_scope", "project_path", "mr_iid", name="uq_human_mr"),
        sa.CheckConstraint(
            "(domain = 'support' AND case_id IS NOT NULL AND source_scope IS NULL "
            "AND project_path IS NULL AND mr_iid IS NULL) OR "
            "(domain = 'review' AND case_id IS NULL "
            "AND source_scope IS NOT NULL AND project_path IS NOT NULL AND mr_iid IS NOT NULL)",
            name="ck_human_identity",
        ),
        sa.CheckConstraint(
            "state IN ('active','paused','ignored','delegated','stopped')", name="ck_human_state"
        ),
        sa.CheckConstraint("revision >= 0", name="ck_human_revision"),
    )
    op.create_table(
        "human_decisions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "control_id", UUID(as_uuid=True), sa.ForeignKey("human_controls.id"), nullable=False
        ),
        sa.Column("request_id", UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("support_cases.id")),
        sa.Column("item_id", UUID(as_uuid=True), sa.ForeignKey("mr_review_items.id")),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("result", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_human_decisions_control_id", "human_decisions", ["control_id"])


def downgrade():
    op.drop_table("human_decisions")
    op.drop_table("human_controls")
