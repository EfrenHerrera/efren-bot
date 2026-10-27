from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from efren_bot.collection.models import CollectionMessage
from efren_bot.collection.runner import execute_run
from efren_bot.collection.service import CollectionService
from efren_bot.models import Task

pytestmark = pytest.mark.integration


class SyntheticSource:
    def read(self, operation, args):
        if operation == "channels":
            return {
                "result": "## My Channels (showing 2 of 2 total)\n"
                "### devs\n- **ID:** C08MAH1JNC8\n### tech\n- **ID:** C07SRBE0V1T\n"
            }
        if operation == "history":
            return {
                "messages": f"Channel: #x ({args['channel_id']})\n\n"
                "=== Message from Person (ID: U1234567890) at 2026-01-01 00:00:00 UTC ===\n"
                "Message TS: 1767225600.000001\nsynthetic body\n",
                "pagination_info": "There are no more messages.",
            }
        return {
            "results": "## Messages (0 results)",
            "pagination_info": "There are no more results.",
        }


def test_persisted_capture_dedupes_retries_without_creating_tasks(database):
    service = CollectionService(database)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start.replace(hour=1)
    service.heartbeat(start)
    service.command("activate", start)
    totals = []
    for _ in range(2):
        service.heartbeat(end)
        service.command("run", end)
        run = service.claim(end)
        result = execute_run(database, run, SyntheticSource())
        totals.append(result["added"])
        service.finish(run["id"], **result)
    assert totals == [2, 0]
    with database() as session:
        assert session.scalar(select(func.count()).select_from(CollectionMessage)) == 2
        assert session.scalar(select(func.count()).select_from(Task)) == 0
