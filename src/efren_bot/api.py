from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from efren_bot.config import Settings
from efren_bot.db import make_engine, session_factory
from efren_bot.ingestion import IdentityConflict, ingest
from efren_bot.models import Activity, Event, Message, Outbox, Task, Thread
from efren_bot.schemas import (
    ActivityView,
    Counts,
    DemoEventInput,
    EventView,
    MessageView,
    Overview,
    Receipt,
    TaskDetail,
    TaskView,
)


def task_view(task: Task, thread: Thread) -> TaskView:
    return TaskView(
        id=task.id,
        title=task.title,
        state=task.state,
        next_action=task.next_action,
        source_url=task.source_url,
        source_event_id=task.source_event_id,
        thread_id=thread.thread_id,
        updated_at=task.updated_at,
        has_new_reply=task.has_new_reply,
    )


def create_app(settings: Settings | None = None, *, engine: Engine | None = None) -> FastAPI:
    settings = settings or Settings()  # validate local mode before constructing the ASGI app
    owned_engine = engine is None
    engine = engine if engine is not None else make_engine(settings)
    sessions = session_factory(engine)
    reads = session_factory(engine.execution_options(isolation_level="REPEATABLE READ"))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        if owned_engine:
            engine.dispose()

    app = FastAPI(title="Efren Bot · local demo", lifespan=lifespan)
    app.state.engine = engine

    from efren_bot.bridge.http import install_bridge

    install_bridge(app, settings, sessions)

    from efren_bot.work.http import install_work

    install_work(app, sessions, reads)

    from efren_bot.factory.http import FactoryOperations, install_factory_webhooks
    from efren_bot.factory.wiring import build_service

    plant = build_service(settings, sessions)
    install_factory_webhooks(
        app,
        plant,
        whatsapp_app_secret=settings.factory_whatsapp_app_secret,
        whatsapp_verify_token=settings.factory_whatsapp_verify_token,
    )
    factory_operations = FactoryOperations(plant, reads)

    from efren_bot.collection.http import install_collection

    install_collection(app, sessions, factory=factory_operations)

    @app.exception_handler(SQLAlchemyError)
    async def unavailable(request, exc):
        # Never return the exception: it may contain credentials, SQL or payloads.
        return JSONResponse(status_code=503, content={"detail": "database unavailable"})

    @app.get("/healthz")
    def health():
        return {"status": "ok"}

    @app.get("/readyz")
    def ready():
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "database": "ok"}

    @app.post("/api/demo/events", response_model=Receipt, status_code=202)
    def accept(data: DemoEventInput, response: Response):
        try:
            receipt = ingest(sessions, data)
        except IdentityConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        response.status_code = 202 if receipt.status == "accepted" else 200
        return receipt

    @app.get("/api/overview", response_model=Overview)
    def overview():
        with reads.begin() as session:
            tasks = [
                task_view(task, thread)
                for task, thread in session.execute(
                    select(Task, Thread)
                    .join(Thread, Thread.id == Task.thread_pk)
                    .order_by(Task.updated_at.desc(), Task.id)
                )
            ]
            activities = [
                ActivityView(
                    id=activity.id,
                    intent=activity.intent,
                    summary=activity.summary,
                    event_id=activity.event_id,
                    thread_id=thread.thread_id,
                    occurred_at=activity.occurred_at,
                )
                for activity, thread in session.execute(
                    select(Activity, Thread)
                    .join(Thread, Thread.id == Activity.thread_pk)
                    .order_by(Activity.occurred_at.desc(), Activity.id)
                )
            ]
            outbox = dict(
                session.execute(select(Outbox.status, func.count()).group_by(Outbox.status)).all()
            )
            return Overview(
                tasks=tasks,
                activities=activities,
                counts=Counts(
                    tasks=len(tasks),
                    needs_context=sum(t.state == "needs_context" for t in tasks),
                    ready=sum(t.state == "ready" for t in tasks),
                    updates=sum(t.has_new_reply for t in tasks),
                    pending_events=outbox.get("pending", 0),
                    failed_events=outbox.get("failed", 0),
                ),
            )

    @app.get("/api/tasks/{task_id}", response_model=TaskDetail)
    def task_detail(task_id: UUID):
        with reads.begin() as session:
            task = session.get(Task, task_id)
            if task is None:
                raise HTTPException(status_code=404, detail="task not found")
            thread = session.get(Thread, task.thread_pk)
            messages = session.scalars(
                select(Message)
                .where(Message.thread_pk == thread.id)
                .order_by(Message.occurred_at, Message.id)
            ).all()
            return TaskDetail(
                task=task_view(task, thread),
                messages=[
                    MessageView(
                        event_id=m.canonical_event_id,
                        actor_id=m.actor_id,
                        text=m.text,
                        occurred_at=m.occurred_at,
                        source_url=m.source_url,
                    )
                    for m in messages
                ],
            )

    @app.get("/api/events/{event_id}", response_model=EventView)
    def event_detail(event_id: UUID):
        with Session(engine) as session:
            event = session.get(Event, event_id)
            if event is None:
                raise HTTPException(status_code=404, detail="event not found")
            return EventView(
                id=event.id,
                provider=event.provider,
                owner_id=event.owner_id,
                payload=DemoEventInput.model_validate(event.payload),
                accepted_at=event.accepted_at,
            )

    @app.get("/api/demo/fixtures")
    def fixtures():
        from efren_bot.fixtures import demo_fixtures

        return demo_fixtures()

    return app


app = create_app()
