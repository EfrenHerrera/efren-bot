"""Factory control plane: intake funnel, admissions, jobs and gated effects."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0011_factory"
down_revision = "0010_human_control"
branch_labels = None
depends_on = None

ITEM_STATES = "'received','admitted','needs_context','needs_human','discarded'"
JOB_STATES = "'queued','running','paused','succeeded','failed','blocked','cancelled','superseded'"
EFFECT_STATES = (
    "'proposed','approved','executing','executed',"
    "'denied','failed','uncertain','superseded','expired'"
)


def upgrade():
    op.create_table(
        "factory_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source_kind", sa.String(30), nullable=False),
        sa.Column("external_id", sa.String(300), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("author", sa.String(200)),
        sa.Column("url", sa.String(2048)),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attrs", JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("fingerprint", name="uq_factory_item_fingerprint"),
        sa.CheckConstraint(f"status IN ({ITEM_STATES})", name="ck_factory_item_status"),
    )
    op.create_index("ix_factory_items_source", "factory_items", ["source_kind", "external_id"])
    op.create_table(
        "factory_admissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("item_id", UUID(as_uuid=True), sa.ForeignKey("factory_items.id"), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("decided_by", sa.String(10), nullable=False),
        sa.Column("reasons", JSONB(), nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("project", sa.String(100)),
        sa.Column("profile", sa.String(100)),
        sa.Column("role", sa.String(20)),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('admit','ask_context','inbox','discard')", name="ck_factory_decision"
        ),
        sa.CheckConstraint("decided_by IN ('policy','human')", name="ck_factory_decided_by"),
    )
    op.create_index("ix_factory_admissions_item_id", "factory_admissions", ["item_id"])
    op.create_table(
        "factory_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("job_key", sa.String(60), nullable=False),
        sa.Column("item_id", UUID(as_uuid=True), sa.ForeignKey("factory_items.id"), nullable=False),
        sa.Column("project", sa.String(100), nullable=False),
        sa.Column("spec", JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempt_id", UUID(as_uuid=True)),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("run_record", JSONB()),
        sa.Column("error_code", sa.String(60)),
        sa.Column("control_note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_key", name="uq_factory_job_key"),
        sa.CheckConstraint(f"status IN ({JOB_STATES})", name="ck_factory_job_status"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_factory_job_attempts"),
    )
    op.create_index("ix_factory_jobs_item_id", "factory_jobs", ["item_id"])
    op.create_index("ix_factory_jobs_queue", "factory_jobs", ["status", "available_at"])
    op.create_table(
        "factory_effects",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("factory_jobs.id"), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("policy", sa.String(10), nullable=False),
        sa.Column("state", sa.String(15), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by", sa.String(100)),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("decision_text", sa.Text(), nullable=False),
        sa.Column("result", JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_id", "kind", name="uq_factory_effect_kind"),
        sa.CheckConstraint(f"state IN ({EFFECT_STATES})", name="ck_factory_effect_state"),
        sa.CheckConstraint("policy IN ('auto','human')", name="ck_factory_effect_policy"),
    )
    op.create_index("ix_factory_effects_job_id", "factory_effects", ["job_id"])


def downgrade():
    op.drop_table("factory_effects")
    op.drop_table("factory_jobs")
    op.drop_table("factory_admissions")
    op.drop_table("factory_items")
