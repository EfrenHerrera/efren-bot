"""Independent synthetic work, job, history, artifact and approval persistence."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0003_synthetic_work"
down_revision = "0002_bridge"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "work_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("idempotency_key", UUID(as_uuid=True), unique=True, nullable=False),
        sa.Column("fixture_id", sa.String(40), nullable=False),
        sa.Column("recipe_version", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.String(200), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("source_snapshot", JSONB(), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("state IN ('active', 'waiting', 'delivered')", name="ck_work_state"),
        sa.CheckConstraint("fixture_id = 'request_video'", name="ck_work_fixture"),
        sa.CheckConstraint("recipe_version = 1", name="ck_work_recipe"),
        sa.CheckConstraint("owner_id = 'efren'", name="ck_work_owner"),
    )
    op.create_table(
        "work_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "work_id",
            UUID(as_uuid=True),
            sa.ForeignKey("work_items.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("checkpoint", JSONB(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error_code", sa.String(40)),
        sa.CheckConstraint(
            "status IN ('queued', 'waiting_human', 'succeeded', 'failed')",
            name="ck_work_job_status",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_work_job_attempts"),
        sa.CheckConstraint("failure_count BETWEEN 0 AND 5", name="ck_work_job_failures"),
    )
    op.create_index("ix_work_job_queue", "work_jobs", ["status", "available_at", "id"])
    op.create_table(
        "work_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("work_jobs.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("actor_id", sa.String(200), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_id", UUID(as_uuid=True), unique=True),
        sa.Column("attempt_number", sa.Integer()),
        sa.Column("data", JSONB(), nullable=False),
        sa.UniqueConstraint("job_id", "sequence", name="uq_work_history_sequence"),
        sa.CheckConstraint("sequence > 0", name="ck_work_history_sequence"),
        sa.CheckConstraint(
            "attempt_number IS NULL OR attempt_number > 0", name="ck_work_history_attempt"
        ),
        sa.CheckConstraint(
            "kind IN ('work_created', 'proposal_prepared', 'approval_recorded', "
            "'simulation_finished', 'attempt_failed')",
            name="ck_work_history_kind",
        ),
    )
    op.create_table(
        "work_artifacts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("work_jobs.id"), nullable=False),
        sa.Column(
            "attempt_id",
            UUID(as_uuid=True),
            sa.ForeignKey("work_history.attempt_id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("content", JSONB(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_id", "version", name="uq_work_artifact_version"),
        sa.CheckConstraint("version > 0", name="ck_work_artifact_version"),
        sa.CheckConstraint("kind IN ('proposal', 'result')", name="ck_work_artifact_kind"),
    )
    op.create_table(
        "work_approvals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("work_jobs.id"), nullable=False),
        sa.Column(
            "artifact_id",
            UUID(as_uuid=True),
            sa.ForeignKey("work_artifacts.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("decision_reason", sa.String(500)),
        sa.Column("decided_by", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')", name="ck_work_approval_status"
        ),
    )


def downgrade():
    for table in ("work_approvals", "work_artifacts", "work_history", "work_jobs", "work_items"):
        op.drop_table(table)
