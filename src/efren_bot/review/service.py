from contextlib import nullcontext
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, case, exists, func, select, update
from sqlalchemy.dialects.postgresql import insert

from efren_bot.collection.models import CollectionCapture, CollectionRun
from efren_bot.collection.models import CollectionMessage as M
from efren_bot.collection.service import CollectionError, view
from efren_bot.human import policy
from efren_bot.review.gitlab import PROJECTS, links, parse_url
from efren_bot.review.models import ReviewControl as Control
from efren_bot.review.models import ReviewEntry as Entry
from efren_bot.review.models import ReviewItem as Item
from efren_bot.review.models import ReviewProposal as Proposal
from efren_bot.review.models import ReviewRequest as Request
from efren_bot.support.service import SupportService

PHASES = {"capture": 0, "plan": 1, "context": 2, "analyze": 3}
DEMO_SCOPE = "slack-account:U0B6T31KXSN:default-workspace"


class ReviewService:
    def __init__(self, sessions):
        self.sessions = sessions

    def control(self, s):
        s.execute(insert(Control).values(id=1, paused=True, epoch=1).on_conflict_do_nothing())
        return s.scalar(select(Control).where(Control.id == 1).with_for_update())

    def command(self, action):
        with self.sessions.begin() as s:
            c = self.control(s)
            if action not in {"activate", "pause", "resume"}:
                raise CollectionError("invalid_action", 422)
            if action != "pause":
                c.activated_at = c.activated_at or datetime.now(UTC)
            c.paused = action == "pause"
            c.epoch += 1
            return view(c)

    def heartbeat(self):
        with self.sessions.begin() as s:
            self.control(s).runner_seen_at = datetime.now(UTC)

    def scan(self):
        with self.sessions.begin() as s:
            c = self.control(s)
            if not c.activated_at:
                return 0
            known = exists(
                select(Request.id).where(
                    Request.source_scope == M.source_scope,
                    Request.channel_id == M.channel_id,
                    Request.message_id == M.message_id,
                )
            )
            rows = s.execute(
                select(M.source_scope, M.channel_id, M.message_id)
                .join(CollectionCapture, CollectionCapture.id == M.capture_id)
                .join(CollectionRun, CollectionRun.id == CollectionCapture.run_id)
                .where(~known)
                .group_by(M.source_scope, M.channel_id, M.message_id)
                .having(
                    and_(
                        func.min(M.stored_at) >= c.activated_at,
                        func.min(M.occurred_at) >= c.activated_at,
                        ~func.bool_or(M.is_historical),
                        ~func.bool_or(CollectionRun.trigger == "import"),
                    )
                )
                .order_by(func.min(M.stored_at), M.source_scope, M.channel_id, M.message_id)
                .limit(100)
            ).all()
            for scope, channel, mid in rows:
                m = s.scalar(
                    select(M)
                    .where(M.source_scope == scope, M.channel_id == channel, M.message_id == mid)
                    .order_by(M.stored_at, M.id)
                    .limit(1)
                )
                s.add(
                    Request(
                        source_scope=scope,
                        channel_id=channel,
                        message_id=mid,
                        variant_id=m.id,
                        demo=False,
                        status="queued",
                        context={},
                        created_at=datetime.now(UTC),
                    )
                )
            return len(rows)

    def demo(self, data):
        with self.sessions.begin() as s:
            self.control(s)
            row = s.scalar(
                select(M)
                .where(
                    M.source_scope == DEMO_SCOPE,
                    M.channel_id == "C07SRBE0V1T",
                    M.message_id == "1792770316.988339",
                )
                .order_by(M.observed_at.desc())
                .limit(1)
            )
            if row is None:
                raise CollectionError("approved_demo_source_missing", 404)
            old = s.scalar(
                select(Request).where(
                    Request.source_scope == row.source_scope,
                    Request.channel_id == row.channel_id,
                    Request.message_id == row.message_id,
                )
            )
            if old:
                return {"id": old.id}
            context = SupportService(self.sessions).snapshot(s, row.id)
            context.pop("sources", None)
            request = Request(
                request_key=data.request_id,
                source_scope=row.source_scope,
                channel_id=row.channel_id,
                message_id=row.message_id,
                variant_id=row.id,
                demo=True,
                status="accepted",
                context=context,
                decision={
                    "requested": True,
                    "reason": "Prueba histórica aislada autorizada; todas las MRs del hilo.",
                },
                created_at=datetime.now(UTC),
            )
            s.add(request)
            s.flush()
            self.targets(s, request, links("\n".join(m["text"] for m in context["messages"])))
            return {"id": request.id}

    def targets(self, s, request, urls):
        for url in dict.fromkeys(urls):
            project, iid = parse_url(url)
            s.add(
                Item(
                    request_id=request.id,
                    project_path=project,
                    mr_iid=iid,
                    url=url,
                    title=f"!{iid}",
                    status="queued" if project in PROJECTS else "blocked",
                    phase="capture",
                    revision=1,
                    error_code=None if project in PROJECTS else "project_not_approved",
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )

    def list(self):
        with self.sessions.begin() as s:
            c = self.control(s)
            rows = s.execute(
                select(Item, Request.demo)
                .join(Request, Request.id == Item.request_id)
                .order_by(Item.updated_at.desc(), Item.id)
                .limit(100)
            ).all()
            requests = s.scalars(
                select(Request).order_by(Request.created_at.desc()).limit(30)
            ).all()
            return {
                "control": {
                    **view(c),
                    "runner_available": bool(
                        c.runner_seen_at
                        and datetime.now(UTC) - c.runner_seen_at < timedelta(seconds=45)
                    ),
                },
                "projects": list(PROJECTS),
                "publication_enabled": True,
                "items": [
                    {
                        **{
                            k: v
                            for k, v in view(i).items()
                            if k not in {"snapshot", "plan", "report"}
                        },
                        "demo": demo,
                        "head_sha": i.snapshot.get("refs", {}).get("head_sha"),
                        "limitations": i.snapshot.get("limitations", []),
                        "source_count": len(i.snapshot.get("sources", [])),
                        "proposal_count": s.scalar(
                            select(func.count())
                            .select_from(Proposal)
                            .where(
                                Proposal.item_id == i.id,
                                Proposal.revision == i.revision,
                                Proposal.status != "discarded",
                            )
                        ),
                    }
                    for i, demo in rows
                ],
                "requests": [
                    {k: v for k, v in view(r).items() if k != "context"} for r in requests
                ],
            }

    def detail(self, identifier):
        with self.sessions() as s:
            item = s.get(Item, identifier)
            if item is None:
                raise CollectionError("review_not_found", 404)
            req = s.get(Request, item.request_id)
            return {
                "item": view(item),
                "request": view(req),
                "proposals": [
                    view(p)
                    for p in s.scalars(
                        select(Proposal).where(Proposal.item_id == item.id).order_by(Proposal.id)
                    )
                ],
                "entries": [
                    view(e)
                    for e in s.scalars(
                        select(Entry)
                        .where(Entry.item_id == item.id)
                        .order_by(Entry.created_at, Entry.id)
                    )
                ],
            }

    def act(self, data, *, session=None):
        with nullcontext(session) if session is not None else self.sessions.begin() as s:
            c = self.control(s)
            item = s.scalar(select(Item).where(Item.id == data.id).with_for_update())
            if item is None:
                raise CollectionError("review_not_found", 404)
            payload = data.model_dump(mode="json")
            existing = s.scalar(
                select(Entry).where(Entry.item_id == item.id, Entry.request_key == data.request_id)
            )
            if existing:
                if existing.payload.get("input") != payload:
                    raise CollectionError("review_request_conflict")
                return {"id": existing.id}
            if item.revision != data.revision:
                raise CollectionError("review_changed")
            if data.action in {"resume", "redirect", "publish", "ask"}:
                policy.require_active(s, "review", item)
            if data.action == "publish":
                req = s.get(Request, item.request_id)
                if req.demo:
                    raise CollectionError("demo_read_only")
                if c.paused:
                    raise CollectionError("reviews_paused")
                if item.status != "ready":
                    raise CollectionError("review_not_current_and_complete")
                proposal = s.scalar(
                    select(Proposal)
                    .where(Proposal.id == data.proposal_id, Proposal.item_id == item.id)
                    .with_for_update()
                )
                if (
                    proposal is None
                    or proposal.status != "private"
                    or proposal.revision != item.revision
                    or proposal.version != data.proposal_version
                ):
                    raise CollectionError("proposal_changed")
                if s.scalar(
                    select(Entry.id).where(
                        Entry.item_id == item.id,
                        Entry.kind == "publish",
                        Entry.status.in_(["queued", "running", "sending", "uncertain"]),
                        Entry.payload["proposal_id"].astext == str(proposal.id),
                    )
                ):
                    raise CollectionError("publication_already_requested")
                selected = next(
                    d for d in item.snapshot["diffs"] if d["path"] == proposal.finding["path"]
                )
                payload = {
                    "input": payload,
                    "proposal_id": str(proposal.id),
                    "version": proposal.version,
                    "review_revision": item.revision,
                    "authorization_epoch": c.epoch,
                    "human_revision": policy.epoch(s, "review", item),
                    "expires_at": (datetime.now(UTC) + timedelta(minutes=15)).isoformat(),
                    "approved": {
                        "body": proposal.body,
                        "finding": proposal.finding,
                        "refs": item.snapshot["refs"],
                        "old_path": selected["old_path"],
                    },
                }
                entry = Entry(
                    item_id=item.id,
                    request_key=data.request_id,
                    kind="publish",
                    text=proposal.body,
                    status="queued",
                    payload=payload,
                    created_at=datetime.now(UTC),
                )
                s.add(entry)
                s.flush()
                return {"id": entry.id}
            if data.action in {"ask", "redirect", "edit"} and not data.text.strip():
                raise CollectionError("text_required", 422)
            if data.action in {"edit", "discard"}:
                p = s.scalar(
                    select(Proposal)
                    .where(Proposal.id == data.proposal_id, Proposal.item_id == item.id)
                    .with_for_update()
                )
                if p is None:
                    raise CollectionError("proposal_not_found", 404)
                if (
                    p.revision != item.revision
                    or p.version != data.proposal_version
                    or p.status != "private"
                ):
                    raise CollectionError("proposal_changed")
                if data.action == "edit":
                    p.body = data.text.strip()
                else:
                    p.status = "discarded"
                p.version += 1
            elif data.action != "ask":
                item.revision += 1
                if data.action == "pause":
                    item.status = "paused"
                else:
                    if item.snapshot or item.report:
                        s.add(
                            Entry(
                                item_id=item.id,
                                kind="archive",
                                text="Revisión anterior conservada.",
                                status="recorded",
                                payload={
                                    "snapshot": item.snapshot,
                                    "plan": item.plan,
                                    "report": item.report,
                                    "error_code": item.error_code,
                                    "revision": item.revision - 1,
                                    "phase": item.phase,
                                },
                                created_at=datetime.now(UTC),
                            )
                        )
                    item.status, item.phase = "queued", "capture"
                    item.error_code = None
            entry = Entry(
                item_id=item.id,
                request_key=data.request_id,
                kind=data.action,
                text=data.text.strip(),
                status="queued" if data.action == "ask" else "recorded",
                payload={"input": payload},
                created_at=datetime.now(UTC),
            )
            s.add(entry)
            s.flush()
            item.updated_at = datetime.now(UTC)
            return {"id": entry.id}

    def recover(self):
        with self.sessions.begin() as s:
            self.control(s)
            s.execute(
                update(Request)
                .where(Request.status == "running")
                .values(status="failed", error_code="runner_interrupted")
            )
            s.execute(
                update(Item)
                .where(Item.status == "running")
                .values(status="failed", error_code="runner_interrupted")
            )
            s.execute(update(Entry).where(Entry.status == "running").values(status="failed"))
            for entry in s.scalars(select(Entry).where(Entry.status == "sending")):
                entry.status = "uncertain"
                proposal = s.get(Proposal, entry.payload.get("proposal_id"))
                if proposal:
                    proposal.status = "uncertain"

    def claim(self):
        with self.sessions.begin() as s:
            c = self.control(s)
            if c.paused or not c.activated_at:
                return None
            ask = s.scalar(
                select(Entry)
                .where(
                    Entry.kind.in_(["ask", "publish"]),
                    Entry.status == "queued",
                    Entry.item_id.in_(select(Item.id).where(~policy.blocked("review", Item))),
                )
                .order_by(Entry.created_at, Entry.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if ask:
                item = s.get(Item, ask.item_id)
                ask.status = "running"
                if ask.kind == "publish":
                    return {
                        "kind": "publish",
                        "id": ask.id,
                        "epoch": c.epoch,
                        "revision": item.revision,
                        "human_revision": policy.epoch(s, "review", item),
                        "item_id": item.id,
                        "project": item.project_path,
                        "iid": item.mr_iid,
                        "payload": ask.payload,
                    }
                return {
                    "kind": "chat",
                    "id": ask.id,
                    "epoch": c.epoch,
                    "revision": item.revision,
                    "human_revision": policy.epoch(s, "review", item),
                    "item_id": item.id,
                    "payload": {
                        "snapshot": item.snapshot,
                        "report": item.report,
                        "question": ask.text,
                        "status": item.status,
                        "phase": item.phase,
                    },
                }
            request = s.scalar(
                select(Request)
                .where(Request.status == "queued")
                .order_by(Request.created_at, Request.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if request:
                context = SupportService(self.sessions).snapshot(s, request.variant_id)
                context.pop("sources", None)
                request.context = context
                request.status = "running"
                return {"kind": "detect", "id": request.id, "epoch": c.epoch, "payload": context}
            item = s.scalar(
                select(Item)
                .where(Item.status == "queued", ~policy.blocked("review", Item))
                .order_by(case(PHASES, value=Item.phase), Item.updated_at, Item.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if item:
                item.status = "running"
                related = list(s.scalars(select(Item).where(Item.request_id == item.request_id)))
                directions = list(
                    s.scalars(
                        select(Entry.text)
                        .where(Entry.item_id == item.id, Entry.kind == "redirect")
                        .order_by(Entry.created_at)
                        .limit(10)
                    )
                )
                return {
                    "kind": item.phase,
                    "id": item.id,
                    "epoch": c.epoch,
                    "revision": item.revision,
                    "human_revision": policy.epoch(s, "review", item),
                    "project": item.project_path,
                    "iid": item.mr_iid,
                    "payload": {
                        "item_id": str(item.id),
                        "request_context": s.get(Request, item.request_id).context,
                        "snapshot": item.snapshot,
                        "plan": item.plan,
                        "directions": directions,
                        "related": [
                            {
                                "item_id": str(r.id),
                                "project": r.project_path,
                                "iid": r.mr_iid,
                                "title": r.title,
                                "refs": r.snapshot.get("refs"),
                                "changed_paths": [d["path"] for d in r.snapshot.get("diffs", [])],
                            }
                            for r in related
                        ],
                    },
                }
            return None

    def finish_detection(self, job, result=None, error=None):
        with self.sessions.begin() as s:
            c = self.control(s)
            request = s.get(Request, job["id"])
            if request.status != "running":
                return
            if c.paused or c.epoch != job["epoch"]:
                request.status = "queued"
                return
            if error:
                request.status, request.error_code = "failed", error
                return
            request.decision = result
            if not result["requested"]:
                request.status = "ignored"
                return
            context = request.context
            if context.get("relation_status") == "conflict":
                request.status, request.error_code = "failed", "conversation_relation_conflict"
                return
            trigger = next(m for m in context["messages"] if m["id"] == context["trigger_id"])
            direct = links(trigger["text"])
            selected = set(result["context_urls"])
            inherited = list(
                dict.fromkeys(
                    url
                    for message in context["messages"]
                    if selected.intersection(links(message["text"]))
                    for url in links(message["text"])
                )
            )
            urls = direct or inherited
            request.status = "accepted" if urls else "ignored"
            self.targets(s, request, urls)

    def finish_item(self, job, value=None, *, next_phase=None, error=None):
        with self.sessions.begin() as s:
            c = self.control(s)
            item = s.scalar(select(Item).where(Item.id == job["id"]).with_for_update())
            if (
                item.revision != job["revision"]
                or item.status != "running"
                or item.phase != job["kind"]
            ):
                return
            if not policy.active(s, "review", item) or policy.epoch(s, "review", item) != job.get(
                "human_revision", 0
            ):
                return
            if c.paused or c.epoch != job["epoch"]:
                item.status = "queued"
                return
            if error:
                item.status, item.error_code = "failed", error
                s.add(
                    Entry(
                        item_id=item.id,
                        kind="stage_failed",
                        status="failed",
                        text=error,
                        payload={"phase": item.phase, "revision": item.revision},
                        created_at=datetime.now(UTC),
                    )
                )
            elif job["kind"] == "capture":
                item.snapshot = value
                item.title = value.get("title", item.title)
                item.status, item.phase = "queued", "plan"
            elif job["kind"] == "plan":
                item.plan = value
                item.status, item.phase = "queued", "context"
            elif job["kind"] == "context":
                item.snapshot = value
                item.status, item.phase = "queued", "analyze"
            else:
                item.report = {**value, "revision": item.revision}
                incomplete = (
                    item.snapshot.get("limitations")
                    or value.get("pending")
                    or any(check["status"] == "limited" for check in value.get("checks", []))
                )
                item.status = "partial" if incomplete else "ready"
                for finding in value["findings"]:
                    s.add(
                        Proposal(
                            item_id=item.id,
                            revision=item.revision,
                            version=1,
                            body=finding["comment"],
                            finding=finding,
                            status="private",
                        )
                    )
                s.add(
                    Entry(
                        item_id=item.id,
                        kind="report",
                        status="recorded",
                        text=value["summary"],
                        payload={"revision": item.revision},
                        created_at=datetime.now(UTC),
                    )
                )
            item.updated_at = datetime.now(UTC)

    def finish_chat(self, job, result=None, error=None):
        with self.sessions.begin() as s:
            c = self.control(s)
            entry = s.get(Entry, job["id"])
            if entry.status != "running":
                return False
            item = s.get(Item, job["item_id"])
            if not policy.active(s, "review", item) or policy.epoch(s, "review", item) != job.get(
                "human_revision", 0
            ):
                entry.status = "cancelled"
                return
            if c.paused or c.epoch != job["epoch"] or item.revision != job["revision"]:
                entry.status = "queued"
                return
            entry.status = "failed" if error else "answered"
            if result:
                s.add(
                    Entry(
                        item_id=item.id,
                        kind="answer",
                        status="recorded",
                        text=result["text"],
                        payload=result,
                        created_at=datetime.now(UTC),
                    )
                )

    def admit_publish(self, job, current):
        with self.sessions.begin() as s:
            c = self.control(s)
            item = s.get(Item, job["item_id"])
            entry = s.get(Entry, job["id"])
            if entry.status != "running":
                return False
            req = s.get(Request, item.request_id)
            p = s.get(Proposal, entry.payload["proposal_id"])
            valid = (
                not c.paused
                and c.epoch == job["epoch"]
                and c.epoch == entry.payload.get("authorization_epoch")
                and policy.active(s, "review", item)
                and policy.epoch(s, "review", item) == entry.payload.get("human_revision", 0)
                and bool(entry.payload.get("expires_at"))
                and datetime.fromisoformat(entry.payload["expires_at"]) > datetime.now(UTC)
                and not req.demo
                and item.status == "ready"
                and item.revision == entry.payload["review_revision"]
                and p
                and p.status == "private"
                and p.version == entry.payload["version"]
                and p.body == entry.payload["approved"]["body"]
                and current.get("state") == "opened"
                and current.get("diff_refs") == entry.payload["approved"]["refs"]
            )
            if not valid:
                entry.status = "cancelled"
                entry.text = (
                    "Publicación cancelada: cambió la versión, decisión o estado. Revalidar."
                )
                return False
            entry.status = "sending"
            p.status = "sending"
            return True

    def finish_publish(self, job, remote_id=None):
        with self.sessions.begin() as s:
            self.control(s)
            entry = s.get(Entry, job["id"])
            if entry.status != "sending":
                return
            proposal = s.get(Proposal, entry.payload["proposal_id"])
            entry.status = "published" if remote_id else "uncertain"
            proposal.status = entry.status
            proposal.remote_id = remote_id

    def fail_publish_before_send(self, job):
        with self.sessions.begin() as s:
            self.control(s)
            entry = s.get(Entry, job["id"])
            if entry.status == "running":
                entry.status = "failed"

    def require_read(self, job, project, iid):
        self.require_current(job)
        with self.sessions() as s:
            identifier = job["item_id"] if job["kind"] in {"chat", "publish"} else job["id"]
            item = s.get(Item, identifier)
            request = s.get(Request, item.request_id)
            targets = s.scalars(
                select(Item)
                .join(Request)
                .where(
                    Request.source_scope == request.source_scope,
                    Item.project_path == project,
                    Item.mr_iid == iid,
                )
            )
            for target in targets:
                policy.require_active(s, "review", target)

    def require_current(self, job):
        with self.sessions.begin() as s:
            c = self.control(s)
            if c.paused or c.epoch != job["epoch"]:
                raise CollectionError("human_work_cancelled")
            if job["kind"] == "detect":
                request = s.get(Request, job["id"])
                if request is None or request.status != "running":
                    raise CollectionError("human_work_cancelled")
                return
            identifier = job["item_id"] if job["kind"] in {"chat", "publish"} else job["id"]
            item = s.get(Item, identifier)
            if job["kind"] in {"chat", "publish"}:
                entry = s.get(Entry, job["id"])
                if entry is None or entry.status != "running":
                    raise CollectionError("human_work_cancelled")
            elif item is None or item.status != "running" or item.phase != job["kind"]:
                raise CollectionError("human_work_cancelled")
            if (
                item.revision != job["revision"]
                or not policy.active(s, "review", item)
                or policy.epoch(s, "review", item) != job.get("human_revision", 0)
            ):
                raise CollectionError("human_work_cancelled")
