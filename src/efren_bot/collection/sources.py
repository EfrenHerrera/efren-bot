from datetime import UTC, datetime
from typing import Literal

from pydantic import Field
from sqlalchemy import select

from efren_bot.collection.inbox import Closed
from efren_bot.collection.models import CollectionCapture
from efren_bot.collection.reader import FULL, parse_memberships
from efren_bot.collection.service import CollectionError, CollectionService


class SourceInput(Closed):
    channel_id: str = Field(pattern=r"^[CG][A-Z0-9]{8,}$", max_length=200)
    mode: Literal["full", "mentions", "off"]


def effective_sources(overrides):
    return {
        **{
            cid: {"channel_name": name, "mode": "full", "since": None} for cid, name in FULL.items()
        },
        **overrides,
    }


class SourceService:
    def __init__(self, sessions):
        self.sessions = sessions

    def catalog(self, session):
        captures = session.scalars(
            select(CollectionCapture)
            .where(CollectionCapture.operation == "channels")
            .order_by(CollectionCapture.observed_at.desc())
            .limit(20)
        ).all()
        channels = {}
        observed = None
        # Only the newest run's membership pages; an earlier membership is not permission proof.
        run_id = captures[0].run_id if captures else None
        for capture in captures:
            if capture.run_id != run_id:
                continue
            if "error_code" in capture.response:
                continue
            try:
                members = parse_memberships(capture.response)
            except ValueError:
                continue
            observed = max(observed, capture.observed_at) if observed else capture.observed_at
            for member in members:
                if not member["direct"]:
                    channels[member["channel_id"]] = member
        return channels, observed

    def list(self):
        with self.sessions.begin() as s:
            control = CollectionService(self.sessions).control(s)
            configured = effective_sources(control.sources)
            channels, observed = self.catalog(s)
            for cid, value in configured.items():
                channels.setdefault(
                    cid,
                    {"channel_id": cid, "channel_name": value["channel_name"], "unavailable": True},
                )
            return {
                "observed_at": observed,
                "channels": [
                    {
                        "channel_id": cid,
                        "channel_name": value["channel_name"],
                        "available": not value.get("unavailable", False),
                        "mode": configured.get(cid, {}).get("mode", "mentions"),
                        "since": configured.get(cid, {}).get("since"),
                    }
                    for cid, value in sorted(
                        channels.items(), key=lambda pair: pair[1]["channel_name"]
                    )
                ],
            }

    def save(self, data: SourceInput):
        with self.sessions.begin() as s:
            control = CollectionService(self.sessions).control(s)
            channels, _ = self.catalog(s)
            current = effective_sources(control.sources)
            if data.channel_id not in channels and not (
                data.mode == "off" and data.channel_id in current
            ):
                raise CollectionError("channel_not_available", 409)
            previous = current.get(data.channel_id, {"mode": "mentions", "since": None})
            channel = channels.get(data.channel_id, current.get(data.channel_id))
            since = previous.get("since")
            if data.mode == "full" and previous["mode"] != "full":
                since = datetime.now(UTC).isoformat()
            control.sources = {
                **control.sources,
                data.channel_id: {
                    "channel_name": channel["channel_name"],
                    "mode": data.mode,
                    "since": since,
                },
            }
        return {"saved": True}
