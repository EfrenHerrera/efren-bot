"""Factory units that need no database: triage, adapters, effects, executor, contracts."""

import json
import subprocess
from datetime import UTC, datetime

import pytest
from factory_helpers import POLICY, PROFILES, item, projects, record
from pydantic import ValidationError

from efren_bot.factory import effects as fx
from efren_bot.factory.contracts import JobPolicy, JobRepo, JobSource, JobSpec
from efren_bot.factory.executor import ExecutorError, ScraftOpsExecutor
from efren_bot.factory.intake import (
    FixtureAdapter,
    MockNotionClient,
    NotionAdapter,
    NotionHttpClient,
    SlackCollectionAdapter,
    WhatsAppAdapter,
)
from efren_bot.factory.profiles import ProfileRegistry
from efren_bot.factory.triage import PriorVersion, triage

REG = projects()


def run_triage(it, prior=None):
    return triage(it, policy=POLICY, projects=REG, profiles=PROFILES, prior=prior)


# ------------------------------------------------------------------ triage


def test_ready_notion_task_with_project_hint_is_admitted():
    result = run_triage(item(project_hint="Landing Web"))
    assert result.decision == "admit"
    assert (result.project, result.profile, result.role) == ("landing", "frontend", "development")
    assert any("explicit hint" in r for r in result.reasons)


def test_notion_task_that_is_not_ready_is_discarded_with_its_status():
    result = run_triage(item(ready=False, status="Backlog", project_hint="Landing Web"))
    assert result.decision == "discard" and "Backlog" in result.reasons[0]


def test_slack_message_nobody_flagged_is_never_work():
    result = run_triage(item("slack", "@efren puedes ver lo de la landing?", human_flagged=False))
    assert result.decision == "discard"


def test_flagged_slack_message_routes_by_channel():
    result = run_triage(item("slack", "revisa esto por favor", channel="web-team"))
    assert result.decision == "admit" and result.project == "landing"


def test_whatsapp_thanks_is_information_and_a_request_is_work():
    thanks = item("whatsapp", "gracias!", human_flagged=False)
    assert run_triage(thanks).decision == "discard"
    ask = item("whatsapp", "por favor cambia el botón de la landing a verde", human_flagged=False)
    assert run_triage(ask).decision == "admit"


def test_whatsapp_without_a_work_marker_is_discarded_not_guessed():
    result = run_triage(item("whatsapp", "la landing se ve rara hoy", human_flagged=False))
    assert result.decision == "discard"


def test_short_marker_words_match_whole_words_only():
    # "ok" inside "book" or "okay-ish" must not make a real request informational.
    result = run_triage(
        item("whatsapp", "necesito que agregues un book de la landing", human_flagged=False)
    )
    assert result.decision == "admit"


def test_ambiguous_project_asks_for_context_instead_of_guessing():
    result = run_triage(item(text="Cambiar la landing y el orquestador para el nuevo evento"))
    assert result.decision == "ask_context"
    assert "ambiguous project" in " ".join(result.reasons)


def test_unknown_project_asks_for_context():
    result = run_triage(item(text="Implementar el reporte mensual de ventas"))
    assert result.decision == "ask_context" and result.project is None


def test_unknown_project_hint_is_not_silently_replaced_by_keywords():
    result = run_triage(item(project_hint="Nope", text="Cambiar el botón de la landing"))
    assert result.decision == "ask_context" and "matches no registered project" in " ".join(
        result.reasons
    )


def test_sensitive_wording_goes_to_the_human_admission_gate():
    result = run_triage(item(text="Cambiar permisos IAM en producción de la landing"))
    assert result.decision == "inbox"
    assert "sensitive wording" in " ".join(result.reasons)


def test_a_changed_version_of_an_admitted_item_needs_a_person():
    result = run_triage(item(project_hint="Landing Web"), prior=PriorVersion(admitted=True))
    assert result.decision == "inbox" and "changed after" in " ".join(result.reasons)


def test_role_is_picked_from_declared_markers():
    review = run_triage(item(text="revisa MR 8573 de la landing", project_hint="Landing Web"))
    research = run_triage(
        item(text="investiga por qué falla la landing", project_hint="Landing Web")
    )
    support = run_triage(
        item(text="soporte: la landing da error en checkout", project_hint="Landing Web")
    )
    assert (review.role, research.role, support.role) == ("review", "research", "support")


def test_every_decision_carries_the_policy_version():
    assert run_triage(item(project_hint="Landing Web")).policy_version == POLICY.version


def test_triage_is_deterministic():
    it = item(project_hint="Landing Web")
    assert run_triage(it) == run_triage(it)


# ------------------------------------------------------------------ intake


def test_fingerprint_changes_with_content_not_with_whitespace_noise_in_ids():
    a, b = item(), item(text="Cambiar el botón de la landing a rojo")
    assert a.fingerprint() == item().fingerprint()
    assert a.fingerprint() != b.fingerprint()


def notion_page(page_id, title, status="Ready", project="Landing Web", description=""):
    def text(value):
        return {"title": [{"plain_text": value}]}

    return {
        "id": page_id,
        "url": f"https://notion.so/{page_id}",
        "last_edited_time": "2026-10-27T12:00:00.000Z",
        "properties": {
            "Name": text(title),
            "Description": {"rich_text": [{"plain_text": description}]},
            "Status": {"status": {"name": status}},
            "Project": {"select": {"name": project}},
            "Key": {"rich_text": [{"plain_text": "KNF-123"}]},
        },
    }


def test_notion_adapter_normalizes_pages_and_marks_readiness():
    client = MockNotionClient(
        [
            notion_page("p1", "Botón verde", description="en la landing"),
            notion_page("p2", "Idea", "Backlog"),
        ]
    )
    items = NotionAdapter(client).fetch(None)
    assert [i.external_id for i in items] == ["p1", "p2"]
    assert items[0].attrs["ready"] is True and items[1].attrs["ready"] is False
    assert (
        items[0].attrs["business_key"] == "KNF-123"
        and items[0].attrs["project_hint"] == "Landing Web"
    )
    assert "en la landing" in items[0].text


def test_notion_http_client_paginates_and_never_exceeds_its_bound():
    calls = []

    class Response:
        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(self.body).encode()

    def opener(request, timeout):
        calls.append((request.full_url, request.get_header("Authorization")))
        return Response({"results": [{"id": "x"}], "has_more": True, "next_cursor": "c"})

    client = NotionHttpClient("secret-token", "db1", opener=opener)
    assert len(client.query_tasks(None)) == 10  # bounded pagination
    assert all(url.endswith("/databases/db1/query") for url, _ in calls)
    assert calls[0][1] == "Bearer secret-token"


def test_notion_http_client_requires_credentials():
    with pytest.raises(ValueError):
        NotionHttpClient("", "db")


def whatsapp_payload(*messages):
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"wa_id": "5219990000000", "profile": {"name": "Ana"}}],
                            "messages": list(messages),
                        }
                    }
                ]
            }
        ]
    }


def test_whatsapp_adapter_reads_text_and_ignores_media():
    text = {
        "id": "wamid.1",
        "from": "5219990000000",
        "timestamp": "1790000000",
        "type": "text",
        "text": {"body": "por favor cambia la landing"},
    }
    image = {"id": "wamid.2", "from": "5219990000000", "timestamp": "1790000001", "type": "image"}
    items = WhatsAppAdapter().parse(whatsapp_payload(text, image))
    assert [i.external_id for i in items] == ["wamid.1"]
    assert items[0].author == "Ana" and items[0].occurred_at.tzinfo is not None


def test_slack_adapter_marks_only_required_attention_as_flagged():
    rows = [
        {
            "channel_id": "C1",
            "message_id": "1.0",
            "text": "haz esto",
            "occurred_at": datetime(2026, 10, 1, tzinfo=UTC),
            "attention": "required",
            "channel_name": "web-team",
        },
        {
            "channel_id": "C1",
            "message_id": "2.0",
            "text": "   ",
            "occurred_at": datetime(2026, 10, 1, tzinfo=UTC),
            "attention": "required",
        },
    ]
    items = SlackCollectionAdapter(lambda since: rows).fetch(None)
    assert (
        len(items) == 1
        and items[0].external_id == "C1:1.0"
        and items[0].attrs["human_flagged"] is True
    )


def test_fixture_adapter_filters_by_time():
    early = item(external_id="a").model_copy(
        update={"occurred_at": datetime(2026, 1, 1, tzinfo=UTC)}
    )
    late = item(external_id="b")
    adapter = FixtureAdapter([early, late])
    assert [i.external_id for i in adapter.fetch(datetime(2026, 6, 1, tzinfo=UTC))] == ["b"]


# ------------------------------------------------------------------ profiles


def test_bundled_profiles_load_and_forbid_merge_and_deploy():
    assert PROFILES.names() == ["frontend", "lambdas", "orchestrator-multirepo"]
    for name in PROFILES.names():
        profile = PROFILES.get(name)
        assert profile.effects["merge"] == "forbidden" and profile.effects["deploy"] == "forbidden"


def test_profile_directory_overrides_bundled(tmp_path):
    (tmp_path / "frontend.json").write_text(
        json.dumps(
            {
                "schema": "scraft.factory.profile/1",
                "name": "frontend",
                "effects": {"open_pr": "human"},
            }
        )
    )
    assert ProfileRegistry.load(tmp_path).get("frontend").effects["open_pr"] == "human"


def test_profile_with_unknown_schema_is_rejected(tmp_path):
    (tmp_path / "bad.json").write_text(json.dumps({"schema": "other/9", "name": "bad"}))
    with pytest.raises(ValueError):
        ProfileRegistry.load(tmp_path)


# ------------------------------------------------------------------ contracts


def spec(**kw):
    base = dict(
        job_id="fj-1",
        source=JobSource(kind="notion", ref="p1"),
        role="development",
        profile="frontend",
        repo=JobRepo(path="/r", base_ref="main"),
        brief="do it",
        policy=JobPolicy(allow_worktree=True),
    )
    base.update(kw)
    return JobSpec(**base)


def test_job_spec_wire_format_matches_the_go_contract():
    wire = spec().wire()
    assert wire["schema"] == "scraft.factory.job/1" and "mock" not in wire
    assert set(wire) == {
        "schema",
        "job_id",
        "source",
        "role",
        "profile",
        "repo",
        "brief",
        "quotes",
        "policy",
    }


def test_job_spec_rejects_unknown_fields_and_roles():
    with pytest.raises(ValidationError):
        JobSpec.model_validate({**spec().wire(), "surprise": 1})
    with pytest.raises(ValidationError):
        spec(role="admin")


def test_run_record_tolerates_future_fields():
    rec = record(spec())
    data = rec.model_dump(by_alias=True)
    data["brand_new_field"] = {"x": 1}
    assert record  # builder importable
    from efren_bot.factory.contracts import RunRecord

    assert RunRecord.model_validate(data).job_id == "fj-1"


# ------------------------------------------------------------------ executor


class Completed:
    def __init__(self, stdout, returncode=0):
        self.stdout, self.returncode = stdout, returncode


def test_scraft_ops_executor_parses_a_failed_run_as_data():
    rec = record(spec(), status="failed")
    payload = json.dumps(rec.model_dump(mode="json", by_alias=True)).encode()
    seen = {}

    def runner(cmd, **kw):
        seen["cmd"], seen["input"] = cmd, kw["input"]
        return Completed(payload, returncode=1)

    exe = ScraftOpsExecutor(
        "scraft-ops", state_dir="/s", profile_dir="/p", executor="fake", runner=runner
    )
    out = exe.run(spec())
    assert out.status == "failed"
    assert seen["cmd"][:4] == ["scraft-ops", "factory", "run", "--job"] and "fake" in seen["cmd"]
    assert json.loads(seen["input"])["job_id"] == "fj-1"


@pytest.mark.parametrize(
    "stdout",
    [
        b"",
        b"not json",
        b'{"schema":"scraft.factory.run/2","job_id":"fj-1","status":"succeeded"}',
        b'{"schema":"scraft.factory.run/1","job_id":"other","status":"succeeded"}',
    ],
)
def test_scraft_ops_executor_refuses_garbled_or_foreign_records(stdout):
    exe = ScraftOpsExecutor(runner=lambda cmd, **kw: Completed(stdout))
    with pytest.raises(ExecutorError):
        exe.run(spec())


def test_scraft_ops_executor_reports_a_missing_binary():
    def runner(cmd, **kw):
        raise FileNotFoundError

    with pytest.raises(ExecutorError):
        ScraftOpsExecutor(runner=runner).run(spec())

    def slow(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 1)

    with pytest.raises(ExecutorError):
        ScraftOpsExecutor(runner=slow).run(spec())


# ------------------------------------------------------------------ effects


def test_fingerprint_depends_on_kind_and_payload_but_not_key_order():
    assert fx.fingerprint("open_pr", {"a": 1, "b": 2}) == fx.fingerprint(
        "open_pr", {"b": 2, "a": 1}
    )
    assert fx.fingerprint("open_pr", {"a": 1}) != fx.fingerprint("open_pr", {"a": 2})
    assert fx.fingerprint("open_pr", {"a": 1}) != fx.fingerprint("post_slack", {"a": 1})


def test_recording_gateway_is_idempotent_per_key():
    gw = fx.RecordingGateway()
    assert gw.execute("open_pr", {"x": 1}, "k1")["status"] == "recorded"
    assert gw.execute("open_pr", {"x": 1}, "k1")["status"] == "already_executed"
    assert len(gw.executed) == 1


def test_no_proposal_for_a_run_that_did_not_succeed():
    rec = record(spec(), status="failed")
    assert (
        fx.build_effects(
            rec, source_kind="notion", source_ref="p1", brief="x", job_key="k", repo_path="/r"
        )
        == []
    )


def test_proposals_follow_the_source_and_never_include_merge_or_deploy():
    rec = record(spec())

    def kinds(src):
        built = fx.build_effects(
            rec, source_kind=src, source_ref="r", brief="x", job_key="k", repo_path="/r"
        )
        return [k for k, _ in built]

    assert kinds("notion") == ["open_pr", "update_notion"]
    assert kinds("slack") == ["open_pr", "post_slack"]
    assert kinds("whatsapp") == ["open_pr"]
    assert set(fx.PROPOSABLE).isdisjoint({"merge", "deploy"})


def test_glab_gateway_refuses_anything_but_open_pr_and_pushes_before_creating():
    calls = []

    def runner(cmd, **kw):
        calls.append(cmd[0:3])
        return Completed(b"https://gitlab/mr/1", 0)

    gw = fx.GlabGateway(runner=runner)
    with pytest.raises(fx.EffectFailed):
        gw.execute("merge", {}, "k")
    out = gw.execute(
        "open_pr",
        {"branch": "b", "base_ref": "main", "worktree": "/w", "title": "t", "body": "b"},
        "k",
    )
    assert (
        out["status"] == "created"
        and calls[0][:2] == ["git", "-C"]
        and calls[1][:3] == ["glab", "mr", "create"]
    )


def test_glab_gateway_push_failure_is_a_definite_failure_and_create_failure_is_uncertain():
    gw = fx.GlabGateway(runner=lambda cmd, **kw: Completed(b"", 1))
    payload = {"branch": "b", "base_ref": "m", "worktree": "/w", "title": "t", "body": "b"}
    with pytest.raises(fx.EffectFailed):
        gw.execute("open_pr", payload, "k")
    seq = iter([Completed(b"", 0), Completed(b"", 1)])
    gw2 = fx.GlabGateway(runner=lambda cmd, **kw: next(seq))
    with pytest.raises(fx.EffectUncertain):
        gw2.execute("open_pr", payload, "k")


def test_composite_gateway_refuses_unrouted_kinds():
    gw = fx.CompositeGateway({"open_pr": fx.RecordingGateway()})
    with pytest.raises(fx.EffectFailed):
        gw.execute("post_slack", {}, "k")


def test_notion_gateway_reports_network_trouble_as_uncertain():
    class Boom:
        def update_status(self, *a):
            raise OSError("down")

    with pytest.raises(fx.EffectUncertain):
        fx.NotionGateway(Boom()).execute("update_notion", {"page_id": "p", "status": "x"}, "k")


# ------------------------------------------------------------------ wiring


def test_notion_is_wired_only_when_the_host_supplies_token_and_database():
    from efren_bot.config import Settings
    from efren_bot.factory.wiring import build_notion_client, pull_adapters

    assert build_notion_client(Settings()) is None
    assert build_notion_client(Settings(factory_notion_token="t")) is None
    client = build_notion_client(
        Settings(factory_notion_token="t", factory_notion_database_id="db")
    )
    assert isinstance(client, NotionHttpClient)
    assert set(pull_adapters(None)) == {"slack"}
    assert set(pull_adapters(None, notion_client=client)) == {"slack", "notion"}


def test_the_default_gateway_never_touches_the_outside_world():
    from efren_bot.config import Settings
    from efren_bot.factory.wiring import build_gateway

    assert isinstance(build_gateway(Settings()), fx.RecordingGateway)
    real = build_gateway(Settings(factory_gateway="real"))
    with pytest.raises(fx.EffectFailed):
        real.execute("post_slack", {}, "k")  # no gateway for it, even when "real"


def test_pull_once_reports_unknown_sources_instead_of_skipping_silently():
    from efren_bot.factory.worker import pull_once

    class Idle:
        sessions = None

        def ingest(self, items):
            return []

    assert pull_once(Idle(), {}, ["notion"]) == {"notion": -1}
