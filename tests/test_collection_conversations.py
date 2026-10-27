from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from efren_bot.collection.conversations import (
    ConversationDetail,
    ConversationList,
    ConversationSeen,
    ConversationService,
    GroupDelete,
    GroupSave,
)
from efren_bot.collection.models import CollectionCapture, CollectionMessage, CollectionRun
from efren_bot.collection.service import CollectionError
from efren_bot.collection.transport import USER_ID

pytestmark = pytest.mark.integration


@pytest.fixture
def conversation(database):
    now = datetime.now(UTC)
    ids = []
    with database.begin() as s:
        run = CollectionRun(
            id=uuid4(),
            trigger="manual",
            status="partial",
            created_at=now,
            window_start=now,
            window_end=now,
            coverage=[],
            page_count=0,
            added_count=0,
        )
        s.add(run)
        s.flush()
        cap = CollectionCapture(
            id=uuid4(),
            run_id=run.id,
            operation="history",
            arguments={},
            response={},
            observed_at=now,
        )
        s.add(cap)
        s.flush()
        for i in range(60):
            row = CollectionMessage(
                id=uuid4(),
                capture_id=cap.id,
                source_scope="synthetic",
                channel_id="C1234567890",
                channel_name="channel",
                message_id="root" if i == 0 else f"reply-{i}",
                thread_id=None if i == 0 else "root",
                actor_id="synthetic-author",
                text=f"<@{USER_ID}> request inside reply"
                if i == 55
                else "root request"
                if i == 0
                else "gracias",
                occurred_at=now + timedelta(seconds=i),
                observed_at=now,
                sha256=f"{i:064x}",
                is_historical=True,
            )
            s.add(row)
            ids.append(row.id)
        s.flush()
        old = s.get(CollectionMessage, ids[55])
        s.add(
            CollectionMessage(
                **{
                    c.name: getattr(old, c.name)
                    for c in old.__table__.columns
                    if c.name not in {"id", "text", "thread_id", "sha256", "observed_at"}
                },
                id=uuid4(),
                text="representation without mention",
                thread_id=None,
                sha256="f" * 64,
                observed_at=now + timedelta(seconds=1),
            )
        )
        for cid, mid in [("C1234567890", "orphan"), ("C9999999999", "root")]:
            s.add(
                CollectionMessage(
                    id=uuid4(),
                    capture_id=cap.id,
                    source_scope="synthetic",
                    channel_id=cid,
                    channel_name="other",
                    message_id=mid,
                    thread_id=None,
                    actor_id=None,
                    text="unrelated",
                    occurred_at=now,
                    observed_at=now,
                    sha256="d" * 64,
                    is_historical=True,
                )
            )
    return ConversationService(database), ids


def test_groups_replies_and_finds_mentions_beyond_first_page_and_latest_variant(conversation):
    service, ids = conversation
    result = service.list(ConversationList(view="mentions"))
    assert result["total"] == 1
    item = result["conversations"][0]
    assert item["message_count"] == 60 and item["root_present"]
    assert item["mention_count"] == 1 and item["preview"] == "root request"
    assert item["group_count"] == 0
    assert service.list(ConversationList())["total"] == 3
    first = service.detail(ConversationDetail(id=ids[0]))
    assert len(first["messages"]) == 50 and first["next_offset"] == 50
    second = service.detail(
        ConversationDetail(id=ids[0], offset=50, snapshot_at=first["snapshot_at"])
    )
    assert any(m["mentions_me"] for m in second["messages"])
    assert all(m["message_id"] != "orphan" for m in first["messages"] + second["messages"])


def test_optional_manual_groups_split_without_classifying_every_comment(conversation, database):
    service, ids = conversation
    groups = []
    for title, selected in [
        ("Whole conversation", []),
        ("First request", [ids[1]]),
        ("Second request", [ids[55]]),
    ]:
        request = GroupSave(
            conversation_message_id=ids[0],
            request_id=uuid4(),
            title=title,
            message_ids=selected,
            category="support",
            attention="required",
        )
        saved = service.save_group(request)
        assert service.save_group(request)["id"] == saved["id"]
        groups.append(saved)
    detail = service.detail(ConversationDetail(id=ids[0]))
    assert len(detail["groups"]) == 3
    assert service.list(ConversationList(view="following"))["total"] == 1
    service.delete_group(GroupDelete(id=groups[0]["id"], revision=groups[0]["revision"]))
    assert len(service.detail(ConversationDetail(id=ids[0]))["groups"]) == 2
    with database() as s:
        assert s.scalar(select(func.count()).select_from(CollectionMessage)) == 63


def test_group_evidence_is_conversation_scoped_and_edits_detect_conflicts(conversation):
    service, ids = conversation
    other = next(
        c
        for c in service.list(ConversationList())["conversations"]
        if c["conversation_id"] == "orphan"
    )
    with pytest.raises(CollectionError):
        service.save_group(
            GroupSave(
                conversation_message_id=ids[0],
                request_id=uuid4(),
                title="bad",
                message_ids=[other["id"]],
            )
        )
    request = GroupSave(conversation_message_id=ids[0], request_id=uuid4(), title="original")
    saved = service.save_group(request)
    with pytest.raises(CollectionError):
        service.save_group(
            request.model_copy(update={"title": "different title with same request id"})
        )
    changed = service.save_group(
        GroupSave(
            conversation_message_id=ids[0],
            request_id=uuid4(),
            id=saved["id"],
            revision=1,
            title="revised",
        )
    )
    assert changed["revision"] == 2
    with pytest.raises(CollectionError):
        service.save_group(
            GroupSave(
                conversation_message_id=ids[0],
                request_id=uuid4(),
                id=saved["id"],
                revision=1,
                title="stale",
            )
        )


def test_missing_root_is_explicit_and_ambiguous_relations_are_not_merged(conversation, database):
    service, ids = conversation
    with database.begin() as s:
        root = s.get(CollectionMessage, ids[0])
        root.message_id = "root-not-the-same"
    target = next(r for r in service.list(ConversationList(view="mentions"))["conversations"])
    assert not target["root_present"] and target["message_count"] == 59
    with database.begin() as s:
        old = s.get(CollectionMessage, ids[1])
        s.add(
            CollectionMessage(
                **{
                    c.name: getattr(old, c.name)
                    for c in old.__table__.columns
                    if c.name not in {"id", "thread_id", "sha256"}
                },
                id=uuid4(),
                thread_id="another-root",
                sha256="e" * 64,
            )
        )
    rows = service.list(ConversationList())["conversations"]
    conflicts = [row for row in rows if row["relation_status"] == "conflict"]
    assert len(conflicts) == 1 and conflicts[0]["message_count"] == 1


def test_new_activity_is_not_a_task_and_seen_does_not_hide_future_replies(conversation, database):
    service, ids = conversation
    with database.begin() as s:
        s.get(CollectionMessage, ids[2]).is_historical = False
    assert service.list(ConversationList(view="new"))["total"] == 1
    detail = service.detail(ConversationDetail(id=ids[0]))
    service.seen(ConversationSeen(id=ids[0], snapshot_at=detail["snapshot_at"]))
    assert service.list(ConversationList(view="new"))["total"] == 0
    with database.begin() as s:
        old = s.get(CollectionMessage, ids[2])
        values = {
            c.name: getattr(old, c.name)
            for c in old.__table__.columns
            if c.name not in {"id", "message_id", "stored_at"}
        }
        s.add(CollectionMessage(**values, id=uuid4(), message_id="new-thanks"))
    fresh = service.list(ConversationList(view="new"))["conversations"][0]
    assert fresh["new_count"] == 1 and fresh["group_count"] == 0
