from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, exists, func, select, update
from sqlalchemy.dialects.postgresql import insert

from efren_bot.collection.conversations import ConversationDetail, ConversationService
from efren_bot.collection.models import CollectionAnnotation, CollectionCapture, CollectionRun
from efren_bot.collection.models import CollectionMessage as M
from efren_bot.collection.service import CollectionError, view
from efren_bot.human import policy
from efren_bot.support.models import SupportCase as C
from efren_bot.support.models import SupportControl
from efren_bot.support.models import SupportEntry as E
from efren_bot.support.models import SupportIntake as I

SOURCE_LIMITS = {
    "cloudwatch": "Pendiente: perfil/cuenta, grupos exactos, ventana y presupuesto aprobados.",
    "gitlab": "Alcance pendiente: proyecto y referencia exacta autorizados.",
    "local_code": "Alcance pendiente: repositorio y versión autorizados; sin operaciones Git.",
}


class SupportService:
    def __init__(self, sessions):
        self.sessions = sessions

    def control(self, s):
        s.execute(
            insert(SupportControl).values(id=1, paused=True, epoch=1).on_conflict_do_nothing()
        )
        return s.scalar(select(SupportControl).where(SupportControl.id == 1).with_for_update())

    def command(self, action):
        with self.sessions.begin() as s:
            control = self.control(s)
            if action not in {"activate", "pause", "resume"}:
                raise CollectionError("invalid_action", 422)
            if action != "pause":
                control.activated_at = control.activated_at or datetime.now(UTC)
            control.paused = action == "pause"
            control.epoch += 1
            return view(control)

    def heartbeat(self):
        with self.sessions.begin() as s:
            self.control(s).runner_seen_at = datetime.now(UTC)

    def scan(self):
        with self.sessions.begin() as s:
            control = self.control(s)
            if not control.activated_at:
                return 0
            identity = [M.source_scope, M.channel_id, M.message_id]
            known = exists(
                select(I.id).where(
                    I.source_scope == M.source_scope,
                    I.channel_id == M.channel_id,
                    I.message_id == M.message_id,
                )
            )
            rows = s.execute(
                select(*identity, func.min(M.stored_at).label("first"))
                .join(CollectionCapture, CollectionCapture.id == M.capture_id)
                .join(CollectionRun, CollectionRun.id == CollectionCapture.run_id)
                .where(~known)
                .group_by(*identity)
                .having(
                    and_(
                        func.min(M.stored_at) >= control.activated_at,
                        func.min(M.occurred_at) >= control.activated_at,
                        ~func.bool_or(M.is_historical),
                        ~func.bool_or(CollectionRun.trigger == "import"),
                    )
                )
                .order_by(func.min(M.stored_at), *identity)
                .limit(100)
            ).all()
            for scope, channel, mid, _ in rows:
                variant = s.scalar(
                    select(M.id)
                    .where(M.source_scope == scope, M.channel_id == channel, M.message_id == mid)
                    .order_by(M.stored_at, M.id)
                )
                s.add(
                    I(
                        source_scope=scope,
                        channel_id=channel,
                        message_id=mid,
                        variant_id=variant,
                        status="queued",
                        created_at=datetime.now(UTC),
                    )
                )
            return len(rows)

    def snapshot(self, s, variant_id):
        _, conv = ConversationService(self.sessions).selected(
            s, ConversationDetail(id=variant_id), datetime.now(UTC)
        )
        members = conv["_members"]
        selected = members[:40] + members[-160:] if len(members) > 200 else members
        if not any(row["id"] == variant_id for row in selected):
            source = s.get(M, variant_id)
            selected = [
                *selected[:-1],
                {
                    "id": source.id,
                    "message_id": source.message_id,
                    "text": source.text,
                    "occurred_at": source.occurred_at,
                },
            ]
        source = s.get(M, variant_id)
        manual = set(
            s.scalars(
                select(CollectionAnnotation.category).where(
                    CollectionAnnotation.source_scope == source.source_scope,
                    CollectionAnnotation.channel_id == source.channel_id,
                    CollectionAnnotation.message_id == source.message_id,
                    CollectionAnnotation.category != "unclassified",
                )
            )
        )
        for group in conv["groups"]:
            if group["category"] != "unclassified" and (
                group["all_context"]
                or any(
                    s.get(M, mid).message_id == source.message_id for mid in group["message_ids"]
                )
            ):
                manual.add(group["category"])
        text_budget = 65000
        bounded = []
        trigger = next(row for row in selected if row["id"] == variant_id)
        for row in [trigger, *(row for row in selected if row["id"] != variant_id)]:
            excerpt = row["text"][: min(4000, text_budget)]
            if text_budget <= 0:
                break
            bounded.append({"id": row["id"], "text": excerpt, "occurred_at": row["occurred_at"]})
            text_budget -= len(excerpt) + 100
        bounded.sort(key=lambda row: (row["occurred_at"], str(row["id"])))
        return jsonable_encoder(
            {
                "conversation_id": conv["conversation_id"],
                "relation_status": conv["relation_status"],
                "root_present": conv["root_present"],
                "channel_name": conv["channel_name"],
                "trigger_id": variant_id,
                "truncated": text_budget < 4000
                or len(bounded) < len(members)
                or any(len(m["text"]) > 4000 for m in selected),
                "messages": bounded,
                "human_categories": sorted(manual),
                "sources": SOURCE_LIMITS,
            }
        )

    def list(self):
        with self.sessions.begin() as s:
            control = self.control(s)
            now = datetime.now(UTC)
            return {
                "control": {
                    **view(control),
                    "runner_available": bool(
                        control.runner_seen_at
                        and now - control.runner_seen_at < timedelta(seconds=45)
                    ),
                },
                "source_limits": SOURCE_LIMITS,
                "cases": [
                    {
                        **{k: v for k, v in view(c).items() if k not in {"context", "report"}},
                        "context": {"channel_name": c.context["channel_name"]},
                    }
                    for c in s.scalars(select(C).order_by(C.updated_at.desc(), C.id).limit(100))
                ],
                "intakes": [
                    view(i)
                    for i in s.scalars(select(I).order_by(I.created_at.desc(), I.id).limit(30))
                ],
            }

    def detail(self, identifier):
        with self.sessions() as s:
            case = s.get(C, identifier)
            if case is None:
                raise CollectionError("case_not_found", 404)
            return {
                "case": view(case),
                "entries": [
                    view(e)
                    for e in s.scalars(
                        select(E).where(E.case_id == case.id).order_by(E.created_at, E.id)
                    )
                ],
            }

    def act(self, data, *, session=None):
        if data.action in {"ask", "redirect"} and not data.text:
            raise CollectionError("text_required", 422)
        with nullcontext(session) if session is not None else self.sessions.begin() as s:
            self.control(s)
            case = s.scalar(select(C).where(C.id == data.id).with_for_update())
            if case is None:
                raise CollectionError("case_not_found", 404)
            if data.action in {"resume", "redirect", "ask"}:
                policy.require_active(s, "support", case)
            existing = s.scalar(
                select(E).where(E.case_id == case.id, E.request_id == data.request_id)
            )
            if existing:
                if existing.kind != data.action or existing.text != data.text:
                    raise CollectionError("support_request_conflict")
                return {"id": existing.id}
            row = E(
                case_id=case.id,
                request_id=data.request_id,
                kind=data.action,
                text=data.text,
                status="queued" if data.action == "ask" else "recorded",
                created_at=datetime.now(UTC),
            )
            s.add(row)
            if data.action != "ask":
                case.revision += 1
                if data.action == "pause":
                    case.status = "paused"
                elif data.action == "dismiss":
                    case.status = "dismissed"
                elif case.status != "dismissed" or data.action == "resume":
                    case.status, case.error_code = "queued", None
                case.updated_at = datetime.now(UTC)
            s.flush()
            return {"id": row.id}

    def recover(self):
        with self.sessions.begin() as s:
            self.control(s)
            s.execute(
                update(I)
                .where(I.status == "running")
                .values(status="failed", error_code="runner_interrupted")
            )
            s.execute(
                update(C)
                .where(C.status == "analyzing")
                .values(status="failed", error_code="runner_interrupted")
            )
            s.execute(update(E).where(E.status == "running").values(status="failed"))

    def claim(self):
        with self.sessions.begin() as s:
            control = self.control(s)
            if control.paused or not control.activated_at:
                return None
            ask = s.scalar(
                select(E)
                .where(
                    E.kind == "ask",
                    E.status == "queued",
                    E.case_id.in_(select(C.id).where(~policy.blocked("support", C))),
                )
                .order_by(E.created_at, E.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if ask:
                ask.status = "running"
                case = s.get(C, ask.case_id)
                return {
                    "kind": "chat",
                    "id": ask.id,
                    "epoch": control.epoch,
                    "case_id": case.id,
                    "revision": case.revision,
                    "human_revision": policy.epoch(s, "support", case),
                    "payload": {
                        "context": case.context,
                        "report": case.report,
                        "question": ask.text,
                        "status": case.status,
                        "history": [
                            {"kind": entry.kind, "text": entry.text[:4000]}
                            for entry in reversed(
                                list(
                                    s.scalars(
                                        select(E)
                                        .where(E.case_id == case.id, E.id != ask.id)
                                        .order_by(E.created_at.desc(), E.id.desc())
                                        .limit(12)
                                    )
                                )
                            )
                        ],
                    },
                }
            case = s.scalar(
                select(C)
                .where(C.status == "queued", ~policy.blocked("support", C))
                .order_by(C.updated_at, C.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if case:
                case.status = "analyzing"
                redirects = list(
                    s.scalars(
                        select(E.text)
                        .where(E.case_id == case.id, E.kind == "redirect")
                        .order_by(E.created_at, E.id)
                    )
                )
                return {
                    "kind": "analyze",
                    "id": case.id,
                    "epoch": control.epoch,
                    "revision": case.revision,
                    "human_revision": policy.epoch(s, "support", case),
                    "payload": {"context": case.context, "directions": redirects[-10:]},
                }
            intake = s.scalar(
                select(I)
                .where(I.status == "queued")
                .order_by(I.created_at, I.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if intake:
                intake.status = "running"
                payload = self.snapshot(s, intake.variant_id)
                held_case = s.scalar(
                    select(C).where(
                        C.source_scope == intake.source_scope,
                        C.channel_id == intake.channel_id,
                        C.conversation_id == payload["conversation_id"],
                    )
                )
                if held_case and not policy.active(s, "support", held_case):
                    intake.status = "ignored"
                    intake.decision = {
                        "action": "human",
                        "reason": "Disposición humana conservada.",
                    }
                    return None
                return {
                    "kind": "classify",
                    "id": intake.id,
                    "epoch": control.epoch,
                    "human_revision": policy.epoch(s, "support", held_case) if held_case else 0,
                    "payload": payload,
                }
            return None

    def finish(self, job, result=None, error=None):
        now = datetime.now(UTC)
        with self.sessions.begin() as s:
            control = self.control(s)
            model = {"classify": I, "analyze": C, "chat": E}[job["kind"]]
            row = s.scalar(select(model).where(model.id == job["id"]).with_for_update())
            if row is None or row.status != (
                "analyzing" if job["kind"] == "analyze" else "running"
            ):
                return
            stale = control.paused or control.epoch != job["epoch"]
            if job["kind"] in {"analyze", "chat"}:
                target = row if job["kind"] == "analyze" else s.get(C, job["case_id"])
                if not policy.active(s, "support", target) or policy.epoch(
                    s, "support", target
                ) != job.get("human_revision", 0):
                    if job["kind"] == "chat":
                        row.status = "cancelled"
                    return
            if job["kind"] == "analyze":
                if row.revision != job["revision"] or row.status != "analyzing":
                    return
            if job["kind"] == "chat":
                case = s.get(C, job["case_id"])
                stale = stale or case.revision != job["revision"]
            if stale:
                row.status = "queued"
                return
            if error:
                row.status = "failed"
                if hasattr(row, "error_code"):
                    row.error_code = error
                return
            if job["kind"] == "classify":
                manual = self.snapshot(s, row.variant_id)["human_categories"]
                if manual and manual != ["support"]:
                    row.status = "ignored"
                    row.decision = {
                        "action": "manual",
                        "reason": "Clasificación humana conservada; sin investigación automática.",
                    }
                    return
                row.decision = result
                row.status = "ignored" if result["action"] != "support" else "support"
                if row.status == "ignored":
                    return
                payload = job["payload"]
                if payload["relation_status"] == "conflict":
                    row.status, row.error_code = "failed", "conversation_relation_conflict"
                    return
                case = s.scalar(
                    select(C)
                    .where(
                        C.source_scope == row.source_scope,
                        C.channel_id == row.channel_id,
                        C.conversation_id == payload["conversation_id"],
                    )
                    .with_for_update()
                )
                if case is not None and (
                    not policy.active(s, "support", case)
                    or policy.epoch(s, "support", case) != job.get("human_revision", 0)
                ):
                    row.status = "ignored"
                    row.case_id = case.id
                    row.decision = {"action": "human", "reason": "Disposición humana conservada."}
                    return
                if case is None:
                    case = C(
                        source_scope=row.source_scope,
                        channel_id=row.channel_id,
                        conversation_id=payload["conversation_id"],
                        anchor_id=row.variant_id,
                        title=result["title"],
                        status="queued",
                        revision=1,
                        context=payload,
                        created_at=now,
                        updated_at=now,
                    )
                    s.add(case)
                    s.flush()
                else:
                    case.context = payload
                    if case.status not in {"paused", "dismissed"} and policy.active(
                        s, "support", case
                    ):
                        case.status = "queued"
                    case.revision += 1
                    case.updated_at = now
                row.case_id = case.id
                s.add(
                    E(
                        case_id=case.id,
                        request_id=uuid4(),
                        kind="classification",
                        text=result["reason"],
                        status="recorded",
                        payload=result,
                        created_at=now,
                    )
                )

            elif job["kind"] == "analyze":
                row.report = {
                    **result,
                    "source_limits": SOURCE_LIMITS,
                    "coverage": "slack_only",
                    "revision": job["revision"],
                }
                row.status, row.error_code = "blocked", "source_scope_pending"
                row.updated_at = now
                s.add(
                    E(
                        case_id=row.id,
                        request_id=uuid4(),
                        kind="preliminary",
                        text="Preliminar basado solo en Slack; logs y código no consultados.",
                        status="recorded",
                        payload=row.report,
                        created_at=now,
                    )
                )
            else:
                row.status = "answered"
                s.add(
                    E(
                        case_id=row.case_id,
                        request_id=uuid4(),
                        kind="answer",
                        text=result["text"],
                        status="recorded",
                        payload={**result, "reply_to": str(row.id)},
                        created_at=now,
                    )
                )

    def require_current(self, job):
        with self.sessions.begin() as s:
            c = self.control(s)
            if c.paused or c.epoch != job["epoch"]:
                raise CollectionError("human_work_cancelled")
            if job["kind"] == "classify":
                intake = s.get(I, job["id"])
                if intake is None or intake.status != "running":
                    raise CollectionError("human_work_cancelled")
                held = s.scalar(
                    select(C).where(
                        C.source_scope == intake.source_scope,
                        C.channel_id == intake.channel_id,
                        C.conversation_id == job["payload"]["conversation_id"],
                    )
                )
                if held is not None:
                    policy.require_active(s, "support", held)
                    if policy.epoch(s, "support", held) != job.get("human_revision", 0):
                        raise CollectionError("human_work_cancelled")
                return
            target = s.get(C, job["case_id"] if job["kind"] == "chat" else job["id"])
            if job["kind"] == "chat":
                entry = s.get(E, job["id"])
                if entry is None or entry.status != "running":
                    raise CollectionError("human_work_cancelled")
            elif target is None or target.status != "analyzing":
                raise CollectionError("human_work_cancelled")
            if (
                target.revision != job["revision"]
                or not policy.active(s, "support", target)
                or policy.epoch(s, "support", target) != job.get("human_revision", 0)
            ):
                raise CollectionError("human_work_cancelled")
