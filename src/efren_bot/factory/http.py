"""HTTP surfaces of the plant.

Two different trust models, kept apart on purpose:

- **Operations** (list, admission, control, effect decisions) mutate real state, so they live on
  the existing hardened local edge (``/api/collection/factory/*``: host, origin, per-session
  token, strict JSON, size caps). They are never exposed unauthenticated.
- **Webhooks** are called by outside services, so they cannot use the local edge; they are
  authenticated by a signature over the raw body and fail closed when no secret is configured.
"""

import hashlib
import hmac
from typing import Literal
from uuid import UUID

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from efren_bot.factory.intake import IntakeItem, WhatsAppAdapter
from efren_bot.factory.models import (
    FactoryAdmission,
    FactoryEffect,
    FactoryItem,
    FactoryJob,
)
from efren_bot.factory.service import FactoryError, FactoryService


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID


class AdmissionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    action: Literal["admit", "discard"]
    project: str | None = Field(default=None, max_length=100)
    note: str = Field(default="", max_length=2000)


class JobControl(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    action: Literal["pause", "continue", "stop", "redirect"]
    text: str = Field(default="", max_length=4000)


class EffectDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    action: Literal["approve", "deny"]
    fingerprint: str = Field(min_length=64, max_length=64)
    text: str = Field(default="", max_length=2000)


def _item(row: FactoryItem, admission: FactoryAdmission | None) -> dict:
    return {
        "id": str(row.id),
        "source": row.source_kind,
        "external_id": row.external_id,
        "title": row.title,
        "text": row.text,
        "status": row.status,
        "url": row.url,
        "occurred_at": row.occurred_at.isoformat(),
        "admission": admission
        and {
            "decision": admission.decision,
            "decided_by": admission.decided_by,
            "reasons": admission.reasons,
            "project": admission.project,
            "profile": admission.profile,
            "role": admission.role,
        },
    }


def _job(row: FactoryJob) -> dict:
    record = row.run_record or {}
    return {
        "id": str(row.id),
        "key": row.job_key,
        "item_id": str(row.item_id),
        "project": row.project,
        "status": row.status,
        "attempts": row.attempt_count,
        "error_code": row.error_code,
        "risk": (record.get("risk") or {}).get("tier"),
        "requires_human": record.get("requires_human"),
        "human_reasons": record.get("human_reasons", []),
        "branch": record.get("branch"),
        "checks": [
            {"name": c["name"], "status": c["status"], "mandatory": c["mandatory"]}
            for c in record.get("checks", [])
        ],
        "review": (record.get("review") or {}).get("verdict"),
    }


def _effect(row: FactoryEffect) -> dict:
    return {
        "id": str(row.id),
        "job_id": str(row.job_id),
        "kind": row.kind,
        "policy": row.policy,
        "state": row.state,
        "payload": row.payload,
        "fingerprint": row.fingerprint,
        "expires_at": row.expires_at.isoformat(),
        "decided_by": row.decided_by,
        "result": row.result,
    }


class FactoryOperations:
    """The operations the local web edge routes to. Pure data in, plain dicts out."""

    def __init__(self, service: FactoryService, reads: sessionmaker):
        self.service, self.reads = service, reads

    def list(self) -> dict:
        with self.reads.begin() as session:
            by_status = dict(
                session.execute(
                    select(FactoryItem.status, func.count()).group_by(FactoryItem.status)
                ).all()
            )
            jobs = session.scalars(
                select(FactoryJob).order_by(FactoryJob.created_at.desc()).limit(50)
            ).all()
            pending = session.scalars(
                select(FactoryEffect)
                .where(FactoryEffect.state == "proposed", FactoryEffect.policy == "human")
                .order_by(FactoryEffect.created_at)
            ).all()
            awaiting = session.scalars(
                select(FactoryItem)
                .where(FactoryItem.status.in_(["needs_human", "needs_context"]))
                .order_by(FactoryItem.created_at)
            ).all()
            latest = {
                row.id: session.scalar(
                    select(FactoryAdmission)
                    .where(FactoryAdmission.item_id == row.id)
                    .order_by(FactoryAdmission.created_at.desc())
                    .limit(1)
                )
                for row in awaiting
            }
            return {
                "items_by_status": by_status,
                "awaiting_admission": [_item(r, latest[r.id]) for r in awaiting],
                "jobs": [_job(j) for j in jobs],
                "pending_effects": [_effect(e) for e in pending],
                "projects": [
                    {"name": p.name, "profile": p.profile} for p in self.service.projects.projects
                ],
            }

    def detail(self, data: Selection) -> dict:
        with self.reads.begin() as session:
            row = session.get(FactoryJob, data.id)
            if row is None:
                raise FactoryError("job_not_found", 404)
            effects = session.scalars(
                select(FactoryEffect).where(FactoryEffect.job_id == row.id)
            ).all()
            return {
                **_job(row),
                "run_record": row.run_record,
                "effects": [_effect(e) for e in effects],
            }

    def admission(self, data: AdmissionDecision) -> dict:
        result = self.service.decide_admission(
            data.id, data.action, project=data.project, note=data.note
        )
        return {
            "item_id": str(result.item_id),
            "decision": result.decision,
            "job_id": str(result.job_id) if result.job_id else None,
        }

    def control(self, data: JobControl) -> dict:
        self.service.control_job(data.id, data.action, data.text)
        return {"job_id": str(data.id), "action": data.action}

    def effect(self, data: EffectDecision) -> dict:
        effect = self.service.decide_effect(
            data.id, data.action, fingerprint=data.fingerprint, text=data.text
        )
        return _effect(effect)

    ROUTES = {
        "detail": ("detail", Selection),
        "admission": ("admission", AdmissionDecision),
        "control": ("control", JobControl),
        "effect": ("effect", EffectDecision),
    }


def whatsapp_signature_ok(secret: str, body: bytes, header: str | None) -> bool:
    """Meta signs the raw body with the app secret: ``X-Hub-Signature-256: sha256=<hex>``."""
    if not secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def install_factory_webhooks(
    app: FastAPI, service: FactoryService, *, whatsapp_app_secret: str, whatsapp_verify_token: str
) -> None:
    """Signed, fail-closed webhook for WhatsApp Cloud API. No other push source is exposed."""
    adapter = WhatsAppAdapter()

    @app.get("/api/factory/webhooks/whatsapp")
    def verify(request: Request):
        q = request.query_params
        if not whatsapp_verify_token:
            return JSONResponse(status_code=503, content={"detail": "webhook_not_configured"})
        ok = q.get("hub.mode") == "subscribe" and hmac.compare_digest(
            q.get("hub.verify_token", ""), whatsapp_verify_token
        )
        if not ok:
            return JSONResponse(status_code=403, content={"detail": "forbidden"})
        return PlainTextResponse(q.get("hub.challenge", ""))

    @app.post("/api/factory/webhooks/whatsapp", status_code=202)
    async def receive(request: Request, response: Response):
        if not whatsapp_app_secret:
            return JSONResponse(status_code=503, content={"detail": "webhook_not_configured"})
        body = await request.body()
        if len(body) > 262144:
            return JSONResponse(status_code=413, content={"detail": "body_too_large"})
        if not whatsapp_signature_ok(
            whatsapp_app_secret, body, request.headers.get("x-hub-signature-256")
        ):
            return JSONResponse(status_code=401, content={"detail": "bad_signature"})
        try:
            import json

            items: list[IntakeItem] = adapter.parse(json.loads(body))
        except (ValueError, KeyError, TypeError, AttributeError):
            return JSONResponse(status_code=422, content={"detail": "invalid_payload"})
        results = service.ingest(items)
        return {"received": len(results), "duplicates": sum(r.duplicate for r in results)}
