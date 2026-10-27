"""Separate manual bridge runs and compatible idle-runner presence."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0002_bridge"
down_revision = "0001_local"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "bridge_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("idempotency_key", UUID(as_uuid=True), unique=True, nullable=False),
        sa.Column("requested_slack_permalink", sa.String(2048), nullable=False),
        sa.Column("profile_id", sa.String(64), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("profile_fingerprint", sa.String(71), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("runner_id", UUID(as_uuid=True)),
        sa.Column("lease_token", UUID(as_uuid=True)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("result", JSONB()),
        sa.Column("error_code", sa.String(40)),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_bridge_status",
        ),
    )
    op.create_index("ix_bridge_queue", "bridge_runs", ["status", "created_at", "id"])
    op.create_index(
        "uq_bridge_running",
        "bridge_runs",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )
    op.create_table(
        "bridge_presence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("runner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("profile_fingerprint", sa.String(71), nullable=False),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_bridge_presence_singleton"),
    )


def downgrade():
    op.drop_table("bridge_presence")
    op.drop_table("bridge_runs")
