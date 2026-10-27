from datetime import UTC, datetime

import pytest

from efren_bot.collection.reader import collect, next_cursor, parse_memberships, parse_messages
from efren_bot.collection.transport import TransportError

MEMBERS = {
    "result": "## My Channels (showing 3 of 3 total)\n"
    "### devs\n- **ID:** C08MAH1JNC8\n### tech\n- **ID:** C07SRBE0V1T\n"
    "### other\n- **ID:** C1234567890\n"
}


def search_message(channel, body):
    return {
        "results": "## Messages (1 results)\n### Result 1 of 1\n"
        f"Channel: #x (ID: {channel})\nMessage_ts: 1767225600.000001\n"
        "From: Person (ID: U1234567890)\nText: " + body,
        "pagination_info": "There are no more results.",
    }


def test_search_scope_escape_is_not_persisted():
    saved = []

    def read(operation, args):
        if operation == "channels":
            return MEMBERS
        if operation == "history":
            return {
                "messages": f"Channel: #x ({args['channel_id']})\n\n",
                "pagination_info": "There are no more messages.",
            }
        return search_message("C1234567890", "not an explicit mention")

    start = datetime(2026, 1, 1, tzinfo=UTC)
    result = collect(
        read, start, start.replace(hour=1), lambda *args: None, lambda *args: saved.append(args)
    )
    assert result["status"] == "partial"
    assert saved == []


def test_repeated_cursor_is_partial_not_silent_exhaustion():
    def read(*args):
        return {**MEMBERS, "next_cursor": "synthetic-cursor"}

    now = datetime.now(UTC)
    result = collect(read, now, now, lambda *args: None, lambda *args: None)
    assert result["status"] == "partial"
    assert result["error_code"] == "membership_incomplete"
    assert any(c.get("code") == "cursor_repeated" for c in result["coverage"])


def test_thread_parser_preserves_parent_and_replies_without_forcing_root_dates():
    parent = "1767225600.000001"
    response = {
        "messages": "=== THREAD PARENT MESSAGE ===\n"
        "From: Person (ID: U1234567890)\nTime: 2026-01-01 00:00:00 UTC\n"
        f"Message TS: {parent}\nparent\n=== THREAD REPLIES (1 total) ===\n"
        "--- Reply 1 of 1 ---\nFrom: Other (ID: U1234567891)\n"
        "Time: 2026-01-01 00:00:01 UTC\nMessage TS: 1767225601.000001\nreply"
    }
    rows = parse_messages(response, "thread", "C08MAH1JNC8", parent)
    assert len(rows) == 2
    assert rows[1]["thread_id"] == parent
    assert rows[1]["message_id"] != parent


def test_membership_formats_and_exhaustion():
    data = {
        "result": "## My Channels (showing 2 of 2 total)\n\n"
        "### #crd-wc-devs\n- **ID:** C08MAH1JNC8\n\n### Person\n"
        "- **ID:** D1234567890\n- **Type:** Direct Message\n"
    }
    rows = parse_memberships(data)
    assert rows[0]["channel_id"] == "C08MAH1JNC8"
    assert rows[1]["direct"] is True
    assert next_cursor(data, "channels") is None
    with pytest.raises(ValueError):
        next_cursor({"pagination_info": "Unknown pagination"}, "history")


def test_empty_history_and_exact_identity():
    response = {
        "messages": "Channel: #devs (C08MAH1JNC8)\n\n",
        "pagination_info": "There are no more messages available.\n",
    }
    assert parse_messages(response, "history", "C08MAH1JNC8") == []
    assert next_cursor(response, "history") is None
    response["messages"] += (
        "=== Message from Person (ID: U1234567890) at 2026-01-01 00:00:00 UTC ===\n"
        "Message TS: 1767225600.000001\nhello\nThread: 1 replies (last: x)\n"
    )
    rows = parse_messages(response, "history", "C08MAH1JNC8")
    assert rows[0]["message_id"] == "1767225600.000001"
    assert rows[0]["thread_id"] == "1767225600.000001"
    assert rows[0]["occurred_at"].microsecond == 1


def test_native_empty_search_format_is_not_a_parser_failure():
    response = {
        "results": "# Search results for: \n\nNo results found.\n",
        "pagination_info": "There are no more results.",
    }
    assert parse_messages(response, "search") == []


def test_rate_limit_defers_remaining_calls_instead_of_hammering_source():
    calls = []

    def read(operation, args):
        calls.append(operation)
        if operation == "channels":
            return MEMBERS
        raise TransportError("source_rate_limited")

    now = datetime.now(UTC)
    result = collect(read, now, now, lambda *args: None, lambda *args: None)
    assert result["status"] == "partial"
    assert calls == ["channels", "channels", "history"]
    assert any(c.get("code") == "rate_limit_deferred" for c in result["coverage"])


def test_healthy_source_uses_own_confirmed_progress_when_another_is_unavailable():
    calls = []

    def read(operation, args):
        calls.append((operation, args))
        if operation == "channels":
            return MEMBERS
        if operation == "history":
            if args["channel_id"] == "C07SRBE0V1T":
                raise TransportError("channel_unavailable")
            return {
                "messages": f"Channel: #x ({args['channel_id']})\n\n",
                "pagination_info": "There are no more messages.",
            }
        return {
            "results": "## Messages (0 results)",
            "pagination_info": "There are no more results.",
        }

    start = datetime(2026, 1, 1, tzinfo=UTC)
    confirmed = start.replace(day=2)
    end = start.replace(day=3)
    result = collect(
        read,
        start,
        end,
        lambda *args: None,
        lambda *args: None,
        progress={"C08MAH1JNC8": confirmed.isoformat()},
    )
    assert result["status"] == "partial"
    assert result["progress"]["C08MAH1JNC8"] == end.isoformat()
    assert "C07SRBE0V1T" not in result["progress"]
    history = [
        args for op, args in calls if op == "history" and args["channel_id"] == "C08MAH1JNC8"
    ]
    assert history[0]["oldest"] == f"{(confirmed.timestamp() - 3600):.6f}"


def test_pending_thread_does_not_advance_the_parent_source_checkpoint():
    def read(operation, args):
        if operation == "channels":
            return MEMBERS
        if operation == "thread":
            raise TransportError("channel_unavailable")
        if operation == "search":
            return {
                "results": "## Messages (0 results)",
                "pagination_info": "There are no more results.",
            }
        body = f"Channel: #x ({args['channel_id']})\n\n"
        if args["channel_id"] == "C08MAH1JNC8":
            body += (
                "=== Message from Person (ID: U1234567890) at 2026-01-01 00:00:00 UTC ===\n"
                "Message TS: 1767225600.000001\nsynthetic\nThread: 1 replies (last: x)\n"
            )
        return {"messages": body, "pagination_info": "There are no more messages."}

    start = datetime(2026, 1, 1, tzinfo=UTC)
    result = collect(read, start, start.replace(hour=1), lambda *args: None, lambda *args: None)
    assert result["status"] == "partial"
    assert "C08MAH1JNC8" not in result["progress"]
    assert "C07SRBE0V1T" in result["progress"]


def test_configured_full_channel_and_disabled_channel_constrain_reads():
    calls = []

    def read(operation, args):
        calls.append((operation, args))
        if operation == "channels":
            return MEMBERS
        if operation == "history":
            return {
                "messages": f"Channel: #x ({args['channel_id']})\n\n",
                "pagination_info": "There are no more messages.",
            }
        return {
            "results": "## Messages (0 results)",
            "pagination_info": "There are no more results.",
        }

    start = datetime(2026, 1, 1, tzinfo=UTC)
    since = start.replace(hour=1)
    end = start.replace(hour=2)
    result = collect(
        read,
        start,
        end,
        lambda *args: None,
        lambda *args: None,
        sources={
            "C08MAH1JNC8": {"mode": "off", "since": None},
            "C1234567890": {"mode": "full", "since": since.isoformat()},
        },
    )
    assert result["status"] == "succeeded"
    assert all(args.get("channel_id") != "C08MAH1JNC8" for op, args in calls if op == "history")
    custom = [args for op, args in calls if op == "history" and args["channel_id"] == "C1234567890"]
    assert custom[0]["oldest"] == f"{since.timestamp():.6f}"


def test_manual_collector_does_not_expand_unapproved_channels():
    calls, captures = [], []

    def read(operation, args):
        calls.append((operation, args))
        if operation == "channels":
            return {
                "result": "## My Channels (showing 2 of 2 total)\n"
                "### devs\n- **ID:** C08MAH1JNC8\n### tech\n- **ID:** C07SRBE0V1T\n"
            }
        if operation == "history":
            return {
                "messages": f"Channel: #x ({args['channel_id']})\n\n",
                "pagination_info": "There are no more messages available.",
            }
        return {
            "results": "## Messages (0 results)",
            "pagination_info": "There are no more results.",
        }

    now = datetime.now(UTC)
    result = collect(read, now, now, lambda *args: captures.append(args), lambda *args: None)
    assert result["status"] == "succeeded"
    assert len(captures) == len(calls)
    assert all(args.get("only_my_channels") is True for op, args in calls if op == "search")
    assert all(args.get("include_context") is False for op, args in calls if op == "search")
    assert all(
        args["channel_id"] in {"C08MAH1JNC8", "C07SRBE0V1T"}
        for op, args in calls
        if op in {"history", "thread"}
    )
