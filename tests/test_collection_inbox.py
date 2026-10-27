from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from efren_bot.collection.inbox import AnnotationInput, InboxService, ListInput
from efren_bot.collection.models import CollectionCapture, CollectionMessage, CollectionRun

pytestmark = pytest.mark.integration


def seed(sessions, count=65):
    now = datetime.now(UTC)
    with sessions.begin() as s:
        run = CollectionRun(
            id=uuid4(),
            trigger="manual",
            status="partial",
            created_at=now,
            window_start=now,
            window_end=now,
            coverage=[],
            added_count=0,
            page_count=0,
        )
        s.add(run)
        s.flush()
        capture = CollectionCapture(
            id=uuid4(),
            run_id=run.id,
            operation="history",
            arguments={},
            response={},
            observed_at=now,
        )
        s.add(capture)
        s.flush()
        rows = []
        for i in range(count):
            row = CollectionMessage(
                id=uuid4(),
                capture_id=capture.id,
                source_scope="synthetic",
                channel_id="C08MAH1JNC8",
                channel_name="devs",
                message_id=f"synthetic-{i}",
                thread_id="root" if i < 3 else None,
                actor_id="synthetic-author",
                text=f"message {i}",
                occurred_at=now - timedelta(minutes=i),
                observed_at=now,
                sha256=f"{i:064x}",
                is_historical=i % 2 == 0,
                provenance={},
            )
            s.add(row)
            rows.append(row.id)
        s.flush()
        original = s.get(CollectionMessage, rows[0])
        duplicate = CollectionMessage(
            **{
                col.name: getattr(original, col.name)
                for col in original.__table__.columns
                if col.name not in {"id", "sha256", "observed_at", "text"}
            },
            id=uuid4(),
            sha256="f" * 64,
            text="second representation",
            observed_at=now + timedelta(microseconds=1),
        )
        s.add(duplicate)
    return rows


def test_all_logical_messages_paginate_without_variants_becoming_new(database):
    seed(database)
    service = InboxService(database)
    first = service.list(ListInput())
    assert first["total"] == 65
    assert len(first["messages"]) == 50
    second = service.list(ListInput(offset=first["next_offset"], snapshot_at=first["snapshot_at"]))
    assert len(second["messages"]) == 15
    assert second["next_offset"] is None
    assert not (
        {r["message_id"] for r in first["messages"]} & {r["message_id"] for r in second["messages"]}
    )
    assert first["messages"][0]["variant_count"] == 2
    assert not first["messages"][0]["is_new"]


def test_review_attention_and_category_are_independent_persistent_annotations(database):
    ids = seed(database, 3)
    service = InboxService(database)
    service.annotate(
        AnnotationInput(id=ids[1], reviewed=True, attention="required", category="support")
    )
    rows = service.list(ListInput(review="reviewed"))["messages"]
    assert len(rows) == 1 and not rows[0]["is_new"]
    assert rows[0]["attention"] == "required" and rows[0]["category"] == "support"
    service.annotate(AnnotationInput(id=ids[1], category="information"))
    assert service.list(ListInput(attention="required"))["messages"][0]["reviewed"]
    with database() as s:
        assert s.scalar(select(func.count()).select_from(CollectionMessage)) == 4


def test_thread_order_and_variants_are_reachable(database):
    ids = seed(database, 3)
    service = InboxService(database)
    result = service.thread(ids[1], 0)
    assert len(result["messages"]) == 3
    assert [r["occurred_at"] for r in result["messages"]] == sorted(
        r["occurred_at"] for r in result["messages"]
    )
    assert len(service.variants(ids[0], 0)["messages"]) == 2


def test_paging_snapshot_excludes_late_import_even_with_old_observation(database):
    ids = seed(database, 3)
    service = InboxService(database)
    first = service.list(ListInput())
    with database.begin() as s:
        original = s.get(CollectionMessage, ids[0])
        values = {
            col.name: getattr(original, col.name)
            for col in original.__table__.columns
            if col.name not in {"id", "message_id", "stored_at"}
        }
        s.add(CollectionMessage(**values, id=uuid4(), message_id="late-import"))
    assert service.list(ListInput(snapshot_at=first["snapshot_at"]))["total"] == 3
    assert service.list(ListInput())["total"] == 4


def test_search_and_filters_do_not_treat_wildcards_as_everything(database):
    seed(database, 3)
    service = InboxService(database)
    assert service.list(ListInput(query="%"))["total"] == 0
    assert service.list(ListInput(review="new"))["total"] == 1
    assert service.list(ListInput(origin="historical"))["total"] == 2
