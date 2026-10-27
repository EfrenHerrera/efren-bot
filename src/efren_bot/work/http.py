"""HTTP adapters; mutations are explicit, reads use a coherent snapshot."""

from uuid import UUID

from fastapi import FastAPI, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from efren_bot.models import WorkItem, WorkJob
from efren_bot.work import service
from efren_bot.work.contracts import (
    CreateReceipt,
    CreateWork,
    Decision,
    DecisionReceipt,
    WorkDetail,
    WorkList,
)


def install_work(app: FastAPI, sessions: sessionmaker, reads: sessionmaker) -> None:
    @app.exception_handler(service.WorkError)
    async def work_error(request, exc):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=exc.status, content={"detail": exc.code})

    @app.post("/api/work", response_model=CreateReceipt, status_code=202)
    def create(data: CreateWork, response: Response):
        result = service.create(sessions, data)
        response.status_code = 202 if result.status == "accepted" else 200
        return result

    @app.get("/api/work", response_model=WorkList)
    def listing():
        with reads.begin() as session:
            rows = session.execute(
                select(WorkItem, WorkJob)
                .join(WorkJob, WorkJob.work_id == WorkItem.id)
                .order_by(WorkItem.created_at.desc(), WorkItem.id)
                .limit(50)
            )
            return WorkList(works=[service.summary(work, job) for work, job in rows])

    @app.get("/api/work/{work_id}", response_model=WorkDetail)
    def get(work_id: UUID):
        with reads.begin() as session:
            return service.detail(session, work_id)

    @app.post(
        "/api/work/{work_id}/approvals/{approval_id}/decision", response_model=DecisionReceipt
    )
    def decide(work_id: UUID, approval_id: UUID, data: Decision):
        try:
            return service.decide(sessions, work_id, approval_id, data)
        except service.WorkError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.code) from exc
