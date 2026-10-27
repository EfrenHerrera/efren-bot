import argparse
import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import Engine, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from efren_bot.classification import ASK_CONTEXT, REVIEW_REPLY, classify
from efren_bot.config import Settings
from efren_bot.db import make_engine, session_factory
from efren_bot.models import Activity, Event, Message, Outbox, Task, Thread, utcnow
from efren_bot.schemas import DemoEventInput

logger = logging.getLogger(__name__)


class ReplyBeforeRoot(Exception):
    """Keep evidence pending until the canonical request has been projected."""


@dataclass(frozen=True)
class WorkResult:
    status: Literal["idle", "processed", "deferred", "retry", "failed"]
    outbox_id: UUID | None = None
    attempts: int = 0


def project(session: Session, event: Event, message: Message) -> None:
    """Pure local DB effects; the caller holds the outbox AND thread row locks."""
    data = DemoEventInput.model_validate(event.payload)
    result = classify(data)
    if result.intent == "task_request":
        # One task per exact source message, NOT one inferred/merged task per thread.
        replies = session.scalars(
            select(Message).where(Message.thread_pk == message.thread_pk, Message.id != message.id)
        ).all()
        has_reply = any(
            classify(
                DemoEventInput.model_validate(reply.payload | {"event_id": "classification-only"})
            ).intent
            == "thread_reply"
            for reply in replies
        )
        session.add(
            Task(
                source_message_id=message.id,
                source_event_id=message.canonical_event_id,
                thread_pk=message.thread_pk,
                title="Subir el video (demo)",
                state="needs_context",
                next_action=REVIEW_REPLY if has_reply else ASK_CONTEXT,
                source_url=message.source_url,
                updated_at=utcnow(),
                has_new_reply=has_reply,
            )
        )
    elif result.intent == "thread_reply":
        tasks = session.scalars(select(Task).where(Task.thread_pk == message.thread_pk)).all()
        if not tasks:
            raise ReplyBeforeRoot()
        for task in tasks:
            task.has_new_reply = True
            task.updated_at = utcnow()
            task.next_action = REVIEW_REPLY
            # Deliberately no state transition, especially no automatic done.
    session.add(
        Activity(
            message_id=message.id,
            event_id=message.canonical_event_id,
            thread_pk=message.thread_pk,
            intent=result.intent,
            summary=result.summary,
            occurred_at=message.occurred_at,
        )
    )
    session.flush()


def process_once(sessions: sessionmaker) -> WorkResult:
    with sessions.begin() as session:
        item = session.scalar(
            select(Outbox)
            .join(Event, Event.id == Outbox.event_id)
            .join(Message, Message.id == Event.message_pk)
            .where(
                Outbox.status == "pending",
                Outbox.available_at <= utcnow(),
                # Waiting replies must not starve a later accepted root when
                # each poll occurs AFTER their backoff. Keep them pending but
                # ineligible until their own scoped thread has a projected task.
                or_(
                    Outbox.last_error.is_distinct_from("awaiting_root"),
                    select(Task.id).where(Task.thread_pk == Message.thread_pk).exists(),
                ),
            )
            .order_by(Outbox.created_at, Outbox.id)
            .limit(1)
            .with_for_update(skip_locked=True, of=Outbox)
        )
        if item is None:
            return WorkResult("idle")
        event = session.get(Event, item.event_id)
        message = session.get(Message, event.message_pk)
        thread = session.scalar(
            select(Thread).where(Thread.id == message.thread_pk).with_for_update(skip_locked=True)
        )
        if thread is None:
            # Do not wait while holding a queue row. Sleep happens outside the transaction.
            item.available_at = utcnow() + timedelta(seconds=0.1)
            return WorkResult("deferred", item.id, item.attempts)
        try:
            # Keep the claim lock in the outer transaction. A failed projection
            # rolls back ALL effects before the bounded failure record is saved.
            with session.begin_nested():
                project(session, event, message)
        except ReplyBeforeRoot:
            item.available_at = utcnow() + timedelta(seconds=1)
            item.last_error = "awaiting_root"
            return WorkResult("deferred", item.id, item.attempts)
        except Exception as exc:
            item.attempts += 1
            item.last_error = type(exc).__name__[:200]  # no payloads, SQL or credentials
            item.available_at = utcnow() + timedelta(seconds=min(60, 2 ** (item.attempts - 1)))
            item.status = "failed" if item.attempts >= 5 else "pending"
            return WorkResult(
                "failed" if item.status == "failed" else "retry", item.id, item.attempts
            )
        item.status = "processed"
        item.processed_at = utcnow()
        item.last_error = None
        return WorkResult("processed", item.id, item.attempts)


class Worker:
    def __init__(self, settings: Settings | None = None, *, engine: Engine | None = None):
        self.settings = settings or Settings()  # fail before any DB work outside local mode
        self.owned_engine = engine is None
        self.engine = engine if engine is not None else make_engine(self.settings)
        self.sessions = session_factory(self.engine)

    def close(self):
        if self.owned_engine:
            self.engine.dispose()

    def once(self) -> WorkResult:
        return process_once(self.sessions)

    def run(self):
        while True:
            try:
                result = self.once()
                if result.status != "idle":
                    print(json.dumps(asdict(result), default=str), flush=True)
            except SQLAlchemyError:
                logger.warning("Local database unavailable; retrying after poll interval")
            # No busy loops (including failures); never inside a DB transaction.
            time.sleep(self.settings.worker_poll_interval_seconds)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Local deterministic demo worker; no external effects"
    )
    parser.add_argument(
        "--once", action="store_true", help="Process at most one eligible outbox row"
    )
    args = parser.parse_args(argv)
    worker = Worker()
    try:
        if args.once:
            print(json.dumps(asdict(worker.once()), default=str))
        else:
            worker.run()
    except SQLAlchemyError:
        print("Local database unavailable", flush=True)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        worker.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
