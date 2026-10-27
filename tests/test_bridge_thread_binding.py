"""Native interface compatibility using synthetic data only; no Claude/Slack calls."""

import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from bridge_helpers import THREAD_URL, URL, profile_data, thread_profile_data, write_profile

from efren_bot.bridge.capability import child_environment
from efren_bot.bridge.contracts import canonical, strict_json
from efren_bot.bridge.policy import RunPolicy, budget_state, decide, write_exclusive
from efren_bot.bridge.profile import Profile
from efren_bot.bridge.proof import EvidenceError, verified_identity
from efren_bot.bridge.verify import native_case

EXPECTED = {
    "channel_id": "Copaque9",
    "message_ts": "1234567890.123456",
    "limit": 100,
    "response_format": "concise",
}


def test_v1_serialization_and_fingerprint_are_unchanged():
    data = profile_data()
    profile = Profile.from_json(data)
    assert profile.model_dump(mode="json") == data
    assert profile.fingerprint == "sha256:" + hashlib.sha256(canonical(data)).hexdigest()
    assert profile.arguments(URL) == {"include_replies": True, "permalink": URL}
    assert Profile.from_json(thread_profile_data()).fingerprint != profile.fingerprint


@pytest.mark.parametrize(
    "digits,expected",
    [
        ("1234567890123456", "1234567890.123456"),
        ("12345678901234567", "12345678901.234567"),
        ("0000000000000001", "0000000000.000001"),
        ("9999999999999999", "9999999999.999999"),
        ("1234567890000000", "1234567890.000000"),
    ],
)
def test_lossless_string_mapping(digits, expected):
    profile = Profile.from_json(thread_profile_data())
    url = f"https://example.slack.com/archives/aOpaque09/p{digits}"
    assert profile.arguments(url) == {**EXPECTED, "channel_id": "aOpaque09", "message_ts": expected}
    assert url.endswith("p" + digits)  # URL/source identity is never rewritten.


@pytest.mark.parametrize(
    "url",
    [
        THREAD_URL + "?thread_ts=1234567890.123456",
        THREAD_URL + "#reply",
        THREAD_URL + "/",
        THREAD_URL + " ",
        THREAD_URL.replace("https:", "http:"),
        THREAD_URL.replace("https:", "HTTPS:"),
        THREAD_URL.replace("example.slack.com", "other.slack.com"),
        THREAD_URL.replace("example.slack.com", "Example.slack.com"),
        THREAD_URL.replace("example.slack.com", "example.slack.com:443"),
        THREAD_URL.replace("example.slack.com", "user@example.slack.com"),
        THREAD_URL.replace("Copaque9", "%43opaque9"),
        THREAD_URL.replace("Copaque9", "C_opaque9"),
        THREAD_URL.replace("1234567890123456", "1234567890.123456"),
        THREAD_URL.replace("1234567890123456", "123456789012345"),
        THREAD_URL.replace("1234567890123456", "１２３４５６７８９０１２３４５６"),
        THREAD_URL.replace("1234567890123456", "1e16"),
    ],
)
def test_binding_rejects_url_variants_and_malformed_timestamps(url):
    with pytest.raises(ValueError):
        Profile.from_json(thread_profile_data()).arguments(url)


@pytest.mark.parametrize(
    "key,value",
    [
        ("selector", "url"),
        ("tool_name", "mcp__claude_ai_Slack__slack_read_channel"),
        ("tool_name", "mcp__plugin_Slack__slack_read_thread"),
        ("server_url", "https://unknown.invalid/mcp"),
        ("url_argument", "url"),
        ("channel_argument", "channel"),
        ("fixed_arguments", {"limit": 1000, "response_format": "concise"}),
        ("fixed_arguments", {"limit": True, "response_format": "concise"}),
        ("fixed_arguments", {"limit": 100, "response_format": "detailed"}),
        ("fixed_arguments", {**EXPECTED}),
        ("fixed_arguments", {"limit": 100, "response_format": "concise", "cursor": "next"}),
    ],
)
def test_binding_is_explicit_closed_and_not_an_arbitrary_mapper(key, value):
    data = thread_profile_data()
    data["connector"][key] = value
    with pytest.raises(ValueError):
        Profile.from_json(data)


def test_binding_requires_matching_version_and_closed_exact_admission_schema():
    for schema_version in (1, True, 3):
        data = thread_profile_data()
        data["schema_version"] = schema_version
        with pytest.raises(ValueError):
            Profile.from_json(data)
    for key in ("channel_id", "message_ts", "limit", "response_format"):
        data = thread_profile_data()
        data["connector"]["input_schema"]["properties"].pop(key)
        with pytest.raises(ValueError):
            Profile.from_json(data)


@pytest.fixture
def thread_policy(tmp_path):
    data = thread_profile_data()
    profile = Profile.from_json(data)
    file = write_profile(tmp_path, data)
    work = tmp_path / "run"
    work.mkdir(mode=0o700)
    policy = RunPolicy(
        run_id=uuid4(),
        deadline_at=datetime.now(UTC) + timedelta(seconds=30),
        profile_file=str(file),
        profile=profile,
        profile_fingerprint=profile.fingerprint,
        requested_slack_permalink=THREAD_URL,
    )
    path = work / "policy.json"
    write_exclusive(path, policy.model_dump(mode="json"))
    write_exclusive(work / "budget.json", {"used": False, "violation": False, "tool_use_id": None})
    event = {
        "hook_event_name": "PreToolUse",
        "session_id": str(policy.run_id),
        "tool_name": profile.connector.tool_name,
        "tool_input": EXPECTED.copy(),
        "tool_use_id": "thread-1",
    }
    return path, event


@pytest.mark.parametrize(
    "key,value",
    [
        ("channel_id", "Cother"),
        ("message_ts", "1234567890.123457"),
        ("message_ts", 1234567890),
        ("message_ts", 1234567890.123456),
        ("message_ts", "1234567890123456"),
        ("limit", 1000),
        ("limit", 100.0),
        ("limit", True),
        ("response_format", "detailed"),
        ("cursor", "next"),
        ("latest", "9999999999.999999"),
        ("oldest", "0000000000.000000"),
        ("thread_ts", "1234567890.123456"),
        ("permalink", THREAD_URL),
        ("text", "write something"),
    ],
)
def test_policy_derives_exact_typed_args_from_persisted_url(thread_policy, key, value):
    path, event = thread_policy
    event["tool_input"][key] = value
    assert decide(path, event) == "deny"
    assert budget_state(path.parent / "budget.json")["violation"]


@pytest.mark.parametrize("key", ["channel_id", "message_ts", "limit", "response_format"])
def test_native_optional_fields_are_mandatory_in_local_admission(thread_policy, key):
    path, event = thread_policy
    event["tool_input"].pop(key)
    assert decide(path, event) == "deny"


def test_thread_profile_drift_denies_even_identical_requested_args(thread_policy):
    path, event = thread_policy
    policy = strict_json(path.read_bytes())
    data = thread_profile_data()
    data["profile_version"] = 2
    write_profile(Path(policy["profile_file"]).parent, data)
    assert decide(path, event) == "deny"


@pytest.mark.parametrize(
    "tool",
    [
        "ToolSearch",
        "Agent",
        "Bash",
        "mcp__claude_ai_Slack__slack_search_public",
        "mcp__claude_ai_Slack__slack_read_channel",
        "mcp__claude_ai_Slack__slack_send_message",
    ],
)
def test_policy_still_denies_other_tools(thread_policy, tool):
    path, event = thread_policy
    event["tool_name"] = tool
    assert decide(path, event) == "deny"


def test_omitted_or_renamed_args_and_second_attempt_fail_closed(thread_policy):
    path, event = thread_policy
    event["tool_input"]["channel"] = event["tool_input"].pop("channel_id")
    assert decide(path, event) == "deny"
    event["tool_input"] = EXPECTED.copy()
    assert decide(path, event) == "deny"


def test_exact_thread_read_has_atomic_one_call_budget(thread_policy):
    path, event = thread_policy
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sorted(pool.map(lambda _: decide(path, event), range(4))) == [
            "allow",
            "deny",
            "deny",
            "deny",
        ]


def test_deferred_tools_are_disabled_not_a_new_permission(tmp_path, monkeypatch):
    monkeypatch.setenv("ENABLE_TOOL_SEARCH", "true")
    assert child_environment(tmp_path)["ENABLE_TOOL_SEARCH"] == "false"


def test_old_reviewed_proof_cannot_authorize_new_binding(tmp_path, monkeypatch):
    from test_bridge_proof import observations

    from efren_bot.bridge import proof
    from efren_bot.bridge.init import initialize
    from efren_bot.bridge.proof import seal

    initialize(tmp_path)
    old = Profile.from_json(profile_data())
    new = Profile.from_json(thread_profile_data())
    monkeypatch.setattr(
        "efren_bot.bridge.proof.identity",
        lambda p, _: {
            "profile_fingerprint": p.fingerprint,
            "cli_sha256": p.cli.verified_sha256,
            "control_sha256": proof.control_digest(),
        },
    )
    from efren_bot.bridge.proof import identity

    seal(old, tmp_path, observations(), identity(old, tmp_path))
    with pytest.raises(EvidenceError, match="policy_evidence_drift"):
        verified_identity(new, tmp_path)
    monkeypatch.setattr("efren_bot.bridge.proof.control_digest", lambda: "changed-control")
    with pytest.raises(EvidenceError, match="policy_evidence_drift"):
        verified_identity(old, tmp_path)


@pytest.mark.parametrize("case", ["allowed", "wrong_scope", "failures"])
def test_native_assay_v2_uses_only_existing_inert_fixture(tmp_path, monkeypatch, case):
    def inspect(argv, work, prompt, version):
        data = strict_json((work / "profile.json").read_bytes())
        assert data["schema_version"] == 1
        assert data["connector"]["tool_name"] == "mcp__bridgeprobe__read"
        assert "--strict-mcp-config" in argv and "Slack" not in prompt
        assert not (work / "policy-proof.json").exists()
        raise EvidenceError("synthetic_stop")

    monkeypatch.setattr("efren_bot.bridge.verify.native_output", inspect)
    with pytest.raises(EvidenceError, match="synthetic_stop"):
        native_case(Profile.from_json(thread_profile_data()), tmp_path, case)
    assert list(tmp_path.iterdir()) == []
