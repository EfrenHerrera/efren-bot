"""Independent support intake, cases and durable intervention history."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0008_support"
down_revision = "0007_collection_conversations"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "support_control",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("paused", sa.Boolean(), nullable=False),
        sa.Column("runner_seen_at", sa.DateTime(timezone=True)),
        sa.Column("epoch", sa.Integer(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_support_singleton"),
    )
    op.create_table(
        "support_cases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source_scope", sa.String(200), nullable=False),
        sa.Column("channel_id", sa.String(200), nullable=False),
        sa.Column("conversation_id", sa.String(200), nullable=False),
        sa.Column(
            "anchor_id",
            UUID(as_uuid=True),
            sa.ForeignKey("slack_collection_messages.id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("context", JSONB(), nullable=False),
        sa.Column("report", JSONB(), nullable=False),
        sa.Column("error_code", sa.String(60)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "source_scope", "channel_id", "conversation_id", name="uq_support_case"
        ),
        sa.CheckConstraint("revision > 0", name="ck_support_revision"),
        sa.CheckConstraint(
            "status IN ('queued','analyzing','blocked','paused','dismissed','failed')",
            name="ck_support_status",
        ),
    )
    op.create_table(
        "support_intakes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source_scope", sa.String(200), nullable=False),
        sa.Column("channel_id", sa.String(200), nullable=False),
        sa.Column("message_id", sa.String(200), nullable=False),
        sa.Column(
            "variant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("slack_collection_messages.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("decision", JSONB(), nullable=False),
        sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("support_cases.id")),
        sa.Column("error_code", sa.String(60)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_scope", "channel_id", "message_id", name="uq_support_intake"),
        sa.CheckConstraint(
            "status IN ('queued','running','ignored','support','failed')",
            name="ck_support_intake_status",
        ),
    )
    op.create_table(
        "support_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("support_cases.id"), nullable=False),
        sa.Column("request_id", UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("case_id", "request_id", name="uq_support_entry_request"),
    )
    op.create_index("ix_support_entries_case_id", "support_entries", ["case_id"])


def downgrade():
    for name in ("support_entries", "support_intakes", "support_cases", "support_control"):
        op.drop_table(name)
