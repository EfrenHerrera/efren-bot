from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from efren_bot.config import OWNER_ID, PROVIDER
from efren_bot.models import Event, Message, Outbox, Thread
from efren_bot.schemas import DemoEventInput, Receipt


class IdentityConflict(Exception):
    """A previously accepted identity has different normalized content."""


def ingest(sessions: sessionmaker, data: DemoEventInput) -> Receipt:
    # Returning from this context commits BEFORE the receipt reaches the caller.
    with sessions.begin() as session:
        return ingest_in_transaction(session, data)


def ingest_in_transaction(session: Session, data: DemoEventInput) -> Receipt:
    """Caller owns transaction; never swallow conflicts and commit partial rows."""
    scope = dict(provider=PROVIDER, workspace_id=data.workspace_id, channel_id=data.channel_id)
    payload = data.canonical_payload()
    message_payload = data.canonical_payload(message=True)

    event = session.scalar(select(Event).filter_by(**scope, event_id=data.event_id))
    if event is not None:
        if event.payload != payload:
            raise IdentityConflict("event identity already has different content")
        return Receipt(id=event.id, status="duplicate")

    # Consistent lock order: thread -> message -> event. ON CONFLICT waits for
    # concurrent inserts; the following READ COMMITTED SELECT sees their commit.
    thread_id = session.scalar(
        insert(Thread)
        .values(id=uuid4(), **scope, thread_id=data.thread_id)
        .on_conflict_do_nothing(constraint="uq_thread")
        .returning(Thread.id)
    )
    if thread_id is None:
        thread_id = session.scalar(select(Thread.id).filter_by(**scope, thread_id=data.thread_id))

    event_uuid = uuid4()
    message_uuid = session.scalar(
        insert(Message)
        .values(
            id=uuid4(),
            **scope,
            message_id=data.message_id,
            thread_pk=thread_id,
            canonical_event_id=event_uuid,
            payload=message_payload,
            actor_id=data.actor_id,
            text=data.text,
            occurred_at=data.occurred_at,
            source_url=str(data.source_url) if data.source_url else None,
        )
        .on_conflict_do_nothing(constraint="uq_message")
        .returning(Message.id)
    )
    new_message = message_uuid is not None
    if not new_message:
        message = session.scalar(select(Message).filter_by(**scope, message_id=data.message_id))
        if message.payload != message_payload:
            raise IdentityConflict("message identity already has different content")
        message_uuid = message.id

    inserted_event = session.scalar(
        insert(Event)
        .values(
            id=event_uuid,
            **scope,
            owner_id=OWNER_ID,
            event_id=data.event_id,
            message_pk=message_uuid,
            payload=payload,
        )
        .on_conflict_do_nothing(constraint="uq_event")
        .returning(Event.id)
    )
    if inserted_event is None:
        event = session.scalar(select(Event).filter_by(**scope, event_id=data.event_id))
        if event.payload != payload:
            raise IdentityConflict("event identity already has different content")
        return Receipt(id=event.id, status="duplicate")
    if new_message:
        session.add(Outbox(event_id=inserted_event))
    session.flush()
    return Receipt(id=inserted_event, status="accepted" if new_message else "duplicate")
