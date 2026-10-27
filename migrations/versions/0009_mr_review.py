"""Private MR requests, independent items, proposals and human action history."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0009_mr_review"
down_revision = "0008_support"
branch_labels = None
depends_on = None


def uid(name, target=None, primary=False):
    args = [sa.ForeignKey(target)] if target else []
    return sa.Column(name, UUID(as_uuid=True), *args, primary_key=primary, nullable=False)


def string(name, size, nullable=False):
    return sa.Column(name, sa.String(size), nullable=nullable)


def stamp(name):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False)


def upgrade():
    op.create_table(
        "mr_review_control",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("paused", sa.Boolean(), nullable=False),
        sa.Column("epoch", sa.Integer(), nullable=False),
        sa.Column("runner_seen_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("id = 1", name="ck_mr_review_singleton"),
    )
    op.create_table(
        "mr_review_requests",
        uid("id", primary=True),
        uid("request_key"),
        string("source_scope", 200),
        string("channel_id", 200),
        string("message_id", 200),
        uid("variant_id", "slack_collection_messages.id"),
        sa.Column("demo", sa.Boolean(), nullable=False),
        string("status", 20),
        sa.Column("context", JSONB(), nullable=False),
        sa.Column("decision", JSONB(), nullable=False),
        string("error_code", 60, True),
        stamp("created_at"),
        sa.UniqueConstraint("source_scope", "channel_id", "message_id", name="uq_mr_review_source"),
        sa.UniqueConstraint("request_key", name="uq_mr_review_request_key"),
    )
    op.create_table(
        "mr_review_items",
        uid("id", primary=True),
        uid("request_id", "mr_review_requests.id"),
        string("project_path", 300),
        string("mr_iid", 20),
        string("url", 700),
        string("title", 500),
        string("status", 20),
        string("phase", 20),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("snapshot", JSONB(), nullable=False),
        sa.Column("plan", JSONB(), nullable=False),
        sa.Column("report", JSONB(), nullable=False),
        string("error_code", 60, True),
        stamp("created_at"),
        stamp("updated_at"),
        sa.UniqueConstraint("request_id", "project_path", "mr_iid", name="uq_mr_review_item"),
        sa.CheckConstraint("revision > 0", name="ck_mr_review_revision"),
    )
    op.create_index("ix_mr_review_items_request_id", "mr_review_items", ["request_id"])
    op.create_table(
        "mr_review_proposals",
        uid("id", primary=True),
        uid("item_id", "mr_review_items.id"),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("finding", JSONB(), nullable=False),
        string("status", 20),
        string("remote_id", 100, True),
    )
    op.create_index("ix_mr_review_proposals_item_id", "mr_review_proposals", ["item_id"])
    op.create_table(
        "mr_review_entries",
        uid("id", primary=True),
        uid("item_id", "mr_review_items.id"),
        uid("request_key"),
        string("kind", 20),
        sa.Column("text", sa.Text(), nullable=False),
        string("status", 20),
        sa.Column("payload", JSONB(), nullable=False),
        stamp("created_at"),
        sa.UniqueConstraint("item_id", "request_key", name="uq_mr_review_entry_key"),
    )
    op.create_index("ix_mr_review_entries_item_id", "mr_review_entries", ["item_id"])


def downgrade():
    for table in (
        "mr_review_entries",
        "mr_review_proposals",
        "mr_review_items",
        "mr_review_requests",
        "mr_review_control",
    ):
        op.drop_table(table)
