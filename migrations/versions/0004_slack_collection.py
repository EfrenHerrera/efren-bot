"""Independent collection tables; original fixture tables remain unchanged."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0004_slack_collection"
down_revision = "0003_synthetic_work"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "slack_collection_control",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("paused", sa.Boolean(), nullable=False),
        sa.Column("next_due_at", sa.DateTime(timezone=True)),
        sa.Column("watermark", sa.DateTime(timezone=True)),
        sa.Column("runner_seen_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("id = 1", name="ck_collection_singleton"),
    )
    op.create_table(
        "slack_collection_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("trigger", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True)),
        sa.Column("added_count", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(40)),
        sa.Column("coverage", JSONB(), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','partial','failed')",
            name="ck_collection_run_status",
        ),
        sa.CheckConstraint("trigger IN ('manual','automatic')", name="ck_collection_trigger"),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_collection_active ON slack_collection_runs ((1)) "
        "WHERE status IN ('queued','running')"
    )
    op.create_table(
        "slack_collection_captures",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id", UUID(as_uuid=True), sa.ForeignKey("slack_collection_runs.id"), nullable=False
        ),
        sa.Column("operation", sa.String(20), nullable=False),
        sa.Column("arguments", JSONB(), nullable=False),
        sa.Column("response", JSONB(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_slack_collection_captures_run_id", "slack_collection_captures", ["run_id"])
    op.create_table(
        "slack_collection_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "capture_id",
            UUID(as_uuid=True),
            sa.ForeignKey("slack_collection_captures.id"),
            nullable=False,
        ),
        sa.Column("source_scope", sa.String(200), nullable=False),
        sa.Column("channel_id", sa.String(200), nullable=False),
        sa.Column("channel_name", sa.String(200), nullable=False),
        sa.Column("message_id", sa.String(200), nullable=False),
        sa.Column("thread_id", sa.String(200)),
        sa.Column("actor_id", sa.String(200)),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_url", sa.String(2048)),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.UniqueConstraint(
            "source_scope", "channel_id", "message_id", "sha256", name="uq_collection_variant"
        ),
    )
    op.create_index(
        "ix_slack_collection_messages_occurred_at", "slack_collection_messages", ["occurred_at"]
    )


def downgrade():
    for name in (
        "slack_collection_messages",
        "slack_collection_captures",
        "slack_collection_runs",
        "slack_collection_control",
    ):
        op.drop_table(name)
