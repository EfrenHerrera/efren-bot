from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert

from efren_bot.collection.models import CollectionAnnotation as A
from efren_bot.collection.models import CollectionMessage as M
from efren_bot.collection.service import CollectionError, view

CATEGORY = Literal["unclassified", "support", "code_review", "coordination", "information"]
ATTENTION = Literal["undecided", "required", "not_required"]
PAGE_SIZE = 50


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListInput(Closed):
    offset: int = Field(default=0, ge=0, le=1000000, strict=True)
    snapshot_at: AwareDatetime | None = None
    channel_id: str = Field(default="", max_length=200)
    query: str = Field(default="", max_length=200)
    review: Literal["all", "new", "unreviewed", "reviewed"] = "all"
    origin: Literal["all", "historical", "live"] = "all"
    category: CATEGORY | None = None
    attention: ATTENTION | None = None


class AnnotationInput(Closed):
    id: UUID
    reviewed: StrictBool | None = None
    category: CATEGORY | None = None
    attention: ATTENTION | None = None


class DetailInput(Closed):
    id: UUID
    offset: int = Field(default=0, ge=0, le=1000000, strict=True)


def logical(snapshot):
    identity = [M.source_scope, M.channel_id, M.message_id]
    ranked = (
        select(
            M,
            func.row_number()
            .over(partition_by=identity, order_by=(M.observed_at.desc(), M.id.desc()))
            .label("rank"),
            func.count().over(partition_by=identity).label("variant_count"),
            func.bool_or(M.is_historical).over(partition_by=identity).label("historical"),
        )
        .where(M.stored_at <= snapshot)
        .subquery()
    )
    category = func.coalesce(A.category, "unclassified").label("category")
    attention = func.coalesce(A.attention, "undecided").label("attention")
    return (
        select(
            *[ranked.c[c.name] for c in M.__table__.columns],
            ranked.c.variant_count,
            ranked.c.historical,
            A.reviewed_at,
            category,
            attention,
        )
        .outerjoin(
            A,
            and_(
                A.source_scope == ranked.c.source_scope,
                A.channel_id == ranked.c.channel_id,
                A.message_id == ranked.c.message_id,
            ),
        )
        .where(ranked.c.rank == 1)
        .subquery()
    )


def present(row):
    result = dict(row)
    result.pop("sha256", None)
    result.pop("capture_id", None)
    result["reviewed"] = result["reviewed_at"] is not None
    result["is_new"] = not result["historical"] and not result["reviewed"]
    return result


class InboxService:
    def __init__(self, sessions):
        self.sessions = sessions

    def list(self, params: ListInput):
        snapshot = params.snapshot_at or datetime.now(UTC)
        rows = logical(snapshot)
        filters = []
        if params.channel_id:
            filters.append(rows.c.channel_id == params.channel_id)
        if params.query.strip():
            needle = (
                "%"
                + params.query.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                + "%"
            )
            filters.append(rows.c.text.ilike(needle, escape="\\"))
        if params.origin != "all":
            filters.append(rows.c.historical == (params.origin == "historical"))
        if params.review in {"new", "unreviewed"}:
            filters.append(rows.c.reviewed_at.is_(None))
        elif params.review == "reviewed":
            filters.append(rows.c.reviewed_at.is_not(None))
        if params.review == "new":
            filters.append(rows.c.historical.is_(False))
        if params.category:
            filters.append(rows.c.category == params.category)
        if params.attention:
            filters.append(rows.c.attention == params.attention)
        with self.sessions() as s:
            total = s.scalar(select(func.count()).select_from(rows).where(*filters))
            found = (
                s.execute(
                    select(rows)
                    .where(*filters)
                    .order_by(
                        rows.c.occurred_at.desc(),
                        rows.c.source_scope,
                        rows.c.channel_id,
                        rows.c.message_id,
                    )
                    .offset(params.offset)
                    .limit(PAGE_SIZE)
                )
                .mappings()
                .all()
            )
            channels = s.execute(
                select(M.channel_id, M.channel_name).distinct().order_by(M.channel_name)
            ).all()
        return {
            "messages": [present(r) for r in found],
            "total": total,
            "snapshot_at": snapshot,
            "offset": params.offset,
            "next_offset": params.offset + len(found)
            if params.offset + len(found) < total
            else None,
            "channels": [{"channel_id": cid, "channel_name": name} for cid, name in channels],
        }

    def annotate(self, data: AnnotationInput):
        now = datetime.now(UTC)
        with self.sessions.begin() as s:
            message = s.get(M, data.id)
            if message is None:
                raise CollectionError("message_not_found", 404)
            identity = {
                key: getattr(message, key) for key in ("source_scope", "channel_id", "message_id")
            }
            updates = {"updated_at": now}
            if data.reviewed is not None:
                updates["reviewed_at"] = now if data.reviewed else None
            if data.category is not None:
                updates["category"] = data.category
            if data.attention is not None:
                updates["attention"] = data.attention
            values = {**identity, "attention": "undecided", "category": "unclassified", **updates}
            s.execute(
                insert(A)
                .values(**values)
                .on_conflict_do_update(
                    index_elements=[A.source_scope, A.channel_id, A.message_id], set_=updates
                )
            )
        return {"saved": True}

    def thread(self, identifier, offset):
        with self.sessions() as s:
            selected = s.get(M, identifier)
            if selected is None:
                raise CollectionError("message_not_found", 404)
            rows = logical(datetime.now(UTC))
            root = selected.thread_id or selected.message_id
            filters = [
                rows.c.source_scope == selected.source_scope,
                rows.c.channel_id == selected.channel_id,
                (rows.c.thread_id == root) | (rows.c.message_id == root),
            ]
            total = s.scalar(select(func.count()).select_from(rows).where(*filters))
            found = (
                s.execute(
                    select(rows)
                    .where(*filters)
                    .order_by(rows.c.occurred_at, rows.c.message_id)
                    .offset(offset)
                    .limit(PAGE_SIZE)
                )
                .mappings()
                .all()
            )
            return {
                "messages": [present(r) for r in found],
                "total": total,
                "next_offset": offset + len(found) if offset + len(found) < total else None,
            }

    def variants(self, identifier, offset):
        with self.sessions() as s:
            selected = s.get(M, identifier)
            if selected is None:
                raise CollectionError("message_not_found", 404)
            filters = [
                getattr(M, key) == getattr(selected, key)
                for key in ("source_scope", "channel_id", "message_id")
            ]
            total = s.scalar(select(func.count()).select_from(M).where(*filters))
            found = s.scalars(
                select(M)
                .where(*filters)
                .order_by(M.observed_at, M.id)
                .offset(offset)
                .limit(PAGE_SIZE)
            ).all()
            return {
                "messages": [
                    {k: v for k, v in view(r).items() if k not in {"sha256", "capture_id"}}
                    for r in found
                ],
                "total": total,
                "next_offset": offset + len(found) if offset + len(found) < total else None,
            }
