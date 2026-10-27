"""Conversation activity and optional manually curated groups, not fixture tasks."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0007_collection_conversations"
down_revision = "0006_collection_inbox"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "slack_collection_conversation_seen",
        sa.Column("source_scope", sa.String(200), primary_key=True),
        sa.Column("channel_id", sa.String(200), primary_key=True),
        sa.Column("conversation_id", sa.String(200), primary_key=True),
        sa.Column("conflicting", sa.Boolean(), primary_key=True),
        sa.Column("seen_through", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "slack_collection_followups",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("request_id", UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("source_scope", sa.String(200), nullable=False),
        sa.Column("channel_id", sa.String(200), nullable=False),
        sa.Column("anchor_message_id", sa.String(200), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("attention", sa.String(20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("revision > 0", name="ck_followup_revision"),
        sa.CheckConstraint(
            "category IN ('unclassified','support','code_review','coordination','information')",
            name="ck_followup_category",
        ),
        sa.CheckConstraint(
            "attention IN ('undecided','required','not_required')", name="ck_followup_attention"
        ),
    )
    op.create_table(
        "slack_collection_followup_messages",
        sa.Column(
            "followup_id",
            UUID(as_uuid=True),
            sa.ForeignKey("slack_collection_followups.id"),
            primary_key=True,
        ),
        sa.Column("message_id", sa.String(200), primary_key=True),
    )


def downgrade():
    for table in (
        "slack_collection_followup_messages",
        "slack_collection_followups",
        "slack_collection_conversation_seen",
    ):
        op.drop_table(table)
