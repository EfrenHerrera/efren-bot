"""Local synthetic profile only; never an approval for the installed real client."""

import json

from efren_bot.bridge.profile import Profile

URL = "https://example.slack.com/archives/C1/p123456"
THREAD_URL = "https://example.slack.com/archives/Copaque9/p1234567890123456"
TOKEN = "a" * 64


def profile_data():
    return {
        "schema_version": 1,
        "profile_id": "test-read",
        "profile_version": 1,
        "approved": True,
        "cli": {
            "path": "/not-a-real-cli/claude",
            "minimum_version": "2.1.295",
            "verified_version": "2.1.309",
            "verified_sha256": "b" * 64,
        },
        "model": "synthetic-test-model",
        "allowed_slack_hosts": ["example.slack.com"],
        "connector": {
            "kind": "claude_ai",
            "server_url": "https://connector.example.invalid/slack",
            "tool_name": "mcp__test__read_thread",
            "url_argument": "permalink",
            "fixed_arguments": {"include_replies": True},
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["permalink", "include_replies"],
                "properties": {
                    "permalink": {"type": "string"},
                    "include_replies": {"type": "boolean"},
                },
            },
        },
        "limits": {
            "run_timeout_seconds": 120,
            "max_turns": 4,
            "max_tool_calls": 1,
            "max_stdout_bytes": 1048576,
            "max_stderr_bytes": 65536,
            "max_result_bytes": 32768,
        },
    }


def write_profile(directory, data=None):
    directory.mkdir(mode=0o700, exist_ok=True)
    directory.chmod(0o700)
    path = directory / "profile.json"
    path.write_text(json.dumps(data or profile_data()))
    path.chmod(0o600)
    return path


def thread_profile_data():
    data = profile_data()
    data["schema_version"] = 2
    data["connector"] = {
        "kind": "claude_ai",
        "selector": "slack_thread_v1",
        "server_url": "https://mcp.slack.com/mcp",
        "tool_name": "mcp__claude_ai_Slack__slack_read_thread",
        "fixed_arguments": {"limit": 100, "response_format": "concise"},
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string"},
                "message_ts": {"type": "string"},
                "limit": {"type": "integer", "const": 100},
                "response_format": {"type": "string", "const": "concise"},
            },
            "required": ["channel_id", "message_ts", "limit", "response_format"],
            "additionalProperties": False,
        },
    }
    return data


def synthetic_profile():
    return Profile.from_json(profile_data())


def result_data():
    return {
        "summary": "Synthetic summary",
        "proposed_actions": ["Review source"],
        "missing_context": [],
        "evidence_refs": [URL],
        "warnings": [],
    }
