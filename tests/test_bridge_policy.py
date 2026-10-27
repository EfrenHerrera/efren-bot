import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from bridge_helpers import URL, profile_data, synthetic_profile, write_profile

from efren_bot.bridge.contracts import canonical, strict_json
from efren_bot.bridge.policy import RunPolicy, budget_state, decide, write_exclusive


@pytest.fixture
def policy(tmp_path):
    profile_file = write_profile(tmp_path)
    profile = synthetic_profile()
    run = tmp_path / "run"
    run.mkdir(mode=0o700)
    path = run / "policy.json"
    policy = RunPolicy(
        run_id=uuid4(),
        deadline_at=datetime.now(UTC) + timedelta(seconds=30),
        profile_file=str(profile_file),
        profile=profile,
        profile_fingerprint=profile.fingerprint,
        requested_slack_permalink=URL,
    )
    write_exclusive(path, policy.model_dump(mode="json"))
    write_exclusive(run / "budget.json", {"used": False, "violation": False, "tool_use_id": None})
    event = {
        "hook_event_name": "PreToolUse",
        "session_id": str(policy.run_id),
        "tool_name": profile.connector.tool_name,
        "tool_input": profile.arguments(URL),
        "tool_use_id": "tool-1",
    }
    return path, event, profile_file


def test_one_attempt_and_atomic_race(policy):
    path, event, _ = policy
    with ThreadPoolExecutor(max_workers=8) as pool:
        decisions = list(pool.map(lambda _: decide(path, event), range(8)))
    assert decisions.count("allow") == 1 and decisions.count("deny") == 7
    assert budget_state(path.parent / "budget.json") == {
        "used": True,
        "violation": True,
        "tool_use_id": "tool-1",
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("tool_name", "Bash"),
        ("tool_name", "mcp__test__search"),
        ("tool_name", "Agent"),
        ("tool_input", {"permalink": URL + "0", "include_replies": True}),
        ("tool_input", {"permalink": URL, "include_replies": 1}),
        ("tool_input", {"permalink": URL, "include_replies": True, "cursor": "next"}),
        ("tool_input", {"permalink": URL}),
        ("hook_event_name", "PostToolUse"),
        ("session_id", str(uuid4())),
        ("tool_use_id", ""),
        ("unknown", "input"),
    ],
)
def test_default_deny_marks_violation(policy, field, value):
    path, event, _ = policy
    event[field] = value
    assert decide(path, event) == "deny"
    assert budget_state(path.parent / "budget.json")["violation"]


def test_profile_drift_and_deadline(policy):
    path, event, profile_file = policy
    data = profile_data()
    data["profile_version"] = 2
    write_profile(profile_file.parent, data)
    assert decide(path, event) == "deny"


@pytest.mark.parametrize("raw", [b"{}", b'{"x":NaN}', b'{"x":1,"x":2}', b"x" * 65537])
def test_hook_process_invalid_input_explicit_deny_and_no_echo(policy, raw):
    path, _, _ = policy
    result = subprocess.run(
        [sys.executable, "-m", "efren_bot.bridge.policy", str(path)],
        input=raw,
        capture_output=True,
        timeout=3,
        check=False,
    )
    assert result.returncode == 2
    assert strict_json(result.stdout) == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
        }
    }
    assert result.stderr == b""
    assert budget_state(path.parent / "budget.json")["violation"]


def test_hook_missing_policy_exits2_no_sensitive_output(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "efren_bot.bridge.policy", str(tmp_path / "missing")],
        input=b'{"secret":"do-not-echo"}',
        capture_output=True,
        timeout=3,
        check=False,
    )
    assert result.returncode == 2
    assert strict_json(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert b"do-not-echo" not in result.stdout and result.stderr == b""


def test_expired_snapshot_deny(policy):
    path, event, _ = policy
    data = strict_json(path.read_bytes())
    data["deadline_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    path.write_bytes(canonical(data))
    assert decide(path, event) == "deny"
