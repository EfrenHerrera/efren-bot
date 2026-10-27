"""Synthetic evidence tests only. Nothing here approves the installed native client."""

import hmac
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from bridge_helpers import synthetic_profile, write_profile

from efren_bot.bridge.capability import assess, child_environment
from efren_bot.bridge.contracts import canonical, strict_json
from efren_bot.bridge.init import initialize
from efren_bot.bridge.policy import write_exclusive
from efren_bot.bridge.proof import (
    PROOF,
    REVIEW,
    EvidenceError,
    identity,
    policy_absence,
    review_state,
    seal,
    validate_observations,
    verified_identity,
)
from efren_bot.bridge.verify import native_case, native_output, verify


def observations():
    return {
        case: {
            "attempts": count,
            "executed": 5 if case == "allowed" else 0,
            "hook_events": count,
            "native_init": True,
        }
        for case, count in (("allowed", 5), ("wrong_scope", 2), ("failures", 5))
    }


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    initialize(tmp_path)
    write_profile(tmp_path)
    profile = synthetic_profile()
    state = {
        "profile_fingerprint": profile.fingerprint,
        "cli_sha256": "b" * 64,
        "control_sha256": "c" * 64,
    }
    monkeypatch.setattr("efren_bot.bridge.proof.identity", lambda *a: state.copy())
    return profile, tmp_path, state


def test_missing_proof_never_probes_cli(evidence, monkeypatch):
    profile, directory, _ = evidence
    monkeypatch.setattr(
        "efren_bot.bridge.capability.probe_binary",
        lambda *a: pytest.fail("no native invocation without proof"),
    )
    capability = assess(profile, directory / "runs")
    assert not capability.policy_verified and capability.reason == "policy_proof_missing"


def test_reviewed_receipt_code_path_is_not_permanently_false(evidence, monkeypatch):
    profile, directory, state = evidence
    seal(profile, directory, observations(), state)
    monkeypatch.setattr(
        "efren_bot.bridge.capability.probe_binary", lambda *a: ("2.1.309", "b" * 64)
    )
    capability = assess(profile, directory / "runs")
    assert capability.policy_verified is True and capability.reason is None
    # This synthetic signature/test seam is NOT emitted by the operator CLI and
    # is never copied to .local/bridge. Only exercises validator/runner logic.
    assert verified_identity(profile, directory) == state


def rewrite(directory, mutate, *, sign=True):
    data = strict_json((directory / PROOF).read_bytes())
    mutate(data["payload"])
    if sign:
        from efren_bot.bridge.profile import load_token

        key = load_token(directory / "token", host=True).encode()
        data["mac"] = hmac.new(key, canonical(data["payload"]), "sha256").hexdigest()
    (directory / PROOF).write_bytes(canonical(data))


@pytest.mark.parametrize(
    "change,reason",
    [
        ("forged", "policy_proof_invalid"),
        ("stale", "policy_proof_stale"),
        ("future", "policy_proof_stale"),
        ("drift", "policy_evidence_drift"),
        ("observations", "native_probe_incomplete"),
    ],
)
def test_fail_closed_proofs(evidence, change, reason):
    profile, directory, state = evidence
    seal(profile, directory, observations(), state)
    if change == "drift":
        state["control_sha256"] = "d" * 64
    elif change == "forged":
        rewrite(directory, lambda p: p.update(identity={}), sign=False)
    elif change == "observations":
        rewrite(directory, lambda p: p["observations"]["failures"].update(attempts=4))
    else:
        date = datetime.now(UTC) + timedelta(days=2 if change == "future" else -2)
        rewrite(
            directory,
            lambda p: p.update(
                created_at=date.isoformat(), expires_at=(date + timedelta(hours=24)).isoformat()
            ),
        )
    with pytest.raises(EvidenceError, match=reason):
        verified_identity(profile, directory)


def test_unsigned_boolean_or_external_report_is_not_a_proof(evidence):
    profile, directory, _ = evidence
    write_exclusive(directory / PROOF, {"policy_verified": True, "native": True})
    with pytest.raises(EvidenceError, match="policy_proof_invalid"):
        verified_identity(profile, directory)


@pytest.mark.parametrize(
    "case,key,value",
    [
        ("allowed", "executed", 0),
        ("failures", "executed", 1),
        ("wrong_scope", "attempts", 0),
        ("allowed", "native_init", 1),
        ("failures", "hook_events", 0),
    ],
)
def test_native_partial_negative_or_unknown_results_never_seal(case, key, value):
    data = observations()
    data[case][key] = value
    with pytest.raises(EvidenceError, match="native_probe_incomplete"):
        validate_observations(data)


def test_proof_secure_files_and_exclusive_write(evidence):
    profile, directory, state = evidence
    seal(profile, directory, observations(), state)
    with pytest.raises(FileExistsError):
        seal(profile, directory, observations(), state)
    (directory / PROOF).chmod(0o644)
    with pytest.raises(EvidenceError, match="policy_proof_invalid"):
        verified_identity(profile, directory)


def test_review_requires_actual_personal_unmanaged_scope(tmp_path, monkeypatch):
    write_profile(tmp_path)
    profile = synthetic_profile()
    monkeypatch.setattr("efren_bot.bridge.proof.policy_absence", lambda: "absent-paths-digest")
    with pytest.raises(EvidenceError, match="policy_review_missing"):
        review_state(profile, tmp_path)
    data = {
        "schema_version": 1,
        "profile_fingerprint": profile.fingerprint,
        "operator": "Local operator",
        "basis": "Reviewed effective unmanaged configuration",
        "account_scope": "personal_subscription",
        "effective_managed_settings": {},
    }
    write_exclusive(tmp_path / REVIEW, data)
    assert review_state(profile, tmp_path)["policy_paths_sha256"] == "absent-paths-digest"
    for field, value in (
        ("account_scope", "team"),
        ("effective_managed_settings", {"env": {}}),
        ("profile_fingerprint", "sha256:" + "0" * 64),
        ("schema_version", True),
    ):
        (tmp_path / REVIEW).write_bytes(canonical({**data, field: value}))
        with pytest.raises(EvidenceError, match="policy_review_invalid"):
            review_state(profile, tmp_path)


def test_official_signature_is_required_not_a_cli_version(tmp_path, monkeypatch):
    monkeypatch.setattr("efren_bot.bridge.proof.sys.platform", "darwin")
    calls = []

    def reject(argv, **kwargs):
        calls.append(argv)
        assert argv[:4] == ["/usr/bin/codesign", "--verify", "--strict", "-R"]
        assert argv[4].startswith("=anchor apple generic")
        assert kwargs["env"] == {"PATH": "/usr/bin:/bin"}
        return subprocess.CompletedProcess(argv, 1)

    monkeypatch.setattr("efren_bot.bridge.proof.subprocess.run", reject)
    path = tmp_path / "fake-claude"
    path.write_text("not signed")
    data = synthetic_profile().model_dump(mode="json")
    data["cli"]["path"] = str(path)
    from efren_bot.bridge.profile import Profile

    with pytest.raises(EvidenceError, match="official_signature_unverified"):
        identity(Profile.from_json(data), tmp_path)
    assert len(calls) == 1


def test_operator_command_missing_profile_no_cli_no_secret(tmp_path, monkeypatch, capsys):
    initialize(tmp_path)
    monkeypatch.setattr(
        "efren_bot.bridge.verify.subprocess.Popen", lambda *a: pytest.fail("no CLI")
    )
    with pytest.raises(ValueError, match="profile_missing"):
        verify(tmp_path)
    assert capsys.readouterr().out == "" and not (tmp_path / PROOF).exists()


def test_native_failure_stream_is_discarded_and_env_clean(tmp_path, monkeypatch, capsys):
    original = subprocess.Popen
    processes = []
    for key in (
        "ANTHROPIC_API_KEY",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "CLAUDE_CODE_SIMPLE",
        "ANTHROPIC_BASE_URL",
        "HTTPS_PROXY",
        "CLAUDE_BRIDGE_TOKEN_FILE",
    ):
        monkeypatch.setenv(key, "SENSITIVE-DO-NOT-LEAK")

    def launch(argv, **kwargs):
        assert kwargs["env"] == child_environment(tmp_path)
        code = "import time;time.sleep(.05);print('SENSITIVE-DO-NOT-LEAK');"
        process = original([sys.executable, "-c", code], **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr("efren_bot.bridge.verify.subprocess.Popen", launch)
    with pytest.raises(ValueError):
        native_output(["/not-a-real-cli"], tmp_path, "inert test", "2.1.309")
    assert all(p.poll() is not None for p in processes)
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("case", ["allowed", "wrong_scope", "failures"])
def test_native_harness_cannot_approve_unattempted_tools(tmp_path, monkeypatch, case):
    tmp_path.chmod(0o700)
    monkeypatch.setattr(
        "efren_bot.bridge.verify.native_output",
        lambda *a: {
            "hook_events": 100,
            "native_init": True,
        },
    )
    with pytest.raises(EvidenceError, match="native_probe_incomplete"):
        native_case(synthetic_profile(), tmp_path, case)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "suffix",
    [
        "managed-settings.json",
        "managed-settings.d",
        "managed-mcp.json",
        "com.anthropic.claudecode.plist",
        "remote-settings.json",
    ],
)
@pytest.mark.parametrize("state", ["present", "unreadable"])
def test_any_managed_source_blocks_without_reading_contents(monkeypatch, suffix, state):
    class PolicyPath:
        def __init__(self, value):
            self.value = value

        def __truediv__(self, value):
            return PolicyPath(self.value + "/" + value)

        @property
        def parents(self):
            return []

        def lstat(self):
            if self.value.endswith("/" + suffix):
                if state == "unreadable":
                    raise PermissionError()
                return object()
            raise FileNotFoundError()

        def __str__(self):
            return self.value

    monkeypatch.setattr("efren_bot.bridge.proof.Path", PolicyPath)
    monkeypatch.setattr("efren_bot.bridge.proof.sys.platform", "darwin")
    monkeypatch.setattr(
        "efren_bot.bridge.proof.pwd.getpwuid",
        lambda *a: SimpleNamespace(
            pw_dir="/synthetic-home",
            pw_name="operator",
        ),
    )
    with pytest.raises(EvidenceError, match="managed_policy_unreviewed"):
        policy_absence()


@pytest.mark.parametrize(
    "field,value",
    [
        ("apiKeySource", "api_key"),
        ("plugins", [{"name": "unreviewed"}]),
        ("claude_code_version", "2.1.1"),
        ("tools", ["Bash"]),
        ("permissionMode", "bypassPermissions"),
        ("mcp_servers", []),
    ],
)
def test_native_unknown_configuration_fails_closed(tmp_path, monkeypatch, field, value):
    original = subprocess.Popen
    init = {
        "type": "system",
        "subtype": "init",
        "apiKeySource": "none",
        "plugins": [],
        "claude_code_version": "2.1.309",
        "permissionMode": "dontAsk",
        "tools": [],
        "mcp_servers": [{"name": "bridgeprobe", "status": "connected"}],
    }
    init[field] = value
    raw = canonical(init).decode()

    def launch(argv, **kwargs):
        return original(
            [sys.executable, "-c", f"import time;time.sleep(.05);print({raw!r})"], **kwargs
        )

    monkeypatch.setattr("efren_bot.bridge.verify.subprocess.Popen", launch)
    with pytest.raises(EvidenceError, match="native_configuration_unreviewed"):
        native_output(["/synthetic-client"], tmp_path, "inert test", "2.1.309")
