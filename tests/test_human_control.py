from datetime import UTC, datetime
from uuid import uuid4

import pytest
from test_support import message

from efren_bot.collection.service import CollectionError
from efren_bot.human.contracts import Decision
from efren_bot.human.service import HumanService
from efren_bot.review.contracts import Action
from efren_bot.review.service import ReviewService
from efren_bot.support.service import SupportService

pytestmark = pytest.mark.integration
CORE = "https://gitlab.com/konfio/organization/guilds/core/core/-/merge_requests/"


def review(database):
    from efren_bot.collection.models import CollectionMessage

    service = ReviewService(database)
    service.command("activate")
    mid = message(database, datetime.now(UTC))
    with database.begin() as s:
        s.get(CollectionMessage, mid).text = CORE + "8573"
    service.scan()
    service.finish_detection(
        service.claim(), {"requested": True, "reason": "review", "context_urls": []}
    )
    return service, service.list()["items"][0]


def test_delegate_invalidates_work_and_cannot_be_undone_by_legacy_resume(database):
    service, item = review(database)
    job = service.claim()
    human = HumanService(database)
    command = Decision(
        domain="review",
        id=item["id"],
        revision=1,
        control_revision=0,
        request_id=uuid4(),
        action="delegate",
        text="Otra persona lo tomó",
    )
    assert human.act(command) == human.act(command)
    service.finish_item(job, {"title": "must not overwrite"})
    assert service.detail(item["id"])["item"]["title"] != "must not overwrite"
    assert service.claim() is None
    with pytest.raises(CollectionError):
        service.act(Action(id=item["id"], request_id=uuid4(), revision=2, action="resume"))
    with pytest.raises(CollectionError):
        human.act(command.model_copy(update={"request_id": uuid4()}))


def test_rerequest_does_not_bypass_delegation(database):
    service, item = review(database)
    human = HumanService(database)
    human.act(
        Decision(
            domain="review",
            id=item["id"],
            revision=1,
            control_revision=0,
            request_id=uuid4(),
            action="delegate",
        )
    )
    from efren_bot.collection.models import CollectionMessage

    mid = message(database, datetime.now(UTC))
    with database.begin() as s:
        s.get(CollectionMessage, mid).text = CORE + "8573"
    service.scan()
    job = service.claim()
    assert job["kind"] == "detect"
    service.finish_detection(job, {"requested": True, "reason": "again", "context_urls": []})
    assert service.claim() is None


@pytest.fixture
def completed(database):
    from test_review_model import report, snapshot

    store, item = review(database)
    store.finish_item(store.claim(), {**snapshot(), "mr_state": "opened"})
    store.finish_item(store.claim(), {"objective": "Trace", "reads": [], "hypotheses": []})
    store.finish_item(store.claim(), {**snapshot(), "mr_state": "opened"})
    store.finish_item(store.claim(), report())
    return store, store.list()["items"][0]


def test_approval_is_exact_and_delegation_cancels_pending_send(database, completed):
    store, item = completed
    human = HumanService(database)
    action = human.detail("review", item["id"])["request"]["actions"][0]
    decision = Decision(
        domain="review",
        id=item["id"],
        revision=1,
        control_revision=0,
        request_id=uuid4(),
        action="approve",
        proposal_id=action["id"],
        fingerprint=action["fingerprint"],
    )
    with pytest.raises(CollectionError):
        human.act(decision.model_copy(update={"fingerprint": "0" * 64}))
    result = human.act(decision)
    assert human.act(decision) == result
    job = store.claim()
    human.act(
        Decision(
            domain="review",
            id=item["id"],
            revision=1,
            control_revision=0,
            request_id=uuid4(),
            action="delegate",
        )
    )
    assert not store.admit_publish(
        job, {"state": "opened", "diff_refs": job["payload"]["approved"]["refs"]}
    )
    assert store.detail(item["id"])["proposals"][0]["status"] == "private"


def test_expired_approval_and_restart_are_not_new_permission(database, completed):
    from datetime import timedelta

    from efren_bot.review.models import ReviewEntry

    store, item = completed
    human = HumanService(database)
    action = human.detail("review", item["id"])["request"]["actions"][0]
    result = human.act(
        Decision(
            domain="review",
            id=item["id"],
            revision=1,
            control_revision=0,
            request_id=uuid4(),
            action="approve",
            proposal_id=action["id"],
            fingerprint=action["fingerprint"],
        )
    )
    from uuid import UUID

    with database.begin() as s:
        entry = s.get(ReviewEntry, UUID(result["entry_id"]))
        entry.payload = {
            **entry.payload,
            "expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        }
    job = store.claim()
    assert not store.admit_publish(
        job, {"state": "opened", "diff_refs": job["payload"]["approved"]["refs"]}
    )
    store.recover()
    assert store.claim() is None


def test_support_delegation_replay_and_blocked_slack_capability(database):
    from efren_bot.support.contracts import CaseAction

    store = SupportService(database)
    store.command("activate")
    identifier = message(database, datetime.now(UTC), mid="support-root", root="support-root")
    store.scan()
    job = store.claim()
    store.finish(
        job,
        {
            "action": "support",
            "title": "Synthetic support",
            "reason": "New report",
            "evidence_ids": [str(identifier)],
        },
    )
    case = store.list()["cases"][0]
    job = store.claim()
    human = HumanService(database)
    human.act(
        Decision(
            domain="support",
            id=case["id"],
            revision=1,
            control_revision=0,
            request_id=uuid4(),
            action="delegate",
        )
    )
    store.finish(
        job,
        {
            "reported": ["Must not overwrite"],
            "hypotheses": [],
            "missing": [],
            "slack_draft": "preliminary",
            "evidence_ids": [str(identifier)],
        },
    )
    assert not store.detail(case["id"])["case"]["report"]
    with pytest.raises(CollectionError):
        store.act(CaseAction(id=case["id"], request_id=uuid4(), action="resume"))
    message(database, datetime.now(UTC), root="support-root")
    store.scan()
    assert store.claim() is None
    human.act(
        Decision(
            domain="support",
            id=case["id"],
            revision=2,
            control_revision=1,
            request_id=uuid4(),
            action="continue",
        )
    )
    job = store.claim()
    assert job["kind"] == "analyze"
    store.finish(
        job,
        {
            "reported": ["Synthetic"],
            "hypotheses": [],
            "missing": ["Logs"],
            "slack_draft": "Preliminary, only Slack",
            "evidence_ids": [str(identifier)],
        },
    )
    descriptor = human.detail("support", case["id"])["request"]["actions"][0]
    approve = Decision(
        domain="support",
        id=case["id"],
        revision=3,
        control_revision=2,
        request_id=uuid4(),
        action="approve",
        proposal_id=case["id"],
        fingerprint=descriptor["fingerprint"],
    )
    with pytest.raises(CollectionError) as error:
        human.act(approve)
    assert error.value.code == "human_capability_blocked"
    human.act(approve.model_copy(update={"action": "deny", "request_id": uuid4()}))
    assert human.detail("support", case["id"])["request"]["actions"][0]["denied"]


def test_reader_stops_before_next_get_when_delegated(database, monkeypatch):
    from subprocess import CompletedProcess

    from efren_bot.review.gitlab import Gitlab

    store, item = review(database)
    job = store.claim()
    human = HumanService(database)
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        human.act(
            Decision(
                domain="review",
                id=item["id"],
                revision=1,
                control_revision=0,
                request_id=uuid4(),
                action="delegate",
            )
        )
        return CompletedProcess(args, 0, b"{}", b"")

    monkeypatch.setattr("efren_bot.review.gitlab.subprocess.run", run)
    reader = Gitlab(item["project_path"], item["mr_iid"])
    reader.before_read = lambda: store.require_current(job)
    reader.metadata()
    with pytest.raises(CollectionError):
        reader.metadata()
    assert len(calls) == 1


def test_human_http_is_closed_and_does_not_expose_generic_execution(database, pg_engine):
    from fastapi.testclient import TestClient

    from efren_bot.api import create_app

    headers = {"Host": "127.0.0.1:8000", "Origin": "http://127.0.0.1:5173", "X-Efren-Local": "1"}
    with TestClient(create_app(engine=pg_engine)) as client:
        assert (
            client.post("/api/collection/human/list", headers=headers, json={}).status_code == 401
        )
        headers["X-Collection-Token"] = client.get(
            "/api/collection/session", headers=headers
        ).json()["token"]
        assert (
            client.post("/api/collection/human/list", headers=headers, json={}).status_code == 200
        )
        response = client.post(
            "/api/collection/human/act",
            headers=headers,
            json={
                "domain": "support",
                "id": str(uuid4()),
                "request_id": str(uuid4()),
                "revision": 1,
                "control_revision": 0,
                "action": "run_tests",
                "command": "private_data",
            },
        )
        assert response.status_code == 422 and "private_data" not in response.text


def decide(human, domain, item, action):
    current = human.detail(domain, item["id"])["request"]
    return human.act(
        Decision(
            domain=domain,
            id=item["id"],
            revision=current["revision"],
            control_revision=current["control_revision"],
            request_id=uuid4(),
            action=action,
        )
    )


def test_delegation_cancels_sibling_work_and_old_questions(database):
    from efren_bot.collection.models import CollectionMessage

    store, first = review(database)
    mid = message(database, datetime.now(UTC))
    with database.begin() as s:
        s.get(CollectionMessage, mid).text = CORE + "8573"
    store.scan()
    store.finish_detection(
        store.claim(), {"requested": True, "reason": "again", "context_urls": []}
    )
    second = next(i for i in store.list()["items"] if i["id"] != first["id"])
    jobs = [store.claim(), store.claim()]
    for item in [first, second]:
        store.act(
            Action(id=item["id"], request_id=uuid4(), revision=1, action="ask", text="Old question")
        )
    chat = store.claim()
    human = HumanService(database)
    decide(human, "review", first, "delegate")
    assert store.detail(second["id"])["item"]["status"] == "paused"
    for job in jobs + [chat]:
        with pytest.raises(CollectionError):
            store.require_current(job)
    decide(human, "review", first, "continue")
    assert store.claim()["kind"] == "capture"
    assert store.claim() is None
    for item in [first, second]:
        assert all(
            e["status"] == "cancelled"
            for e in store.detail(item["id"])["entries"]
            if e["kind"] == "ask"
        )


def test_recovered_job_cannot_make_more_reads_or_finish_detection(database):
    store, item = review(database)
    job = store.claim()
    store.recover()
    with pytest.raises(CollectionError):
        store.require_current(job)


def test_action_availability_tracks_pause_and_existing_send_without_changing_content(
    database, completed
):
    store, item = completed
    human = HumanService(database)
    original = human.detail("review", item["id"])["request"]["actions"][0]
    store.command("pause")
    paused = human.detail("review", item["id"])["request"]["actions"][0]
    assert not paused["enabled"]
    assert paused["fingerprint"] == original["fingerprint"]
    store.command("resume")
    human.act(
        Decision(
            domain="review",
            id=item["id"],
            revision=1,
            control_revision=0,
            request_id=uuid4(),
            action="approve",
            proposal_id=original["id"],
            fingerprint=original["fingerprint"],
        )
    )
    queued = human.detail("review", item["id"])["request"]["actions"][0]
    assert not queued["enabled"]
    assert queued["fingerprint"] == original["fingerprint"]


def test_demo_never_allows_approval(database, completed):
    from efren_bot.review.models import ReviewRequest

    store, item = completed
    with database.begin() as s:
        s.get(ReviewRequest, item["request_id"]).demo = True
    human = HumanService(database)
    action = human.detail("review", item["id"])["request"]["actions"][0]
    assert not action["enabled"]
    with pytest.raises(CollectionError):
        human.act(
            Decision(
                domain="review",
                id=item["id"],
                revision=1,
                control_revision=0,
                request_id=uuid4(),
                action="approve",
                proposal_id=action["id"],
                fingerprint=action["fingerprint"],
            )
        )
    assert store.claim() is None


def test_concurrent_decisions_have_one_winner(database):
    from concurrent.futures import ThreadPoolExecutor

    store, item = review(database)
    human = HumanService(database)

    def apply(action):
        try:
            human.act(
                Decision(
                    domain="review",
                    id=item["id"],
                    revision=1,
                    control_revision=0,
                    request_id=uuid4(),
                    action=action,
                )
            )
            return "saved"
        except CollectionError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(apply, ["delegate", "stop"])) == ["human_decision_stale", "saved"]
    assert len(human.detail("review", item["id"])["history"]) == 1


@pytest.mark.parametrize("action", ["ignore", "delegate", "stop"])
def test_support_questions_do_not_revive_after_continue(database, action):
    from efren_bot.support.contracts import CaseAction

    store = SupportService(database)
    store.command("activate")
    mid = message(database, datetime.now(UTC), mid="support", root="support")
    store.scan()
    store.finish(
        store.claim(),
        {"action": "support", "title": "Synthetic", "reason": "New", "evidence_ids": [str(mid)]},
    )
    case = store.list()["cases"][0]
    for _ in range(2):
        store.act(CaseAction(id=case["id"], request_id=uuid4(), action="ask", text="Old"))
    job = store.claim()
    human = HumanService(database)
    decide(human, "support", case, action)
    decide(human, "support", case, "continue")
    with pytest.raises(CollectionError):
        store.require_current(job)
    store.finish(job, {"text": "Must not revive", "evidence_ids": []})
    entries = store.detail(case["id"])["entries"]
    assert all(e["status"] == "cancelled" for e in entries if e["kind"] == "ask")
    assert not any(e["kind"] == "answer" for e in entries)
    assert store.claim()["kind"] == "analyze"
    assert store.claim() is None


def test_related_reads_also_respect_delegation(database):
    from efren_bot.review.models import ReviewItem

    store, item = review(database)
    with database.begin() as s:
        related = ReviewItem(
            request_id=item["request_id"],
            project_path=item["project_path"],
            mr_iid="8594",
            url=CORE + "8594",
            title="Related",
            status="queued",
            phase="capture",
            revision=1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        s.add(related)
        s.flush()
        related_id = related.id
    job = store.claim()
    human = HumanService(database)
    decide(human, "review", {"id": related_id}, "delegate")
    store.require_current(job)
    with pytest.raises(CollectionError):
        store.require_read(job, item["project_path"], "8594")


def test_late_classification_does_not_replace_human_context_after_continue(database):
    store = SupportService(database)
    store.command("activate")
    mid = message(database, datetime.now(UTC), mid="root", root="root")
    store.scan()
    result = {
        "action": "support",
        "title": "Synthetic",
        "reason": "New",
        "evidence_ids": [str(mid)],
    }
    store.finish(store.claim(), result)
    case = store.list()["cases"][0]
    store.finish(
        store.claim(),
        {
            "reported": ["Original"],
            "hypotheses": [],
            "missing": [],
            "slack_draft": "Draft",
            "evidence_ids": [str(mid)],
        },
    )
    message(database, datetime.now(UTC), root="root")
    store.scan()
    job = store.claim()
    assert job["kind"] == "classify"
    human = HumanService(database)
    decide(human, "support", case, "delegate")
    decide(human, "support", case, "continue")
    with pytest.raises(CollectionError):
        store.require_current(job)
    before = store.detail(case["id"])["case"]
    store.finish(job, {**result, "title": "Late classification"})
    assert store.detail(case["id"])["case"] == before


def test_previous_phase_cannot_overwrite_next_phase_work(database):
    store, item = review(database)
    capture = store.claim()
    store.finish_item(capture, {"title": "Captured"})
    plan = store.claim()
    store.finish_item(capture, {"title": "Old capture"})
    assert store.detail(item["id"])["item"]["title"] == "Captured"
    store.require_current(plan)


def test_support_http_decisions_are_atomic_versioned_and_preserve_report(database, pg_engine):
    from fastapi.testclient import TestClient

    from efren_bot.api import create_app

    store = SupportService(database)
    store.command("activate")
    mid = message(database, datetime.now(UTC), mid="root", root="root")
    store.scan()
    store.finish(
        store.claim(),
        {
            "action": "support",
            "title": "Synthetic support",
            "reason": "New",
            "evidence_ids": [str(mid)],
        },
    )
    case = store.list()["cases"][0]
    store.finish(
        store.claim(),
        {
            "reported": ["Original"],
            "hypotheses": [],
            "missing": [],
            "slack_draft": "Draft",
            "evidence_ids": [str(mid)],
        },
    )
    original = store.detail(case["id"])["case"]["report"]
    headers = {"Host": "127.0.0.1:8000", "Origin": "http://127.0.0.1:5173", "X-Efren-Local": "1"}
    with TestClient(create_app(engine=pg_engine)) as client:
        headers["X-Collection-Token"] = client.get(
            "/api/collection/session", headers=headers
        ).json()["token"]

        def post(path, body):
            return client.post("/api/collection/" + path, headers=headers, json=body)

        target = {"domain": "support", "id": str(case["id"])}
        detail = post("human/detail", target).json()
        action = detail["request"]["actions"][0]
        approve = {
            **target,
            "revision": 1,
            "control_revision": 0,
            "request_id": str(uuid4()),
            "action": "approve",
            "proposal_id": action["id"],
            "fingerprint": action["fingerprint"],
        }
        assert post("human/act", approve).json()["error"] == "human_capability_blocked"
        command = {
            **target,
            "revision": 1,
            "control_revision": 0,
            "request_id": str(uuid4()),
            "action": "delegate",
        }
        assert post("human/act", command).status_code == 200
        assert post("human/act", command).status_code == 200
        assert post("human/act", {**command, "request_id": str(uuid4())}).status_code == 409
        legacy = {"id": target["id"], "request_id": str(uuid4()), "action": "resume"}
        assert post("support/act", legacy).json()["error"] == "human_control_required"
        detail = post("human/detail", target).json()
        assert detail["request"]["disposition"] == "delegated"
        assert len(detail["history"]) == 1
        assert detail["report"] == original
        assert (
            post(
                "human/act",
                {
                    **target,
                    "revision": 2,
                    "control_revision": 1,
                    "request_id": str(uuid4()),
                    "action": "redirect",
                    "text": "Revisar solo contexto",
                },
            ).status_code
            == 200
        )
        assert post("human/detail", target).json()["report"] == original
        assert store.claim()["payload"]["directions"] == ["Revisar solo contexto"]
