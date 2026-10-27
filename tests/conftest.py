import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url

from efren_bot.config import Settings
from efren_bot.db import make_engine, session_factory
from efren_bot.schemas import DemoEventInput

TEST_URL = "postgresql+psycopg://efren_bot:local_demo_only@127.0.0.1:55433/efren_bot_test"


def require_test_database(value: str) -> None:
    url = make_url(value)
    if (
        url.drivername != "postgresql+psycopg"
        or url.database != "efren_bot_test"
        or url.host not in {"127.0.0.1", "localhost", "::1"}
        or url.port != 55433
        or url.query
    ):
        raise ValueError(
            "tests require loopback PostgreSQL database efren_bot_test on 55433, no query options"
        )


@pytest.fixture(scope="session")
def pg_engine():
    url = os.environ.get("DATABASE_URL", TEST_URL)
    require_test_database(url)  # BEFORE connection, migration or destructive SQL
    engine = make_engine(Settings(database_url=url))
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == "efren_bot_test"
    # Alembic reads the SAME guarded URL; restore the caller's environment afterwards.
    original = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        command.upgrade(Config("alembic.ini"), "head")
    finally:
        if original is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original
    yield engine
    engine.dispose()


@pytest.fixture
def database(pg_engine):
    # Explicit own tables only, in the previously verified separate test database.
    with pg_engine.begin() as connection:
        assert connection.scalar(text("SELECT current_database()")) == "efren_bot_test"
        connection.execute(
            text(
                "TRUNCATE activities, tasks, outbox, events, messages, threads, "
                "bridge_runs, bridge_presence, work_approvals, work_artifacts, work_history, "
                "work_jobs, work_items, slack_collection_messages, slack_collection_captures, "
                "slack_collection_runs, slack_collection_control, slack_collection_annotations, "
                "slack_collection_followup_messages, slack_collection_followups, "
                "slack_collection_conversation_seen, support_entries, support_intakes, "
                "support_cases, support_control, mr_review_entries, mr_review_proposals, "
                "mr_review_items, mr_review_requests, mr_review_control, "
                "human_decisions, human_controls"
            )
        )
    return session_factory(pg_engine)


@pytest.fixture
def event_input():
    return DemoEventInput(
        event_id="evt-request-video-001",
        workspace_id="demo-workspace",
        channel_id="demo-channel",
        message_id="msg-video-001",
        thread_id="msg-video-001",
        actor_id="ana",
        text="@efren sube el video",
        occurred_at="2026-01-15T15:00:00Z",
    )
