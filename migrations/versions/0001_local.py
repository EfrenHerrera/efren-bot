"""Canonical local identities, receipt/outbox and projections."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0001_local"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "threads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("workspace_id", sa.String(200), nullable=False),
        sa.Column("channel_id", sa.String(200), nullable=False),
        sa.Column("thread_id", sa.String(200), nullable=False),
        sa.UniqueConstraint(
            "provider", "workspace_id", "channel_id", "thread_id", name="uq_thread"
        ),
        sa.CheckConstraint("provider = 'fixture'", name="ck_thread_provider"),
    )
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("workspace_id", sa.String(200), nullable=False),
        sa.Column("channel_id", sa.String(200), nullable=False),
        sa.Column("message_id", sa.String(200), nullable=False),
        sa.Column("thread_pk", UUID(as_uuid=True), sa.ForeignKey("threads.id"), nullable=False),
        sa.Column("canonical_event_id", UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("actor_id", sa.String(200), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_url", sa.String(2048)),
        sa.UniqueConstraint(
            "provider", "workspace_id", "channel_id", "message_id", name="uq_message"
        ),
        sa.CheckConstraint("provider = 'fixture'", name="ck_message_provider"),
    )
    op.create_index("ix_messages_thread", "messages", ["thread_pk", "occurred_at", "id"])
    op.create_table(
        "events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("owner_id", sa.String(200), nullable=False),
        sa.Column("workspace_id", sa.String(200), nullable=False),
        sa.Column("channel_id", sa.String(200), nullable=False),
        sa.Column("event_id", sa.String(200), nullable=False),
        sa.Column("message_pk", UUID(as_uuid=True), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column(
            "accepted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("provider", "workspace_id", "channel_id", "event_id", name="uq_event"),
        sa.CheckConstraint("provider = 'fixture'", name="ck_event_provider"),
        sa.CheckConstraint("owner_id = 'efren'", name="ck_event_owner"),
    )
    op.create_foreign_key(
        "fk_message_canonical_event",
        "messages",
        "events",
        ["canonical_event_id"],
        ["id"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_table(
        "outbox",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "event_id", UUID(as_uuid=True), sa.ForeignKey("events.id"), nullable=False, unique=True
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(200)),
        sa.CheckConstraint("status IN ('pending', 'processed', 'failed')", name="ck_outbox_status"),
        sa.CheckConstraint("attempts BETWEEN 0 AND 5", name="ck_outbox_attempts"),
    )
    op.create_index("ix_outbox_poll", "outbox", ["status", "available_at", "created_at", "id"])
    op.create_table(
        "tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_message_id",
            UUID(as_uuid=True),
            sa.ForeignKey("messages.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "source_event_id",
            UUID(as_uuid=True),
            sa.ForeignKey("events.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("thread_pk", UUID(as_uuid=True), sa.ForeignKey("threads.id"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("next_action", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(2048)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("has_new_reply", sa.Boolean(), nullable=False, server_default="false"),
        sa.CheckConstraint("state IN ('needs_context', 'ready')", name="ck_task_state"),
    )
    op.create_index("ix_tasks_thread_pk", "tasks", ["thread_pk"])
    op.create_table(
        "activities",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "message_id",
            UUID(as_uuid=True),
            sa.ForeignKey("messages.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "event_id", UUID(as_uuid=True), sa.ForeignKey("events.id"), nullable=False, unique=True
        ),
        sa.Column("thread_pk", UUID(as_uuid=True), sa.ForeignKey("threads.id"), nullable=False),
        sa.Column("intent", sa.String(40), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_activities_thread_pk", "activities", ["thread_pk"])


def downgrade():
    op.drop_table("activities")
    op.drop_table("tasks")
    op.drop_table("outbox")
    op.drop_constraint("fk_message_canonical_event", "messages", type_="foreignkey")
    op.drop_table("events")
    op.drop_table("messages")
    op.drop_table("threads")
    # vector is a shared database extension, not owned by this migration's tables.
