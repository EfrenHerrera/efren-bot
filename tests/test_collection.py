from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from efren_bot.collection.service import CollectionService

pytestmark = pytest.mark.integration


@pytest.fixture
def collection(database):
    return CollectionService(database)


def test_pause_manual_and_interval_share_one_run(collection):
    now = datetime(2026, 10, 25, tzinfo=UTC)
    collection.heartbeat(now)
    collection.command("activate", now)
    assert collection.claim(now + timedelta(minutes=14)) is None
    collection.command("pause", now)
    assert collection.claim(now + timedelta(minutes=16)) is None
    collection.heartbeat(now + timedelta(minutes=16))
    queued = collection.command("run", now + timedelta(minutes=16))
    assert collection.command("run", now + timedelta(minutes=16))["id"] == queued["id"]
    run = collection.claim(now + timedelta(minutes=16))
    assert run["id"] == queued["id"]
    assert run["trigger"] == "manual"
    collection.finish(run["id"], "succeeded", now + timedelta(minutes=17))
    assert collection.status(now + timedelta(minutes=17))["paused"] is True
    assert collection.claim(now + timedelta(minutes=40)) is None
    collection.command("resume", now + timedelta(minutes=40))
    assert collection.claim(now + timedelta(minutes=54)) is None
    assert collection.claim(now + timedelta(minutes=55))["trigger"] == "automatic"


def test_partial_and_crash_never_advance(collection):
    now = datetime.now(UTC)
    collection.heartbeat(now)
    collection.command("activate", now)
    collection.command("run", now)
    run = collection.claim(now)
    collection.finish(run["id"], "partial", now, error_code="page_limit")
    assert collection.status(now)["watermark"] is None
    collection.command("run", now)
    collection.claim(now)
    collection.recover(now)
    assert collection.status(now)["active_run"] is None
    assert collection.status(now)["watermark"] is None


def test_concurrent_clicks_coalesce(collection):
    now = datetime.now(UTC)
    collection.heartbeat(now)
    collection.command("activate", now)
    with ThreadPoolExecutor(max_workers=4) as pool:
        runs = list(pool.map(lambda _: collection.command("run", now), range(8)))
    assert len({r["id"] for r in runs}) == 1


def test_partial_source_progress_does_not_claim_global_success(collection):
    now = datetime.now(UTC)
    collection.heartbeat(now)
    collection.command("activate", now)
    collection.command("run", now)
    run = collection.claim(now)
    progress = {"C08MAH1JNC8": now.isoformat()}
    collection.finish(run["id"], "partial", now, progress=progress)
    state = collection.status(now)
    assert state["watermark"] is None
    assert state["progress"] == progress
    collection.command("run", now)
    assert collection.claim(now)["progress"] == progress
