"""Separate opt-in synthetic worker. No implicit startup, remote engine or commands."""

import argparse
import json
import time
from dataclasses import asdict, dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import Engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from efren_bot.config import Settings
from efren_bot.db import make_engine, session_factory
from efren_bot.models import WorkItem, WorkJob, utcnow
from efren_bot.work.contracts import Checkpoint
from efren_bot.work.service import InvalidState, digest, execute_step, history, source


@dataclass(frozen=True)
class WorkResult:
    status: str
    job_id: UUID | None = None
    attempt_count: int = 0
    error_code: str | None = None


def process_once(sessions: sessionmaker) -> WorkResult:
    with sessions.begin() as session:
        job = session.scalar(
            select(WorkJob)
            .where(WorkJob.status == "queued", WorkJob.available_at <= utcnow())
            .order_by(WorkJob.available_at, WorkJob.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if job is None:
            return WorkResult("idle")
        work = session.get(WorkItem, job.work_id)
        attempt_id = uuid4()
        job.attempt_count += 1
        session.flush()  # outer counter before begin_nested's unconditional pre-flush
        try:
            with session.begin_nested():
                execute_step(session, job, work, attempt_id)
        except Exception as exc:
            # Nested rollback expires modified objects. Reload, never session.rollback():
            # the outer transaction must retain the queue row lock and attempt count.
            session.refresh(job)
            session.refresh(work)
            permanent = isinstance(exc, (InvalidState, ValueError, TypeError, KeyError))
            code = "state_invalid" if permanent else "execution_failed"
            job.failure_count += 1
            exhausted = permanent or job.failure_count >= 5
            job.status = "failed" if exhausted else "queued"
            job.last_error_code = code
            job.available_at = utcnow() + timedelta(seconds=2 ** (job.failure_count - 1))
            if exhausted:
                job.checkpoint = Checkpoint(
                    phase="failed", source_sha256=digest(source()), next_action="none"
                ).model_dump(mode="json")
            work.state = "waiting" if exhausted else "active"
            work.updated_at = utcnow()
            history(
                session,
                job,
                "attempt_failed",
                "Paso revertido; revisión o reintento local.",
                attempt_id=attempt_id,
                error_code=code,
            )
            return WorkResult("failed" if exhausted else "retry", job.id, job.attempt_count, code)
        return WorkResult(job.status, job.id, job.attempt_count)


class Worker:
    def __init__(self, settings: Settings | None = None, *, engine: Engine | None = None):
        self.settings = settings or Settings()  # APP_ENV validation BEFORE engine/DB
        self.owned_engine = engine is None
        self.engine = engine if engine is not None else make_engine(self.settings)
        self.sessions = session_factory(self.engine)

    def once(self) -> WorkResult:
        return process_once(self.sessions)

    def close(self) -> None:
        if self.owned_engine:
            self.engine.dispose()

    def run(self) -> None:
        while True:
            try:
                result = self.once()
                if result.status != "idle":
                    print(json.dumps(asdict(result), default=str), flush=True)
            except SQLAlchemyError:
                print("Local database unavailable", flush=True)
            time.sleep(self.settings.worker_poll_interval_seconds)  # no connection held


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Synthetic DB-only fake executor; no external effects"
    )
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    worker = None
    try:
        worker = Worker()  # Settings errors may include rejected secrets: never render them.
        if args.once:
            print(json.dumps(asdict(worker.once()), default=str), flush=True)
        else:
            worker.run()
    except ValidationError:
        print("Invalid local configuration", flush=True)
        return 1
    except SQLAlchemyError:
        print("Local database unavailable", flush=True)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        if worker is not None:
            worker.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
