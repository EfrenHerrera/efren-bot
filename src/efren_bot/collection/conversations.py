from collections import defaultdict
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from efren_bot.collection.inbox import ATTENTION, CATEGORY, PAGE_SIZE, Closed, logical, present
from efren_bot.collection.models import (
    CollectionConversationSeen,
    CollectionFollowup,
    CollectionFollowupMessage,
    CollectionMessage,
)
from efren_bot.collection.reader import MENTION
from efren_bot.collection.service import CollectionError, view
from efren_bot.collection.transport import USER_ID


class ConversationList(Closed):
    offset: int = Field(default=0, ge=0, le=1000000, strict=True)
    snapshot_at: AwareDatetime | None = None
    channel_id: str = Field(default="", max_length=200)
    query: str = Field(default="", max_length=200)
    view: Literal["all", "mentions", "following", "new"] = "all"
    category: CATEGORY | None = None
    attention: ATTENTION | None = None


class ConversationDetail(Closed):
    id: UUID
    offset: int = Field(default=0, ge=0, le=1000000, strict=True)
    snapshot_at: AwareDatetime | None = None


class ConversationSeen(Closed):
    id: UUID
    snapshot_at: AwareDatetime


class GroupSave(Closed):
    conversation_message_id: UUID
    request_id: UUID
    id: UUID | None = None
    revision: int | None = Field(default=None, ge=1, strict=True)
    title: str = Field(min_length=1, max_length=200)
    category: CATEGORY = "unclassified"
    attention: ATTENTION = "undecided"
    message_ids: list[UUID] = Field(default_factory=list, max_length=200)

    @field_validator("title")
    @classmethod
    def nonblank(cls, value):
        if not value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError("invalid title")
        return value.strip()


class GroupDelete(Closed):
    id: UUID
    revision: int = Field(ge=1, strict=True)


def identity(row):
    return row["source_scope"], row["channel_id"], row["message_id"]


def snapshot_time(value=None):
    now = datetime.now(UTC)
    if value is not None and value > now:
        raise CollectionError("invalid_snapshot", 422)
    return value or now


class ConversationService:
    def __init__(self, sessions):
        self.sessions = sessions

    def load(self, s, snapshot):
        rows = [present(r) for r in s.execute(select(logical(snapshot))).mappings()]
        evidence = defaultdict(
            lambda: {"roots": set(), "mentions": [], "texts": [], "first_stored_at": None}
        )
        for row in s.execute(
            select(
                CollectionMessage.source_scope,
                CollectionMessage.channel_id,
                CollectionMessage.message_id,
                CollectionMessage.thread_id,
                CollectionMessage.text,
                CollectionMessage.stored_at,
            ).where(CollectionMessage.stored_at <= snapshot)
        ).mappings():
            data = evidence[identity(row)]
            if row["thread_id"]:
                data["roots"].add(row["thread_id"])
            if MENTION.search(row["text"]):
                data["mentions"].append(row["text"])
            data["texts"].append(row["text"])
            data["first_stored_at"] = (
                min(data["first_stored_at"], row["stored_at"])
                if data["first_stored_at"]
                else row["stored_at"]
            )
        buckets = defaultdict(list)
        lookup = {}
        for row in rows:
            data = evidence[identity(row)]
            roots = data["roots"]
            root = next(iter(roots)) if len(roots) == 1 else row["message_id"]
            key = (row["source_scope"], row["channel_id"], root, len(roots) > 1)
            row["mentions_me"] = bool(data["mentions"])
            row["mention_excerpt"] = data["mentions"][0] if data["mentions"] else None
            buckets[key].append(row)
            lookup[identity(row)] = key
        saved = s.scalars(
            select(CollectionFollowup).order_by(
                CollectionFollowup.created_at, CollectionFollowup.id
            )
        ).all()
        group_messages = defaultdict(list)
        for followup_id, message_id in s.execute(
            select(CollectionFollowupMessage.followup_id, CollectionFollowupMessage.message_id)
        ):
            group_messages[followup_id].append(message_id)
        attached = defaultdict(list)
        for group in saved:
            key = lookup.get((group.source_scope, group.channel_id, group.anchor_message_id))
            if key:
                members = {r["message_id"]: r for r in buckets[key]}
                attached[key].append(
                    {
                        **view(group),
                        "message_ids": [
                            members[mid]["id"] for mid in group_messages[group.id] if mid in members
                        ],
                        "evidence_count": len(group_messages[group.id]),
                        "all_context": not group_messages[group.id],
                    }
                )
        seen = {
            (r.source_scope, r.channel_id, r.conversation_id, r.conflicting): r.seen_through
            for r in s.scalars(select(CollectionConversationSeen))
        }
        result = {}
        for key, members in buckets.items():
            members.sort(key=lambda row: (row["occurred_at"], row["message_id"]))
            root = next((row for row in members if row["message_id"] == key[2]), None)
            anchor = root or members[0]
            mentions = [r for r in members if r["mentions_me"]]
            new_count = sum(
                not r["historical"]
                and (key not in seen or evidence[identity(r)]["first_stored_at"] > seen[key])
                for r in members
            )
            related = any(evidence[identity(r)]["roots"] for r in members)
            result[key] = {
                "id": anchor["id"],
                "conversation_id": key[2],
                "source_scope": key[0],
                "channel_id": key[1],
                "channel_name": anchor["channel_name"],
                "preview": (root or anchor)["text"][:600],
                "root_present": root is not None,
                "relation_status": "conflict" if key[3] else "confirmed" if related else "unlinked",
                "message_count": len(members),
                "mention_count": len(mentions),
                "new_count": new_count,
                "group_count": len(attached[key]),
                "last_activity_at": members[-1]["occurred_at"],
                "mention_previews": [
                    {"id": r["id"], "excerpt": r["mention_excerpt"][:600]} for r in mentions[:3]
                ],
                "groups": attached[key],
                "root": root,
                "_members": members,
                "_search": "\n".join(
                    text for row in members for text in evidence[identity(row)]["texts"]
                ).casefold(),
            }
        return result, lookup

    def public(self, conversation):
        return {key: value for key, value in conversation.items() if not key.startswith("_")}

    def selected(self, s, data, snapshot):
        message = s.get(CollectionMessage, data.id)
        if message is None:
            raise CollectionError("message_not_found", 404)
        conversations, lookup = self.load(s, snapshot)
        key = lookup.get((message.source_scope, message.channel_id, message.message_id))
        if key is None:
            raise CollectionError("message_not_in_snapshot", 409)
        return key, conversations[key]

    def list(self, params: ConversationList):
        snapshot = snapshot_time(params.snapshot_at)
        with self.sessions() as s:
            all_conversations, _ = self.load(s, snapshot)
        found = []
        for row in all_conversations.values():
            if params.channel_id and row["channel_id"] != params.channel_id:
                continue
            if params.query.strip().casefold() not in row["_search"]:
                continue
            if params.view == "mentions" and not row["mention_count"]:
                continue
            if params.view == "following" and not row["group_count"]:
                continue
            if params.view == "new" and not row["new_count"]:
                continue
            if (params.category or params.attention) and not any(
                (not params.category or group["category"] == params.category)
                and (not params.attention or group["attention"] == params.attention)
                for group in row["groups"]
            ):
                continue
            found.append(row)
        found.sort(
            key=lambda r: (
                r["last_activity_at"],
                r["source_scope"],
                r["channel_id"],
                r["conversation_id"],
                r["relation_status"],
            ),
            reverse=True,
        )
        page = found[params.offset : params.offset + PAGE_SIZE]
        channels = sorted(
            {(r["channel_id"], r["channel_name"]) for r in all_conversations.values()},
            key=lambda pair: pair[1],
        )
        return {
            "conversations": [
                {k: v for k, v in self.public(row).items() if k not in {"root", "groups"}}
                for row in page
            ],
            "total": len(found),
            "snapshot_at": snapshot,
            "offset": params.offset,
            "next_offset": params.offset + len(page)
            if params.offset + len(page) < len(found)
            else None,
            "channels": [{"channel_id": cid, "channel_name": name} for cid, name in channels],
        }

    def detail(self, data: ConversationDetail):
        snapshot = snapshot_time(data.snapshot_at)
        with self.sessions() as s:
            _, conversation = self.selected(s, data, snapshot)
        members = conversation["_members"]
        page = members[data.offset : data.offset + PAGE_SIZE]
        return {
            "self_user_id": USER_ID,
            "conversation": {k: v for k, v in self.public(conversation).items() if k != "groups"},
            "groups": conversation["groups"],
            "messages": page,
            "total": len(members),
            "offset": data.offset,
            "snapshot_at": snapshot,
            "mention_locations": [
                {
                    "id": r["id"],
                    "offset": index // PAGE_SIZE * PAGE_SIZE,
                    "excerpt": r["mention_excerpt"][:600],
                }
                for index, r in enumerate(members)
                if r["mentions_me"]
            ],
            "next_offset": data.offset + len(page)
            if data.offset + len(page) < len(members)
            else None,
        }

    def seen(self, data: ConversationSeen):
        snapshot = snapshot_time(data.snapshot_at)
        with self.sessions.begin() as s:
            key, _ = self.selected(s, data, snapshot)
            values = dict(
                zip(
                    ("source_scope", "channel_id", "conversation_id", "conflicting"),
                    key,
                    strict=True,
                )
            )
            s.execute(
                insert(CollectionConversationSeen)
                .values(**values, seen_through=snapshot)
                .on_conflict_do_update(
                    index_elements=[
                        CollectionConversationSeen.source_scope,
                        CollectionConversationSeen.channel_id,
                        CollectionConversationSeen.conversation_id,
                        CollectionConversationSeen.conflicting,
                    ],
                    set_={
                        "seen_through": func.greatest(
                            CollectionConversationSeen.seen_through, snapshot
                        )
                    },
                )
            )
        return {"saved": True}

    def save_group(self, data: GroupSave):
        with self.sessions.begin() as s:
            key, conversation = self.selected(
                s, ConversationDetail(id=data.conversation_message_id), datetime.now(UTC)
            )
            member_keys = {r["message_id"] for r in conversation["_members"]}
            selected = set()
            for identifier in data.message_ids:
                message = s.get(CollectionMessage, identifier)
                if (
                    message is None
                    or message.source_scope != key[0]
                    or message.channel_id != key[1]
                    or message.message_id not in member_keys
                ):
                    raise CollectionError("evidence_outside_conversation", 422)
                selected.add(message.message_id)
            values = {"title": data.title, "category": data.category, "attention": data.attention}
            now = datetime.now(UTC)
            if data.id:
                group = s.scalar(
                    select(CollectionFollowup)
                    .where(CollectionFollowup.id == data.id)
                    .with_for_update()
                )
                if group is None:
                    raise CollectionError("group_not_found", 404)
                if (group.source_scope, group.channel_id, group.anchor_message_id) not in {
                    (key[0], key[1], mid) for mid in member_keys
                }:
                    raise CollectionError("group_outside_conversation", 422)
                if data.revision != group.revision:
                    raise CollectionError("group_changed", 409)
                existing_evidence = set(
                    s.scalars(
                        select(CollectionFollowupMessage.message_id).where(
                            CollectionFollowupMessage.followup_id == group.id
                        )
                    )
                )
                if not existing_evidence <= member_keys:
                    raise CollectionError("group_evidence_changed", 409)
                for name, value in values.items():
                    setattr(group, name, value)
                group.revision += 1
                group.updated_at = now
                s.execute(
                    delete(CollectionFollowupMessage).where(
                        CollectionFollowupMessage.followup_id == group.id
                    )
                )
            else:
                anchor = next(r for r in conversation["_members"] if r["id"] == conversation["id"])
                created = s.scalar(
                    insert(CollectionFollowup)
                    .values(
                        request_id=data.request_id,
                        source_scope=key[0],
                        channel_id=key[1],
                        anchor_message_id=anchor["message_id"],
                        **values,
                        revision=1,
                        created_at=now,
                        updated_at=now,
                    )
                    .on_conflict_do_nothing(index_elements=[CollectionFollowup.request_id])
                    .returning(CollectionFollowup.id)
                )
                if created is None:
                    group = s.scalar(
                        select(CollectionFollowup).where(
                            CollectionFollowup.request_id == data.request_id
                        )
                    )
                    previous = set(
                        s.scalars(
                            select(CollectionFollowupMessage.message_id).where(
                                CollectionFollowupMessage.followup_id == group.id
                            )
                        )
                    )
                    if (
                        any(getattr(group, k) != v for k, v in values.items())
                        or previous != selected
                        or (group.source_scope, group.channel_id, group.anchor_message_id)
                        != (key[0], key[1], anchor["message_id"])
                    ):
                        raise CollectionError("group_request_conflict", 409)
                    return {"id": group.id, "revision": group.revision}
                group = s.get(CollectionFollowup, created)
            for mid in sorted(selected):
                s.add(CollectionFollowupMessage(followup_id=group.id, message_id=mid))
            s.flush()
            return {"id": group.id, "revision": group.revision}

    def delete_group(self, data: GroupDelete):
        with self.sessions.begin() as s:
            group = s.scalar(
                select(CollectionFollowup).where(CollectionFollowup.id == data.id).with_for_update()
            )
            if group is None:
                raise CollectionError("group_not_found", 404)
            if group.revision != data.revision:
                raise CollectionError("group_changed", 409)
            s.execute(
                delete(CollectionFollowupMessage).where(
                    CollectionFollowupMessage.followup_id == group.id
                )
            )
            s.delete(group)
        return {"deleted": True}
