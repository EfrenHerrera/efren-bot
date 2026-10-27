import json
import os
from pathlib import Path

import pytest
from bridge_helpers import TOKEN, URL, profile_data, result_data, write_profile

from efren_bot.bridge.contracts import (
    BridgeResult,
    ClaimInput,
    CompleteInput,
    slack_url,
    strict_json,
)
from efren_bot.bridge.init import initialize
from efren_bot.bridge.profile import (
    Profile,
    ProfileError,
    load_profile,
    load_token,
    validate_schema,
)
from efren_bot.config import Settings


@pytest.mark.parametrize(
    "raw",
    [
        b'{"a":1,"a":2}',
        b'{"a":NaN}',
        b'{"a":Infinity}',
        b'{"a":1.0}',
        b"[]",
        b"null",
        b'{"a":"\\ud800"}',
        b'{"a":',
        b'{"a": {"b":1,"b":2}}',
        '{"a":1}'.encode("utf-16"),
    ],
)
def test_strict_json(raw):
    with pytest.raises(ValueError):
        strict_json(raw)


def test_profile_fingerprint_and_order(tmp_path):
    data = profile_data()
    a = Profile.from_json(data)
    b = Profile.from_json(dict(reversed(list(data.items()))))
    assert a.fingerprint == b.fingerprint
    data["profile_version"] = 2
    assert a.fingerprint != Profile.from_json(data).fingerprint
    assert load_profile(write_profile(tmp_path, data), host=True).profile_version == 2


@pytest.mark.parametrize(
    "key,value",
    [
        ("approved", False),
        ("approved", 1),
        ("schema_version", True),
        ("schema_version", 2),
        ("profile_version", True),
        ("profile_version", "1"),
        ("model", "\n"),
        ("allowed_slack_hosts", ["*.slack.com"]),
        ("allowed_slack_hosts", ["Example.slack.com"]),
        ("allowed_slack_hosts", []),
        ("extra", "no"),
        ("limits", None),
        ("limits", []),
    ],
)
def test_closed_profile(key, value):
    data = profile_data()
    data[key] = value
    with pytest.raises(ValueError):
        Profile.from_json(data)


@pytest.mark.parametrize(
    "section,key,value",
    [
        ("cli", "path", "relative"),
        ("cli", "verified_version", "2.1.294"),
        ("cli", "minimum_version", "2.1.294"),
        ("cli", "verified_sha256", "B" * 64),
        ("connector", "tool_name", "mcp__read*"),
        ("connector", "server_url", "http://bad.test"),
        ("connector", "server_url", "https://user@bad.test"),
        ("connector", "server_url", "https://bad.test?q=x"),
        ("connector", "input_schema", {"$ref": "https://bad.test/schema"}),
        ("connector", "fixed_arguments", {"permalink": URL}),
        ("connector", "fixed_arguments", {"include_replies": 1}),
        ("limits", "max_tool_calls", True),
        ("limits", "max_turns", 5),
        ("limits", "run_timeout_seconds", 121),
        ("limits", "max_stdout_bytes", 1048577),
    ],
)
def test_profile_nested_boundaries(section, key, value):
    data = profile_data()
    data[section][key] = value
    with pytest.raises(ValueError):
        Profile.from_json(data)


@pytest.mark.parametrize(
    "name", ["claude-slack-profile.example.json", "claude-slack-thread-profile.example.json"]
)
def test_example_unapproved(tmp_path, name):
    data = json.loads((Path("docs/examples") / name).read_text())
    with pytest.raises(ProfileError, match="profile_unapproved"):
        load_profile(write_profile(tmp_path, data), host=True)


@pytest.mark.parametrize(
    "url",
    [
        URL + "?thread_ts=1",
        URL + "#x",
        URL.replace("https", "http"),
        URL.replace("example.slack.com", "other.slack.com"),
        URL.replace("example.slack.com", "example.slack.com:443"),
        URL.replace("example.slack.com", "a@example.slack.com"),
        URL + " ",
        URL.replace("C1", "%431"),
        URL.replace("p123456", "p1.2"),
    ],
)
def test_url_byte_exact(url):
    with pytest.raises(ValueError):
        slack_url(url, ["example.slack.com"])


def test_schema_rejects_open_unknown_and_bool_int():
    with pytest.raises(ValueError):
        validate_schema({"type": "integer"}, True)
    with pytest.raises(ValueError):
        validate_schema({"type": "string", "format": "uri"}, URL)
    with pytest.raises(ValueError):
        validate_schema({"type": "object", "properties": {}, "required": []}, {})
    with pytest.raises(ValueError):
        validate_schema({"type": "integer", "const": True}, 1)


def test_init_exclusive_and_safe_file_permissions(tmp_path, capsys):
    directory = tmp_path / "bridge"
    initialize(directory)
    token = load_token(directory / "token", host=True)
    assert len(token) == 64 and (directory / "token").stat().st_size == 65
    with pytest.raises(FileExistsError):
        initialize(directory)
    assert load_token(directory / "token", host=True) == token
    assert not (directory / "profile.json").exists()
    assert capsys.readouterr().out == ""
    (directory / "token").chmod(0o644)
    with pytest.raises(ValueError):
        load_token(directory / "token", host=True)
    (directory / "token").unlink()
    target = tmp_path / "target"
    target.write_text(TOKEN + "\n")
    target.chmod(0o600)
    (directory / "token").symlink_to(target)
    with pytest.raises(ValueError):
        load_token(directory / "token", host=True)


def test_non_regular_token_never_blocks(tmp_path):
    tmp_path.chmod(0o700)
    os.mkfifo(tmp_path / "token", 0o600)
    with pytest.raises(ValueError):
        load_token(tmp_path / "token", host=True)


def test_result_closed_and_exact_evidence():
    result = result_data()
    assert BridgeResult.from_json(result).for_run(URL, 32768)
    result["evidence_refs"] = [URL, URL]
    with pytest.raises(ValueError):
        BridgeResult.from_json(result).for_run(URL, 32768)
    result["evidence_refs"] = [URL]
    result["summary"] = "\x00"
    with pytest.raises(ValueError):
        BridgeResult.from_json(result)


def test_outcome_and_capability_types():
    from uuid import uuid4

    from bridge_helpers import synthetic_profile

    lease = {
        "runner_id": str(uuid4()),
        "lease_token": str(uuid4()),
        "profile_fingerprint": synthetic_profile().fingerprint,
    }
    with pytest.raises(ValueError):
        CompleteInput.from_json(
            {**lease, "outcome": "succeeded", "result": None, "error_code": None}
        )
    with pytest.raises(ValueError):
        ClaimInput.from_json(
            {
                "runner_id": str(uuid4()),
                "profile_fingerprint": lease["profile_fingerprint"],
                "cli_version": "2.1.309",
                "cli_sha256": "b" * 64,
                "policy_verified": 1,
            }
        )
    assert not Settings().claude_bridge_enabled
    with pytest.raises(ValueError):
        Settings(claude_bridge_enabled="maybe")
