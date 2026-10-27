from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from efren_bot.collection.models import CollectionControl, CollectionMessage, CollectionRun

INTERVAL = timedelta(minutes=15)
PRESENCE = timedelta(seconds=45)
ACTIVE = ("queued", "running")


class CollectionError(Exception):
    def __init__(self, code, status=409):
        self.code, self.status = code, status


def view(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


class CollectionService:
    def __init__(self, sessions):
        self.sessions = sessions

    def control(self, session):
        session.execute(
            insert(CollectionControl).values(id=1, paused=True).on_conflict_do_nothing()
        )
        return session.scalar(
            select(CollectionControl).where(CollectionControl.id == 1).with_for_update()
        )

    def active(self, session):
        return session.scalar(select(CollectionRun).where(CollectionRun.status.in_(ACTIVE)))

    def enqueue(self, session, control, trigger, now):
        run = self.active(session)
        if run is None:
            start = control.activated_at
            run = CollectionRun(
                trigger=trigger,
                status="queued",
                created_at=now,
                window_start=start,
                coverage=[],
                added_count=0,
                page_count=0,
                sources=dict(control.sources),
            )
            session.add(run)
            session.flush()
        return run

    def command(self, action, now=None):
        now = now or datetime.now(UTC)
        with self.sessions.begin() as session:
            control = self.control(session)
            if action == "pause":
                control.paused = True
            elif action in {"activate", "resume"}:
                control.activated_at = control.activated_at or now
                control.paused = False
                control.next_due_at = now + INTERVAL
            elif action == "run":
                existing = self.active(session)
                if existing:
                    return view(existing)
                if control.runner_seen_at is None or now - control.runner_seen_at > PRESENCE:
                    raise CollectionError("runner_unavailable")
                control.activated_at = control.activated_at or now
                return view(self.enqueue(session, control, "manual", now))
            else:
                raise CollectionError("invalid_action", 422)
            return {
                "paused": control.paused,
                "activated_at": control.activated_at,
                "next_due_at": control.next_due_at,
            }

    def heartbeat(self, now=None):
        with self.sessions.begin() as session:
            self.control(session).runner_seen_at = now or datetime.now(UTC)

    def recover(self, now=None):
        with self.sessions.begin() as session:
            self.control(session)
            for run in session.scalars(
                select(CollectionRun).where(CollectionRun.status == "running")
            ):
                run.status, run.error_code = "failed", "runner_interrupted"
                run.finished_at = now or datetime.now(UTC)

    def claim(self, now=None):
        now = now or datetime.now(UTC)
        with self.sessions.begin() as session:
            control = self.control(session)
            run = self.active(session)
            if run and run.status == "running":
                return None
            if (
                run is None
                and not control.paused
                and control.activated_at
                and control.next_due_at <= now
            ):
                run = self.enqueue(session, control, "automatic", now)
            if run is None:
                return None
            run.status, run.started_at, run.window_end = "running", now, now
            session.flush()
            return {**view(run), "progress": dict(control.progress)}

    def finish(
        self,
        run_id,
        status,
        now=None,
        *,
        added=0,
        pages=0,
        coverage=None,
        error_code=None,
        progress=None,
    ):
        if status not in {"succeeded", "partial", "failed"}:
            raise ValueError("invalid terminal status")
        now = now or datetime.now(UTC)
        with self.sessions.begin() as session:
            control = self.control(session)
            run = session.get(CollectionRun, UUID(str(run_id)))
            if run is None or run.status != "running":
                raise CollectionError("run_not_running")
            run.status, run.finished_at = status, now
            run.added_count, run.page_count = added, pages
            run.coverage, run.error_code = coverage or [], error_code
            control.progress = {**control.progress, **(progress or {})}
            if status == "succeeded":
                control.watermark = run.window_end
            control.next_due_at = now + INTERVAL

    def status(self, now=None):
        now = now or datetime.now(UTC)
        with self.sessions.begin() as session:
            control = self.control(session)
            runs = session.scalars(
                select(CollectionRun).order_by(CollectionRun.created_at.desc()).limit(20)
            ).all()
            messages = session.scalars(
                select(CollectionMessage)
                .order_by(
                    CollectionMessage.occurred_at.desc(), CollectionMessage.observed_at.desc()
                )
                .limit(50)
            ).all()
            active = self.active(session)
            return {
                **view(control),
                "interval_seconds": int(INTERVAL.total_seconds()),
                "runner_available": control.runner_seen_at is not None
                and now - control.runner_seen_at <= PRESENCE,
                "active_run": view(active) if active else None,
                "runs": [view(r) for r in runs],
                "messages": [view(m) for m in messages],
                "message_count": session.scalar(
                    select(func.count()).select_from(CollectionMessage)
                ),
            }
