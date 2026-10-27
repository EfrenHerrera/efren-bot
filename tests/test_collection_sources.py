from datetime import UTC, datetime
from uuid import uuid4

import pytest

from efren_bot.collection.models import CollectionCapture, CollectionRun
from efren_bot.collection.service import CollectionError, CollectionService
from efren_bot.collection.sources import SourceInput, SourceService

pytestmark = pytest.mark.integration


def test_sources_are_membership_scoped_and_runs_freeze_configuration(database):
    now = datetime.now(UTC)
    service = CollectionService(database)
    sources = SourceService(database)
    with database.begin() as s:
        run = CollectionRun(
            id=uuid4(),
            trigger="manual",
            status="partial",
            created_at=now,
            window_start=now,
            coverage=[],
            added_count=0,
            page_count=0,
        )
        s.add(run)
        s.flush()
        s.add(
            CollectionCapture(
                run_id=run.id,
                operation="channels",
                arguments={},
                observed_at=now,
                response={
                    "result": "## My Channels (showing 1 of 1 total)\n"
                    "### private-channel\n- **ID:** C1234567890\n"
                },
            )
        )
    with pytest.raises(CollectionError):
        sources.save(SourceInput(channel_id="C9999999999", mode="full"))
    sources.save(SourceInput(channel_id="C1234567890", mode="full"))
    assert any(
        r["mode"] == "full" and r["since"]
        for r in sources.list()["channels"]
        if r["channel_id"] == "C1234567890"
    )
    service.heartbeat(now)
    service.command("activate", now)
    queued = service.command("run", now)
    sources.save(SourceInput(channel_id="C1234567890", mode="off"))
    claimed = service.claim(now)
    assert claimed["id"] == queued["id"]
    assert claimed["sources"]["C1234567890"]["mode"] == "full"
    assert service.status(now)["sources"]["C1234567890"]["mode"] == "off"
