from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from test_support import message

from efren_bot.collection.service import CollectionError
from efren_bot.review.contracts import Action
from efren_bot.review.gitlab import Gitlab, links, parse_url
from efren_bot.review.service import ReviewService

CORE = "https://gitlab.com/konfio/organization/guilds/core/core/-/merge_requests/"
WEB = "https://gitlab.com/konfio/organization/scope/p01/contexts/c01/domains/web/konfio-app-web/-/merge_requests/"


def test_urls_all_targets_dedupe_and_no_untrusted_destinations():
    urls = links(f"Please review <{CORE}8573|MR> and {CORE}8594 and {CORE}8573.")
    assert len(urls) == 2
    assert parse_url(urls[0])[0] == "konfio/organization/guilds/core/core"
    for bad in [
        CORE.replace("gitlab.com", "gitlab.com.evil") + "1",
        CORE + "1?token=bad",
        "http://gitlab.com/konfio/organization/guilds/core/core/-/merge_requests/1",
    ]:
        with pytest.raises(ValueError):
            parse_url(bad)


@pytest.mark.integration
def test_cut_excludes_history_but_new_reply_can_request_all_mrs(database):
    service = ReviewService(database)
    message(database, datetime.now(UTC) - timedelta(days=1))
    service.command("activate")
    message(database, datetime.now(UTC), historical=True)
    message(database, datetime.now(UTC), root="old-thread")
    assert service.scan() == 1 and service.scan() == 0


@pytest.mark.integration
def test_all_mrs_are_enqueued_and_unknown_project_does_not_drop_others(database):
    service = ReviewService(database)
    service.command("activate")
    identifier = message(database, datetime.now(UTC))
    from efren_bot.collection.models import CollectionMessage

    with database.begin() as s:
        s.get(
            CollectionMessage, identifier
        ).text = f"Review {CORE}8573 {CORE}8594 https://gitlab.com/other/repo/-/merge_requests/9"
    service.scan()
    job = service.claim()
    service.finish_detection(
        job, {"requested": True, "reason": "explicit request", "context_urls": []}
    )
    items = service.list()["items"]
    assert len(items) == 3 and sum(i["status"] == "blocked" for i in items) == 1


def test_gitlab_boundary_never_defaults_to_post_or_accepts_arbitrary_paths(monkeypatch):
    calls = []

    def fake(args, **kwargs):
        calls.append(args)
        from subprocess import CompletedProcess

        return CompletedProcess(args, 0, b"{}", b"")

    monkeypatch.setattr("efren_bot.review.gitlab.subprocess.run", fake)
    client = Gitlab("konfio/organization/guilds/core/core", "8573")
    client.metadata()
    assert "--method" in calls[0] and "GET" in calls[0] and "--hostname" in calls[0]
    for path in [".env", "../secrets", "/etc/passwd", "core/../../.env", "core/token.pem"]:
        with pytest.raises(ValueError):
            client.file(path, "a" * 40)
    assert len(calls) == 1


@pytest.mark.integration
def test_demo_never_publishes_and_pause_invalidates_running_work(database):
    service = ReviewService(database)
    service.command("activate")
    identifier = message(database, datetime.now(UTC))
    from efren_bot.collection.models import CollectionMessage

    with database.begin() as s:
        s.get(CollectionMessage, identifier).text = f"Review {CORE}8573"
    service.scan()
    job = service.claim()
    service.finish_detection(job, {"requested": True, "reason": "request", "context_urls": []})
    item = service.list()["items"][0]
    work = service.claim()
    service.act(Action(id=item["id"], request_id=uuid4(), revision=1, action="pause"))
    service.finish_item(work, {"refs": {"head_sha": "a" * 40}}, next_phase="plan")
    assert service.detail(item["id"])["item"]["status"] == "paused"


@pytest.mark.integration
def test_runner_progresses_all_items_and_isolates_failure(database):
    from test_review_model import report, snapshot

    from efren_bot.collection.models import CollectionMessage
    from efren_bot.review.runner import tick

    service = ReviewService(database)
    service.command("activate")
    identifier = message(database, datetime.now(UTC))
    with database.begin() as s:
        s.get(CollectionMessage, identifier).text = f"Review {CORE}8573 {CORE}8594"
    service.scan()

    class Client:
        def __init__(self, project, iid):
            self.iid = iid

        def capture(self):
            if self.iid == "8573":
                raise RuntimeError("no access")
            return {**snapshot(), "title": "Second MR"}

        def metadata(self):
            return {"diff_refs": snapshot()["refs"]}

    def model(kind, payload):
        if kind == "detect":
            return {"requested": True, "reason": "explicit", "context_urls": []}
        if kind == "plan":
            return {"objective": "Trace changed behavior", "reads": [], "hypotheses": []}
        if kind == "chat":
            return {"text": "Static evidence only", "evidence": []}
        return report()

    for _ in range(8):
        tick(service, model, Client)
    items = service.list()["items"]
    assert {i["status"] for i in items} == {"failed", "ready"}
    ready = next(i for i in items if i["status"] == "ready")
    detail = service.detail(ready["id"])
    p = detail["proposals"][0]
    action = Action(
        id=ready["id"],
        request_id=uuid4(),
        revision=ready["revision"],
        action="edit",
        proposal_id=p["id"],
        proposal_version=p["version"],
        text="Private revised comment",
    )
    assert service.act(action) == service.act(action)
    with pytest.raises(CollectionError):
        service.act(action.model_copy(update={"request_id": uuid4()}))
    service.act(
        Action(
            id=ready["id"],
            request_id=uuid4(),
            revision=ready["revision"],
            action="ask",
            text="Why?",
        )
    )
    assert tick(service, model, Client)
    assert service.detail(ready["id"])["entries"][-1]["kind"] == "answer"


@pytest.mark.integration
def test_review_http_capability_closed_body_and_no_publish(database, pg_engine):
    from fastapi.testclient import TestClient

    from efren_bot.api import create_app

    headers = {"Host": "127.0.0.1:8000", "Origin": "http://127.0.0.1:5173", "X-Efren-Local": "1"}
    with TestClient(create_app(engine=pg_engine)) as client:
        token = client.get("/api/collection/session", headers=headers).json()["token"]
        assert (
            client.post("/api/collection/reviews/list", headers=headers, json={}).status_code == 401
        )
        headers = {**headers, "X-Collection-Token": token}
        assert (
            client.post("/api/collection/reviews/list", headers=headers, json={}).json()["items"]
            == []
        )
        bad = client.post(
            "/api/collection/reviews/act",
            headers=headers,
            json={"text": "private", "unknown": True},
        )
        assert bad.status_code == 422 and "private" not in bad.text
        assert (
            client.post(
                "/api/collection/reviews/demo",
                headers=headers,
                json={"request_id": str(uuid4()), "url": "https://evil.test"},
            ).status_code
            == 422
        )


@pytest.fixture
def ready_review(database):
    from test_review_model import report, snapshot

    from efren_bot.collection.models import CollectionMessage

    service = ReviewService(database)
    service.command("activate")
    identifier = message(database, datetime.now(UTC))
    with database.begin() as s:
        s.get(CollectionMessage, identifier).text = f"Review {CORE}8573"
    service.scan()
    service.finish_detection(
        service.claim(), {"requested": True, "reason": "review", "context_urls": []}
    )
    data = {**snapshot(), "title": "Synthetic ready MR", "mr_state": "opened"}
    service.finish_item(service.claim(), data)
    service.finish_item(service.claim(), {"objective": "Trace", "reads": [], "hypotheses": []})
    service.finish_item(service.claim(), data)
    service.finish_item(service.claim(), report())
    item = service.list()["items"][0]
    return service, item, service.detail(item["id"])["proposals"][0]


@pytest.mark.integration
def test_publication_is_exactly_admitted_and_records_inflight_result(ready_review):
    service, item, p = ready_review
    action = Action(
        id=item["id"],
        request_id=uuid4(),
        revision=1,
        action="publish",
        proposal_id=p["id"],
        proposal_version=p["version"],
    )
    assert service.act(action) == service.act(action)
    with pytest.raises(CollectionError):
        service.act(action.model_copy(update={"request_id": uuid4()}))
    job = service.claim()
    assert job["kind"] == "publish"
    current = {"state": "opened", "diff_refs": job["payload"]["approved"]["refs"]}
    assert service.admit_publish(job, current)
    service.act(Action(id=item["id"], request_id=uuid4(), revision=1, action="pause"))
    service.finish_publish(job, "synthetic-discussion-id")
    detail = service.detail(item["id"])
    assert detail["item"]["status"] == "paused"
    assert detail["proposals"][0]["status"] == "published"


@pytest.mark.integration
def test_demo_publication_and_stale_head_cannot_reach_writer(ready_review, database):
    from efren_bot.review.models import ReviewRequest

    service, item, p = ready_review
    action = Action(
        id=item["id"],
        request_id=uuid4(),
        revision=1,
        action="publish",
        proposal_id=p["id"],
        proposal_version=p["version"],
    )
    with database.begin() as s:
        s.get(ReviewRequest, item["request_id"]).demo = True
    with pytest.raises(CollectionError) as error:
        service.act(action)
    assert error.value.code == "demo_read_only"
    with database.begin() as s:
        s.get(ReviewRequest, item["request_id"]).demo = False
    service.act(action)
    job = service.claim()
    assert not service.admit_publish(job, {"state": "opened", "diff_refs": {}})
    assert service.detail(item["id"])["proposals"][0]["status"] == "private"


@pytest.mark.integration
def test_interruption_after_send_admission_is_uncertain_never_retried(ready_review):
    service, item, p = ready_review
    action = Action(
        id=item["id"],
        request_id=uuid4(),
        revision=1,
        action="publish",
        proposal_id=p["id"],
        proposal_version=p["version"],
    )
    service.act(action)
    job = service.claim()
    assert service.admit_publish(
        job, {"state": "opened", "diff_refs": job["payload"]["approved"]["refs"]}
    )
    service.recover()
    assert service.detail(item["id"])["proposals"][0]["status"] == "uncertain"
    with pytest.raises(CollectionError):
        service.act(action.model_copy(update={"request_id": uuid4()}))


def test_writer_can_only_post_one_approved_inline_comment(monkeypatch):
    import json
    from subprocess import CompletedProcess

    from test_review_model import report, snapshot

    from efren_bot.review.publish import publish_comment

    calls = []

    def fake(args, **kwargs):
        calls.append((args, kwargs))
        return CompletedProcess(args, 0, b'{"id":"synthetic-discussion"}', b"")

    monkeypatch.setattr("efren_bot.review.publish.subprocess.run", fake)
    approved = {
        "refs": snapshot()["refs"],
        "finding": report()["findings"][0],
        "body": "Approved question",
        "old_path": "core/example.py",
    }
    assert (
        publish_comment(
            "konfio/organization/guilds/core/core", "8573", approved, "synthetic-marker"
        )
        == "synthetic-discussion"
    )
    args, kwargs = calls[0]
    assert args[-3:] == ["projects/40652545/merge_requests/8573/discussions", "--input", "-"]
    assert "POST" in args and len(calls) == 1
    payload = json.loads(kwargs["input"])
    assert payload["position"]["head_sha"] == "a" * 40 and "synthetic-marker" in payload["body"]


def test_file_range_is_rejected_before_network(monkeypatch):
    calls = []
    monkeypatch.setattr(Gitlab, "_get", lambda *args: calls.append(args) or b"code")
    client = Gitlab("konfio/organization/guilds/core/core", "8573")
    for start, end in [(0, 20), (30, 20), (1, 502)]:
        with pytest.raises(ValueError):
            client.file("core/example.py", "a" * 40, start=start, end=end)
    assert calls == []


def test_capture_must_match_all_immutable_refs_not_only_head(monkeypatch):
    from efren_bot.review.gitlab import GitlabError

    refs = {"head_sha": "a" * 40, "base_sha": "b" * 40, "start_sha": "c" * 40}
    client = Gitlab("konfio/organization/guilds/core/core", "8573")

    def get(endpoint):
        if endpoint == client.root:
            return {"diff_refs": refs}
        return [
            {
                "id": 1,
                "head_commit_sha": refs["head_sha"],
                "base_commit_sha": "d" * 40,
                "start_commit_sha": refs["start_sha"],
            }
        ]

    monkeypatch.setattr(client, "get", get)
    with pytest.raises(GitlabError, match="gitlab_version_missing"):
        client.capture()


def test_capture_does_not_forward_sensitive_file_diffs_to_model(monkeypatch):
    import json

    from efren_bot.review.gitlab import GitlabError

    client = Gitlab("konfio/organization/guilds/core/core", "8573")
    refs = {"head_sha": "a" * 40, "base_sha": "b" * 40, "start_sha": "c" * 40}
    version = {
        "id": 1,
        **{f"{side}_commit_sha": refs[f"{side}_sha"] for side in ("head", "base", "start")},
    }
    secret = "SENSITIVE_SHOULD_NOT_REACH_MODEL"

    def get(endpoint):
        if endpoint == client.root:
            return {
                "diff_refs": refs,
                "title": "Synthetic",
                "state": "opened",
                "changes_count": "2",
            }
        if "/versions?" in endpoint:
            return [version]
        if endpoint.endswith("/versions/1"):
            return {
                **version,
                "state": "collected",
                "diffs": [
                    {
                        "new_path": path,
                        "old_path": path,
                        "deleted_file": False,
                        "diff": "@@ -0,0 +1 @@\n+" + body,
                    }
                    for path, body in [(".env", secret), ("core/example.py", "normal_code()")]
                ],
            }
        return []

    def missing(*args, **kwargs):
        raise GitlabError("source_missing")

    monkeypatch.setattr(client, "get", get)
    monkeypatch.setattr(client, "file", missing)
    snapshot = client.capture()
    assert secret not in json.dumps(snapshot)
    assert len(snapshot["diffs"]) == 2 and snapshot["limitations"]
    assert snapshot["diffs"][0]["added_lines"] == []


@pytest.mark.integration
def test_global_pause_revokes_queued_publication_even_after_resume(ready_review):
    service, item, p = ready_review
    service.act(
        Action(
            id=item["id"],
            request_id=uuid4(),
            revision=1,
            action="publish",
            proposal_id=p["id"],
            proposal_version=p["version"],
        )
    )
    service.command("pause")
    service.command("resume")
    job = service.claim()
    assert not service.admit_publish(
        job, {"state": "opened", "diff_refs": job["payload"]["approved"]["refs"]}
    )
    assert service.detail(item["id"])["proposals"][0]["status"] == "private"


@pytest.mark.integration
def test_publication_admission_is_single_use(ready_review):
    service, item, p = ready_review
    service.act(
        Action(
            id=item["id"],
            request_id=uuid4(),
            revision=1,
            action="publish",
            proposal_id=p["id"],
            proposal_version=p["version"],
        )
    )
    job = service.claim()
    current = {"state": "opened", "diff_refs": job["payload"]["approved"]["refs"]}
    assert service.admit_publish(job, current)
    assert not service.admit_publish(job, current)
    service.finish_publish(job, "one-remote-result")
    service.finish_publish(job)
    assert service.detail(item["id"])["proposals"][0]["status"] == "published"


@pytest.mark.integration
def test_inherited_request_keeps_every_mr_from_referenced_message(database):
    from efren_bot.collection.models import CollectionMessage

    service = ReviewService(database)
    service.command("activate")
    identifier = message(database, datetime.now(UTC))
    with database.begin() as s:
        s.get(CollectionMessage, identifier).text = "Can you re-review these?"
    service.scan()
    job = service.claim()
    from efren_bot.review.models import ReviewRequest

    with database.begin() as s:
        req = s.get(ReviewRequest, job["id"])
        req.context = {
            **req.context,
            "messages": [
                *req.context["messages"],
                {"id": str(uuid4()), "text": f"Review {CORE}8573 and {CORE}8594"},
            ],
        }
    service.finish_detection(
        job, {"requested": True, "reason": "New re-review request", "context_urls": [CORE + "8573"]}
    )
    assert {item["mr_iid"] for item in service.list()["items"]} == {"8573", "8594"}


@pytest.mark.integration
def test_snapshot_limitations_and_model_gaps_do_not_become_ready(ready_review):
    from test_review_model import report, snapshot

    service, item, _ = ready_review
    service.act(Action(id=item["id"], request_id=uuid4(), revision=1, action="resume"))
    service.finish_item(service.claim(), snapshot())
    service.finish_item(service.claim(), {"objective": "Trace", "reads": [], "hypotheses": []})
    service.finish_item(service.claim(), snapshot())
    limited = report()
    limited["checks"][0]["status"] = "limited"
    service.finish_item(service.claim(), limited)
    assert service.detail(item["id"])["item"]["status"] == "partial"


@pytest.mark.integration
def test_demo_is_one_exact_stored_identity_and_never_enables_history(database):
    from efren_bot.collection.models import CollectionMessage
    from efren_bot.review.contracts import DemoInput
    from efren_bot.review.service import DEMO_SCOPE

    service = ReviewService(database)
    service.command("activate")
    identifier = message(
        database,
        datetime.now(UTC) - timedelta(days=1),
        historical=True,
        mid="1792770316.988339",
        root="1792770316.988339",
    )
    with database.begin() as s:
        row = s.get(CollectionMessage, identifier)
        row.channel_id = "C07SRBE0V1T"
        row.text = f"Review {CORE}8573 {CORE}8594 {CORE}8616"
    with pytest.raises(CollectionError) as error:
        service.demo(DemoInput(request_id=uuid4()))
    assert error.value.code == "approved_demo_source_missing"
    with database.begin() as s:
        s.get(CollectionMessage, identifier).source_scope = DEMO_SCOPE
    demo = service.demo(DemoInput(request_id=uuid4()))
    assert service.demo(DemoInput(request_id=uuid4())) == demo
    assert {item["mr_iid"] for item in service.list()["items"]} == {"8573", "8594", "8616"}
    assert all(item["demo"] for item in service.list()["items"])
    assert service.scan() == 0
