"""Closed-scope collection of connector representations, never source actions."""

import re
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

from efren_bot.collection.transport import USER_ID, TransportError

FULL = {"C08MAH1JNC8": "crd-wc-devs", "C07SRBE0V1T": "crd-wc-tech"}
TS = r"\d{10}\.\d{6}"
HISTORY = re.compile(r"^=== Message from (.+?) at (.+?) ===[ \t]*$", re.M)
SEARCH = re.compile(r"^### Result (\d+) of (\d+)\s*$", re.M)
REPLY = re.compile(r"^--- Reply \d+ of \d+ ---[ \t]*$", re.M)
HEADER = re.compile(rf"\AFrom: ([^\n]+)\nTime: ([^\n]+)\nMessage TS: ({TS})[ \t]*(?:\n|$)")
MENTION = re.compile(r"<@" + USER_ID + r"(?:\|[^>\n]*)?>")
MAX_CALLS = 400
MAX_SECONDS = 720


def query_stamp(value):
    delta = value.astimezone(UTC) - datetime(1970, 1, 1, tzinfo=UTC)
    seconds = delta.days * 86400 + delta.seconds
    return f"{seconds}.{delta.microseconds:06d}"


def unwrap(data):
    if isinstance(data.get("result"), dict):
        return data["result"]
    return data


def stamp_datetime(stamp):
    if not isinstance(stamp, str) or re.fullmatch(TS, stamp) is None:
        raise ValueError("timestamp_invalid")
    value = Decimal(stamp)
    return datetime.fromtimestamp(int(value), UTC).replace(
        microsecond=int((value - int(value)) * 1_000_000)
    )


def parse_memberships(data):
    data = unwrap(data)
    if isinstance(data.get("channels"), list):
        result = []
        for channel in data["channels"]:
            if not isinstance(channel.get("id"), str):
                raise ValueError("membership_format")
            result.append(
                {
                    "channel_id": channel["id"],
                    "channel_name": channel.get("name") or channel["id"],
                    "direct": bool(channel.get("is_im") or channel.get("is_mpim")),
                }
            )
        return result
    rendered = data.get("result", "")
    if not isinstance(rendered, str) or not re.search(
        r"^## My Channels \(showing \d+ of \d+ total\)", rendered
    ):
        raise ValueError("membership_format")
    blocks = re.split(r"^### ", rendered, flags=re.M)[1:]
    result = []
    for block in blocks:
        ids = re.findall(r"^- \*\*ID:\*\*\s*([CDG][A-Z0-9]+)\s*$", block, re.M)
        if len(ids) != 1:
            raise ValueError("membership_format")
        kind = re.findall(r"^- \*\*Type:\*\*\s*([^\n]+)", block, re.M)
        result.append(
            {
                "channel_id": ids[0],
                "channel_name": block.splitlines()[0].strip().lstrip("#")[:200],
                "direct": kind in (["Direct Message"], ["Group DM"]),
            }
        )
    return result


def next_cursor(data, operation):
    data = unwrap(data)
    cursor = data.get("next_cursor") or data.get("response_metadata", {}).get("next_cursor")
    if cursor:
        if not isinstance(cursor, str) or len(cursor) > 16384:
            raise ValueError("cursor_format")
        return cursor
    info = data.get("pagination_info")
    if not isinstance(info, str) and operation == "channels":
        info = data.get("result", "")
        count = re.search(r"^## My Channels \(showing (\d+) of (\d+) total\)", info)
        if count and count[1] == count[2]:
            return None
    if isinstance(info, str):
        matches = re.findall(r"cursor(?:\s*:\s*|\s+)`([^`]+)`", info, re.I)
        if len(set(matches)) == 1:
            return matches[0]
        if not matches and re.search(r"no more|end of results", info, re.I):
            return None
    if data.get("has_more") is False:
        return None
    raise ValueError("pagination_unknown")


def field(block, name):
    values = re.findall(r"^" + re.escape(name) + r":[ \t]*(.*)$", block, re.M)
    return values[0].strip() if len(values) == 1 else None


def message(channel, stamp, body, author, thread=None, url=None):
    if not isinstance(channel, str) or re.fullmatch(r"[CDG][A-Z0-9]+", channel) is None:
        raise ValueError("message_channel")
    if thread is not None and re.fullmatch(TS, thread) is None:
        raise ValueError("thread_identity")
    user = re.findall(r"\((?:ID:\s*)?([UW][A-Z0-9]+)\)", author or "")
    return {
        "channel_id": channel,
        "message_id": stamp,
        "thread_id": thread,
        "actor_id": user[0] if len(user) == 1 else None,
        "text": body,
        "occurred_at": stamp_datetime(stamp),
        "source_url": url,
    }


def parse_messages(data, operation, channel=None, parent=None):
    data = unwrap(data)
    rendered = data.get("results" if operation == "search" else "messages")
    if not isinstance(rendered, str):
        raise ValueError("message_format")
    if re.search(
        r"\[(?:[^\]\n]{0,90})truncat[^\]\n]*\]|\bresponse (?:was |is )?truncated\b", rendered, re.I
    ):
        raise ValueError("source_truncated")
    result = []
    if operation == "history":
        prefix = rendered.split("=== Message from ", 1)[0]
        if re.findall(r"\(([CDG][A-Z0-9]+)\)", prefix) != [channel]:
            raise ValueError("history_channel_mismatch")
        markers = list(HISTORY.finditer(rendered))
        for i, marker in enumerate(markers):
            stop = markers[i + 1].start() if i + 1 < len(markers) else len(rendered)
            tail = rendered[marker.end() : stop].lstrip("\n")
            stamp = re.match(rf"Message TS: ({TS})\s*\n?", tail)
            if not stamp:
                raise ValueError("history_identity")
            body = tail[stamp.end() :].rstrip("\n")
            replies = re.findall(r"^Thread: (\d+) replies \(last: [^\n]+\)\s*$", body, re.M)
            result.append(
                message(
                    channel,
                    stamp[1],
                    body,
                    marker[1],
                    stamp[1] if replies and int(replies[0]) else None,
                )
            )
        if not markers and ("Message TS:" in rendered or "=== " in rendered):
            raise ValueError("history_unparsed")
        return result
    if operation == "search":
        markers = list(SEARCH.finditer(rendered))
        if not markers and re.fullmatch(
            r"# Search results for:[^\n]*\n\s*No results found\.\s*", rendered, re.I
        ):
            return []
        if not markers and not re.search(r"^## Messages \(0 results\)", rendered, re.M):
            raise ValueError("search_format")
        for i, marker in enumerate(markers):
            stop = markers[i + 1].start() if i + 1 < len(markers) else len(rendered)
            block = rendered[marker.end() : stop]
            delimiter = re.search(r"^Text:[ \t]*", block, re.M)
            if not delimiter:
                raise ValueError("search_text")
            meta, body = block[: delimiter.start()], block[delimiter.end() :]
            cids = re.findall(r"\b[CDG][A-Z0-9]{8,}\b", field(meta, "Channel") or "")
            if len(cids) != 1:
                raise ValueError("search_channel")
            stamp = field(meta, "Message_ts")
            url, root = None, None
            link = field(meta, "Permalink")
            if link:
                parsed = urlsplit(link)
                if (
                    parsed.scheme == "https"
                    and re.fullmatch(
                        r"[a-z0-9-]+\.(?:enterprise\.)?slack\.com", parsed.hostname or ""
                    )
                    and not parsed.username
                    and not parsed.password
                    and not parsed.port
                    and parsed.path == f"/archives/{cids[0]}/p{stamp.replace('.', '')}"
                ):
                    url = link
                    roots = parse_qs(parsed.query).get("thread_ts", [])
                    root = roots[0] if len(roots) == 1 else None
            count = field(meta, "Reply count")
            if root is None and count and count.isdigit() and int(count) > 0:
                root = stamp
            result.append(
                message(
                    cids[0],
                    stamp,
                    re.sub(r"\n---\s*$", "", body).rstrip("\n"),
                    field(meta, "From"),
                    root,
                    url,
                )
            )
        return result
    if operation != "thread" or not rendered.startswith("=== THREAD PARENT MESSAGE ===\n"):
        raise ValueError("thread_format")
    reply_heading = re.search(r"^=== THREAD REPLIES \(\d+ total\) ===\s*$", rendered, re.M)
    parent_end = reply_heading.start() if reply_heading else len(rendered)
    header = HEADER.match(rendered[len("=== THREAD PARENT MESSAGE ===\n") : parent_end])
    if not header or header[3] != parent:
        raise ValueError("thread_parent")
    parent_body = rendered[len("=== THREAD PARENT MESSAGE ===\n") + header.end() : parent_end]
    result.append(message(channel, parent, parent_body.rstrip("\n"), header[1], parent))
    markers = list(REPLY.finditer(rendered))
    for i, marker in enumerate(markers):
        stop = markers[i + 1].start() if i + 1 < len(markers) else len(rendered)
        raw = rendered[marker.end() : stop].lstrip("\n")
        header = HEADER.match(raw)
        if not header:
            raise ValueError("thread_reply")
        result.append(
            message(channel, header[3], raw[header.end() :].rstrip("\n"), header[1], parent)
        )
    return result


def collect(read, start, end, capture, accept, *, progress=None, sources=None):
    began, calls, coverage, targets = time.monotonic(), 0, [], set()
    membership = {}
    complete = True
    rate_limited = False
    checkpoints, dependencies, failed_threads = {}, {}, set()
    progress = progress or {}
    configured = {**{cid: {"mode": "full", "since": None} for cid in FULL}, **(sources or {})}
    full = {cid for cid, value in configured.items() if value["mode"] == "full"}

    def pages(operation, arguments, channel=None, parent=None, mode="full", label="", lower=None):
        nonlocal calls, complete, rate_limited
        cursor, seen = None, set()
        while True:
            if rate_limited:
                raise ValueError("rate_limit_deferred")
            if calls >= MAX_CALLS or time.monotonic() - began > MAX_SECONDS:
                raise ValueError("run_budget")
            args = {**arguments, **({"cursor": cursor} if cursor else {})}
            calls += 1
            try:
                response = read(operation, args)
            except TransportError as error:
                capture(operation, args, {"error_code": str(error)})
                rate_limited = str(error) == "source_rate_limited"
                code = (
                    str(error)
                    if re.fullmatch(r"[a-z_]{1,40}", str(error))
                    else "source_read_failed"
                )
                raise ValueError(code) from error
            reference = capture(operation, args, response)
            if operation == "channels":
                for row in parse_memberships(response):
                    membership[row["channel_id"]] = row
            else:
                for row in parse_messages(response, operation, channel, parent):
                    cid = row["channel_id"]
                    if cid not in membership:
                        raise ValueError("source_scope_mismatch")
                    if configured.get(cid, {}).get("mode") == "off":
                        continue
                    if operation == "search" and mode == "full" and cid != channel:
                        raise ValueError("search_scope_mismatch")
                    if mode == "mentions" and not MENTION.search(row["text"]):
                        continue
                    if mode == "direct" and not membership[cid]["direct"]:
                        raise ValueError("direct_scope_mismatch")
                    if mode != "context" and not (lower or start) <= row["occurred_at"] <= end:
                        continue
                    row["channel_name"] = membership[cid]["channel_name"]
                    accept(reference, row)
                    if operation != "thread" and row["thread_id"]:
                        targets.add((cid, row["thread_id"]))
                        dependencies.setdefault(label, set()).add((cid, row["thread_id"]))
            following = next_cursor(response, operation)
            if following is None:
                return
            if following in seen:
                raise ValueError("cursor_repeated")
            seen.add(following)
            cursor = following

    def scope(label, operation, args, **kwargs):
        nonlocal complete
        try:
            lower = start
            if operation in {"history", "search"} and label.split(":")[0] in configured:
                since = configured[label.split(":")[0]].get("since")
                if since:
                    lower = max(lower, datetime.fromisoformat(since))
            if operation in {"history", "search"} and label in progress:
                confirmed = datetime.fromisoformat(progress[label])
                if confirmed.tzinfo is None or confirmed > end:
                    raise ValueError("invalid_checkpoint")
                lower = max(lower, confirmed - timedelta(hours=1))
            if operation in {"history", "search"}:
                args = {**args, "oldest" if operation == "history" else "after": query_stamp(lower)}
            pages(operation, args, **kwargs, label=label, lower=lower)
            if operation in {"history", "search"}:
                checkpoints[label] = end.isoformat()
            coverage.append({"scope": label, "state": "available_pages_exhausted"})
            return True
        except (ValueError, RuntimeError) as error:
            complete = False
            code = str(error) if re.fullmatch(r"[a-z_]{1,40}", str(error)) else "source_failed"
            coverage.append({"scope": label, "state": "partial", "code": code})
            return False

    scope(
        "joined_channels",
        "channels",
        {"types": "public_channel,private_channel", "format": "full", "limit": 200},
    )
    scope("direct_conversations", "channels", {"types": "im,mpim", "format": "full", "limit": 200})
    if not complete or not full <= membership.keys():
        return {
            "status": "partial",
            "pages": calls,
            "coverage": coverage,
            "error_code": "membership_incomplete",
        }
    low, high = query_stamp(start), query_stamp(end)
    search = {
        "after": low,
        "before": high,
        "include_bots": True,
        "sort": "timestamp",
        "sort_dir": "asc",
        "limit": 20,
        "response_format": "detailed",
        "include_context": False,
        "only_my_channels": True,
        "natural_language_query": "",
    }
    for cid in membership:
        if cid not in full and not membership[cid]["direct"]:
            continue
        scope(
            cid,
            "history",
            {
                "channel_id": cid,
                "oldest": low,
                "latest": high,
                "limit": 100,
                "response_format": "detailed",
            },
            channel=cid,
        )
    for cid in sorted(full):
        scope(cid + ":replies", "search", {**search, "filters": f"in:<#{cid}>"}, channel=cid)
    scope(
        "direct:replies",
        "search",
        {**search, "channel_types": "im,mpim", "filters": "is:dm"},
        mode="direct",
    )
    scope(
        "mentions",
        "search",
        {
            **search,
            "channel_types": "public_channel,private_channel",
            "keywords": [f'"<@{USER_ID}>"'],
        },
        mode="mentions",
    )
    for cid, parent in sorted(targets):
        completed = scope(
            cid + ":thread",
            "thread",
            {"channel_id": cid, "message_ts": parent, "limit": 1000, "response_format": "detailed"},
            channel=cid,
            parent=parent,
            mode="context",
        )
        if not completed:
            failed_threads.add((cid, parent))
    for label, required in dependencies.items():
        if required & failed_threads:
            checkpoints.pop(label, None)
    return {
        "status": "succeeded" if complete else "partial",
        "pages": calls,
        "coverage": coverage,
        "error_code": None if complete else "coverage_partial",
        "progress": checkpoints,
    }
