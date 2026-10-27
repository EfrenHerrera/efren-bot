import hashlib
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from efren_bot.collection.service import CollectionError
from efren_bot.human import policy
from efren_bot.human.models import HumanControl, HumanDecision
from efren_bot.review.contracts import Action
from efren_bot.review.models import (
    ReviewControl,
    ReviewEntry,
    ReviewItem,
    ReviewProposal,
    ReviewRequest,
)
from efren_bot.review.service import ReviewService
from efren_bot.support.contracts import CaseAction
from efren_bot.support.models import SupportCase, SupportEntry
from efren_bot.support.service import SupportService

MODES = {
    "attend": "active",
    "continue": "active",
    "redirect": "active",
    "pause": "paused",
    "ignore": "ignored",
    "delegate": "delegated",
    "stop": "stopped",
}
CAPABILITIES = [
    {
        "kind": "slack_reply",
        "label": "Publicar respuesta en Slack",
        "enabled": False,
        "reason": "No hay publicador Slack autorizado en esta entrega.",
    },
    {
        "kind": "run_tests",
        "label": "Ejecutar pruebas o comandos",
        "enabled": False,
        "reason": "Sin ejecutor de código autorizado.",
    },
    {
        "kind": "edit_code",
        "label": "Modificar código o datos",
        "enabled": False,
        "reason": "Fuera de alcance; no existe un ejecutor habilitado.",
    },
    {
        "kind": "extend_sources",
        "label": "Consultar fuentes adicionales",
        "enabled": False,
        "reason": "Necesita alcance y adaptador aprobados; no se concede desde un texto.",
    },
]


class HumanService:
    def __init__(self, sessions):
        self.sessions = sessions

    def target(self, s, domain, identifier):
        model = ReviewItem if domain == "review" else SupportCase
        row = s.get(model, identifier)
        if row is None:
            raise CollectionError("human_target_not_found", 404)
        return row

    def actions(self, s, domain, row):
        result = []
        if domain == "review":
            demo = s.get(ReviewRequest, row.request_id).demo
            global_control = s.get(ReviewControl, 1)
            for p in s.scalars(
                select(ReviewProposal)
                .where(
                    ReviewProposal.item_id == row.id,
                    ReviewProposal.revision == row.revision,
                    ReviewProposal.status == "private",
                )
                .order_by(ReviewProposal.id)
            ):
                pending = s.scalar(
                    select(ReviewEntry.id).where(
                        ReviewEntry.item_id == row.id,
                        ReviewEntry.kind == "publish",
                        ReviewEntry.status.in_(["queued", "running", "sending", "uncertain"]),
                        ReviewEntry.payload["proposal_id"].astext == str(p.id),
                    )
                )
                result.append(
                    {
                        "id": str(p.id),
                        "kind": "gitlab_comment",
                        "label": "Publicar este comentario",
                        "body": p.body,
                        "destination": row.url,
                        "version": p.version,
                        "refs": row.snapshot.get("refs", {}),
                        "position": p.finding,
                        "enabled": not demo
                        and row.status == "ready"
                        and row.snapshot.get("mr_state") == "opened"
                        and bool(global_control and not global_control.paused)
                        and not pending
                        and policy.active(s, domain, row),
                        "reason": "Demo: nunca publica."
                        if demo
                        else "Publicación ya solicitada; espera su resultado."
                        if pending
                        else "Control global pausado."
                        if not global_control or global_control.paused
                        else "Requiere MR completa, abierta y versión vigente.",
                        "expires_in_seconds": 900,
                    }
                )
        elif row.report.get("slack_draft"):
            result.append(
                {
                    "id": str(row.id),
                    "kind": "slack_reply",
                    "label": "Publicar borrador Slack",
                    "body": row.report["slack_draft"],
                    "destination": f"Canal {row.channel_id}, conversación {row.conversation_id}",
                    "version": row.report.get("revision"),
                    "enabled": False,
                    "reason": "Borrador preliminar solo Slack. No hay publicador autorizado.",
                }
            )
        control = policy.control(s, domain, row)
        for action in result:
            frozen = {k: v for k, v in action.items() if k not in {"enabled", "reason", "label"}}
            frozen.update(
                domain=domain,
                target_id=str(row.id),
                revision=row.revision,
                control_revision=control.revision if control else 0,
            )
            action["fingerprint"] = hashlib.sha256(
                json.dumps(frozen, sort_keys=True).encode()
            ).hexdigest()
            denied = s.scalar(
                select(HumanDecision.id)
                .where(
                    HumanDecision.payload["input"]["action"].astext == "deny",
                    HumanDecision.payload["input"]["fingerprint"].astext == action["fingerprint"],
                )
                .limit(1)
            )
            action["denied"] = denied is not None
            if denied:
                action["enabled"] = False
                action["reason"] = "Denegada por ti para este contenido y versión."
        return result

    def summary(self, s, domain, row):
        control = policy.control(s, domain, row)
        state = (
            control.state
            if control
            else {"paused": "paused", "dismissed": "ignored"}.get(row.status, "active")
        )
        report = row.report
        summary = (
            report.get("summary", "")
            if domain == "review"
            else "\n".join(report.get("reported", []))
        )
        pending = report.get("pending", []) if domain == "review" else report.get("missing", [])
        actions = self.actions(s, domain, row)
        category = (
            "inactive"
            if state != "active"
            else "decision"
            if row.status in {"blocked", "failed", "partial"} or actions
            else "conclusion"
            if summary
            else "working"
        )
        return {
            "domain": domain,
            "id": str(row.id),
            "title": row.title,
            "status": row.status,
            "revision": row.revision,
            "control_revision": control.revision if control else 0,
            "disposition": state,
            "category": category,
            "conclusion": summary,
            "report_revision": report.get("revision"),
            "pending": pending,
            "actions": actions,
            "updated_at": row.updated_at.isoformat(),
            "error_code": row.error_code,
        }

    def list(self):
        from efren_bot.review.models import ReviewControl
        from efren_bot.support.models import SupportControl

        with self.sessions() as s:
            items = []
            controls = {}
            for domain, model, global_model in [
                ("review", ReviewItem, ReviewControl),
                ("support", SupportCase, SupportControl),
            ]:
                for row in s.scalars(
                    select(model).order_by(model.updated_at.desc(), model.id).limit(100)
                ):
                    items.append(self.summary(s, domain, row))
                c = s.get(global_model, 1)
                controls[domain] = {
                    "activated_at": c.activated_at.isoformat() if c and c.activated_at else None,
                    "paused": c.paused if c else True,
                    "available": bool(
                        c
                        and c.runner_seen_at
                        and datetime.now(UTC) - c.runner_seen_at < timedelta(seconds=45)
                    ),
                    "queued": s.query(model).filter(model.status == "queued").count(),
                }
            items.sort(key=lambda item: (item["updated_at"], item["id"]), reverse=True)
            return {
                "items": items,
                "controls": controls,
                "capabilities": CAPABILITIES,
                "limit_per_domain": 100,
            }

    def detail(self, domain, identifier):
        with self.sessions() as s:
            row = self.target(s, domain, identifier)
            control = policy.control(s, domain, row)
            history = (
                s.scalars(
                    select(HumanDecision)
                    .where(HumanDecision.control_id == control.id)
                    .order_by(HumanDecision.created_at, HumanDecision.id)
                ).all()
                if control
                else []
            )
            return {
                "request": self.summary(s, domain, row),
                "report": row.report,
                "snapshot": row.snapshot if domain == "review" else row.context,
                "history": [
                    {
                        "id": str(h.id),
                        "input": h.payload["input"],
                        "created_at": h.created_at.isoformat(),
                        "result": h.result,
                    }
                    for h in history
                ],
            }

    def act(self, data):
        store = (
            ReviewService(self.sessions)
            if data.domain == "review"
            else SupportService(self.sessions)
        )
        raw = data.model_dump(mode="json")
        with self.sessions.begin() as s:
            store.control(s)
            old = s.scalar(select(HumanDecision).where(HumanDecision.request_id == data.request_id))
            if old:
                if old.payload["input"] != raw:
                    raise CollectionError("human_request_conflict")
                return old.result
            row = self.target(s, data.domain, data.id)
            key = policy.identity(s, data.domain, row)
            s.execute(
                insert(HumanControl)
                .values(**key, state="active", revision=0, updated_at=datetime.now(UTC))
                .on_conflict_do_nothing()
            )
            control = policy.control(s, data.domain, row)
            if row.revision != data.revision or control.revision != data.control_revision:
                raise CollectionError("human_decision_stale")
            action = None
            result = {"request_id": str(data.request_id)}
            if data.action in {"approve", "deny"}:
                action = next(
                    (
                        a
                        for a in self.actions(s, data.domain, row)
                        if a["id"] == str(data.proposal_id) and a["fingerprint"] == data.fingerprint
                    ),
                    None,
                )
                if action is None or action["denied"]:
                    raise CollectionError("human_action_changed")
                if data.action == "approve":
                    if not action["enabled"]:
                        raise CollectionError("human_capability_blocked")
                    entry = store.act(
                        Action(
                            id=row.id,
                            request_id=data.request_id,
                            revision=row.revision,
                            action="publish",
                            proposal_id=data.proposal_id,
                            proposal_version=action["version"],
                        ),
                        session=s,
                    )
                    result["entry_id"] = str(entry["id"])
                elif data.domain == "review":
                    store.act(
                        Action(
                            id=row.id,
                            request_id=data.request_id,
                            revision=row.revision,
                            action="discard",
                            proposal_id=data.proposal_id,
                            proposal_version=action["version"],
                        ),
                        session=s,
                    )
            else:
                if data.action == "redirect" and not data.text.strip():
                    raise CollectionError("text_required", 422)
                control.state = MODES[data.action]
                control.revision += 1
                control.updated_at = datetime.now(UTC)
                s.flush()
                mapped = (
                    "redirect"
                    if data.action == "redirect"
                    else "resume"
                    if control.state == "active"
                    else "pause"
                )
                if data.domain == "review":
                    store.act(
                        Action(
                            id=row.id,
                            request_id=data.request_id,
                            revision=row.revision,
                            action=mapped,
                            text=data.text,
                        ),
                        session=s,
                    )
                    siblings = list(
                        s.scalars(
                            select(ReviewItem)
                            .join(ReviewRequest)
                            .where(
                                ReviewRequest.source_scope == key["source_scope"],
                                ReviewItem.project_path == row.project_path,
                                ReviewItem.mr_iid == row.mr_iid,
                            )
                        )
                    )
                    for sibling in siblings:
                        if sibling.id != row.id and (
                            control.state != "active" or sibling.status in {"queued", "running"}
                        ):
                            sibling.status = "paused"
                            sibling.revision += 1
                            sibling.updated_at = datetime.now(UTC)
                    for pending in s.scalars(
                        select(ReviewEntry).where(
                            ReviewEntry.kind.in_(["publish", "ask"]),
                            ReviewEntry.status.in_(["queued", "running"]),
                            ReviewEntry.item_id.in_([i.id for i in siblings]),
                        )
                    ):
                        pending.status = "cancelled"
                else:
                    store.act(
                        CaseAction(
                            id=row.id, request_id=data.request_id, action=mapped, text=data.text
                        ),
                        session=s,
                    )
                    for pending in s.scalars(
                        select(SupportEntry).where(
                            SupportEntry.case_id == row.id,
                            SupportEntry.kind == "ask",
                            SupportEntry.status.in_(["queued", "running"]),
                        )
                    ):
                        pending.status = "cancelled"
            decision = HumanDecision(
                control_id=control.id,
                request_id=data.request_id,
                case_id=row.id if data.domain == "support" else None,
                item_id=row.id if data.domain == "review" else None,
                payload={"input": raw, "action_snapshot": action},
                result=result,
                created_at=datetime.now(UTC),
            )
            s.add(decision)
            return result
