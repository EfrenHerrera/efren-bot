"""Per-source confirmed progress keeps unavailable conversations independent."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005_collection_progress"
down_revision = "0004_slack_collection"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "slack_collection_control",
        sa.Column("progress", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.execute("""
        UPDATE slack_collection_control SET progress = COALESCE((
            SELECT jsonb_object_agg(scope, confirmed) FROM (
                SELECT item->>'scope' AS scope, max(r.window_end) AS confirmed
                FROM slack_collection_runs r, jsonb_array_elements(r.coverage) item
                WHERE r.status IN ('succeeded','partial') AND r.added_count = 0
                AND r.window_end IS NOT NULL
                AND item->>'state' = 'available_pages_exhausted'
                AND item->>'scope' NOT IN ('joined_channels','direct_conversations')
                AND NOT EXISTS (
                    SELECT 1 FROM jsonb_array_elements(r.coverage) child
                    WHERE right(child->>'scope', 7) = ':' || 'thread'
                )
                GROUP BY item->>'scope'
            ) confirmed_sources
        ), '{}'::jsonb) WHERE id = 1
    """)


def downgrade():
    op.drop_column("slack_collection_control", "progress")
