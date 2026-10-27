"""Local review annotations and provenance, independent of source messages/tasks."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006_collection_inbox"
down_revision = "0005_collection_progress"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "slack_collection_messages",
        sa.Column(
            "stored_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.drop_constraint("ck_collection_trigger", "slack_collection_runs", type_="check")
    op.create_check_constraint(
        "ck_collection_trigger",
        "slack_collection_runs",
        "trigger IN ('manual','automatic','import')",
    )
    for table in ("slack_collection_control", "slack_collection_runs"):
        op.add_column(
            table,
            sa.Column("sources", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        )
    op.add_column(
        "slack_collection_messages",
        sa.Column("is_historical", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "slack_collection_messages",
        sa.Column("provenance", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_table(
        "slack_collection_annotations",
        sa.Column("source_scope", sa.String(200), primary_key=True),
        sa.Column("channel_id", sa.String(200), primary_key=True),
        sa.Column("message_id", sa.String(200), primary_key=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("attention", sa.String(20), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "attention IN ('undecided','required','not_required')", name="ck_collection_attention"
        ),
        sa.CheckConstraint(
            "category IN ('unclassified','support','code_review','coordination','information')",
            name="ck_collection_category",
        ),
    )


def downgrade():
    # Imported runs cannot be silently reclassified as manual executions.
    op.drop_constraint("ck_collection_trigger", "slack_collection_runs", type_="check")
    op.create_check_constraint(
        "ck_collection_trigger", "slack_collection_runs", "trigger IN ('manual','automatic')"
    )
    op.drop_table("slack_collection_annotations")
    for column in ("provenance", "is_historical", "stored_at"):
        op.drop_column("slack_collection_messages", column)
    for table in ("slack_collection_runs", "slack_collection_control"):
        op.drop_column(table, "sources")
