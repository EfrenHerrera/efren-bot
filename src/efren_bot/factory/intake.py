"""The funnel's mouth: every source normalizes to one ``IntakeItem``.

Adding a source means writing one adapter: pull sources implement ``fetch``, push sources
implement ``parse``. Nothing here decides whether an item is work; that is triage's job.
Real network access is opt-in per adapter and absent from the default wiring.
"""

import hashlib
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


class IntakeItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_kind: str = Field(min_length=1, max_length=30)
    external_id: str = Field(min_length=1, max_length=300)
    title: str = Field(default="", max_length=300)
    text: str = Field(max_length=20000)
    author: str | None = Field(default=None, max_length=200)
    url: str | None = Field(default=None, max_length=2048)
    occurred_at: datetime
    # Source facts triage may use (flags, project hints, status). Never executed.
    attrs: dict[str, Any] = Field(default_factory=dict)

    def fingerprint(self) -> str:
        """Identity of this exact version of this exact request."""
        canon = json.dumps(
            [self.source_kind, self.external_id, self.title.strip(), self.text.strip()],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(canon.encode()).hexdigest()


class PullAdapter(Protocol):
    kind: str

    def fetch(self, since: datetime | None) -> list[IntakeItem]: ...


class PushAdapter(Protocol):
    kind: str

    def parse(self, payload: dict) -> list[IntakeItem]: ...


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class FixtureAdapter:
    """Replays canned items; the default mock for every rehearsal."""

    kind = "fixture"

    def __init__(self, items: list[IntakeItem]):
        self._items = items

    def fetch(self, since: datetime | None) -> list[IntakeItem]:
        return [i for i in self._items if since is None or _aware(i.occurred_at) > _aware(since)]

    def parse(self, payload: dict) -> list[IntakeItem]:
        return [IntakeItem.model_validate(payload)]


# ---------------------------------------------------------------- Notion


class NotionClient(Protocol):
    def query_tasks(self, since: datetime | None) -> list[dict]: ...

    def update_status(self, page_id: str, status: str) -> dict: ...


class MockNotionClient:
    """Serves recorded page objects in Notion's API shape; records status updates."""

    def __init__(self, pages: list[dict]):
        self.pages = pages
        self.updates: list[tuple[str, str]] = []

    def query_tasks(self, since: datetime | None) -> list[dict]:
        return list(self.pages)

    def update_status(self, page_id: str, status: str) -> dict:
        self.updates.append((page_id, status))
        return {"id": page_id, "status": status}


class NotionHttpClient:
    """Official Notion REST API. Opt-in: needs a token and a database id from the host."""

    BASE = "https://api.notion.com/v1"
    VERSION = "2022-06-28"

    def __init__(
        self,
        token: str,
        database_id: str,
        *,
        status_property: str = "Status",
        opener: Callable | None = None,
    ):
        if not token or not database_id:
            raise ValueError("Notion needs a token and a database id")
        self._token = token
        self._database_id = database_id
        self._status_property = status_property
        self._opener = opener

    def _call(self, method: str, path: str, body: dict | None) -> dict:
        import urllib.request

        request = urllib.request.Request(  # noqa: S310 - fixed https base
            self.BASE + path,
            data=json.dumps(body).encode() if body is not None else None,
            method=method,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Notion-Version": self.VERSION,
                "Content-Type": "application/json",
            },
        )
        opener = self._opener or urllib.request.urlopen
        with opener(request, timeout=20) as response:  # noqa: S310
            return json.loads(response.read())

    def query_tasks(self, since: datetime | None) -> list[dict]:
        body: dict = {"page_size": 50}
        if since is not None:
            body["filter"] = {
                "timestamp": "last_edited_time",
                "last_edited_time": {"on_or_after": _aware(since).isoformat()},
            }
        pages: list[dict] = []
        for _ in range(10):  # bounded pagination
            data = self._call("POST", f"/databases/{self._database_id}/query", body)
            pages.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            body["start_cursor"] = data["next_cursor"]
        return pages

    def update_status(self, page_id: str, status: str) -> dict:
        body = {"properties": {self._status_property: {"status": {"name": status}}}}
        return self._call("PATCH", f"/pages/{page_id}", body)


def _plain(prop: dict | None) -> str:
    if not prop:
        return ""
    for key in ("title", "rich_text"):
        if key in prop:
            return "".join(part.get("plain_text", "") for part in prop[key])
    if "status" in prop and prop["status"]:
        return prop["status"].get("name", "")
    if "select" in prop and prop["select"]:
        return prop["select"].get("name", "")
    return ""


class NotionAdapter:
    """Planned work: pages of a task database, normalized, never inferred from chat.

    Property names are configurable because every workspace names them differently.
    """

    kind = "notion"

    def __init__(
        self,
        client: NotionClient,
        *,
        title_property: str = "Name",
        description_property: str = "Description",
        status_property: str = "Status",
        project_property: str = "Project",
        key_property: str = "Key",
        ready_statuses: tuple[str, ...] = ("Ready", "To do", "Todo", "Planned"),
    ):
        self._client = client
        self._props = (
            title_property,
            description_property,
            status_property,
            project_property,
            key_property,
        )
        self._ready = {s.lower() for s in ready_statuses}

    def fetch(self, since: datetime | None) -> list[IntakeItem]:
        title_p, desc_p, status_p, project_p, key_p = self._props
        items: list[IntakeItem] = []
        for page in self._client.query_tasks(since):
            properties = page.get("properties", {})
            status = _plain(properties.get(status_p))
            title = _plain(properties.get(title_p))
            if not title:
                continue
            description = _plain(properties.get(desc_p))
            items.append(
                IntakeItem(
                    source_kind=self.kind,
                    external_id=page["id"],
                    title=title,
                    text=(f"{title}\n\n{description}" if description else title),
                    url=page.get("url"),
                    occurred_at=page.get("last_edited_time") or datetime.now(UTC),
                    attrs={
                        "status": status,
                        "ready": status.lower() in self._ready,
                        "project_hint": _plain(properties.get(project_p)) or None,
                        "business_key": _plain(properties.get(key_p)) or None,
                    },
                )
            )
        return items


# ---------------------------------------------------------------- WhatsApp


class WhatsAppAdapter:
    """Push source: normalizes Meta WhatsApp Cloud API webhook payloads (text messages).

    Only the documented ``entry[].changes[].value.messages[]`` text shape is read. Verifying
    the webhook signature belongs to the HTTP edge, not here.
    """

    kind = "whatsapp"

    def parse(self, payload: dict) -> list[IntakeItem]:
        items: list[IntakeItem] = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                names = {
                    c.get("wa_id"): c.get("profile", {}).get("name")
                    for c in value.get("contacts", [])
                }
                for message in value.get("messages", []):
                    if message.get("type") != "text":
                        continue  # media and reactions are not requests
                    stamp = int(message.get("timestamp", "0") or 0)
                    sender = message.get("from", "")
                    body = message.get("text", {}).get("body", "")
                    if not body.strip():
                        continue
                    items.append(
                        IntakeItem(
                            source_kind=self.kind,
                            external_id=message["id"],
                            text=body,
                            author=names.get(sender) or sender or None,
                            occurred_at=datetime.fromtimestamp(stamp, UTC),
                            attrs={"from": sender, "human_flagged": False},
                        )
                    )
        return items


# ---------------------------------------------------------------- Slack


class SlackCollectionAdapter:
    """Reads what the existing collector already stored; never calls Slack itself.

    Only messages a human marked ``attention = required`` become candidates: a mention is
    not an assignment. The adapter takes a query callable so it stays DB-agnostic in tests.
    """

    kind = "slack"

    def __init__(self, query: Callable[[datetime | None], list[dict]]):
        self._query = query

    def fetch(self, since: datetime | None) -> list[IntakeItem]:
        items: list[IntakeItem] = []
        for row in self._query(since):
            text = (row.get("text") or "").strip()
            if not text:
                continue
            items.append(
                IntakeItem(
                    source_kind=self.kind,
                    external_id=f"{row['channel_id']}:{row['message_id']}",
                    text=text,
                    author=row.get("actor_id"),
                    url=row.get("source_url"),
                    occurred_at=row["occurred_at"],
                    attrs={
                        "channel": row.get("channel_name"),
                        "thread_id": row.get("thread_id"),
                        "human_flagged": row.get("attention") == "required",
                        "category": row.get("category"),
                    },
                )
            )
        return items


_WS = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    return _WS.sub(" ", value).strip().lower()
