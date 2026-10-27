"""Hostile local CLI double. Does not certify installed Claude hooks or use network."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

mode, *args = sys.argv[1:]
time.sleep(0.05)  # let supervisor record kernel process identity before fast exit


def flag(name):
    return args[args.index(name) + 1]


def emit(data):
    print(json.dumps(data), flush=True)


forbidden = {
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "OPENAI_API_KEY",
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "ALL_PROXY",
    "CLAUDE_BRIDGE_TOKEN_FILE",
    "CLAUDE_BRIDGE_PROFILE_FILE",
    "CLAUDE_BRIDGE_ENABLED",
    "PYTHONPATH",
}
if forbidden & set(os.environ):
    raise SystemExit(31)
if any(
    x in args for x in ("--allowedTools", "--bare", "--safe-mode", "--dangerously-skip-permissions")
):
    raise SystemExit(32)
data = json.loads(sys.stdin.read())
url = data["authorized_slack_permalink"]
assert url not in args
settings = json.loads(Path(flag("--settings")).read_text())
hook = settings["hooks"]["PreToolUse"][0]["hooks"][0]
policy = json.loads(Path(hook["args"][-1]).read_text())
connector = policy["profile"]["connector"]
if policy["profile"]["schema_version"] == 2:
    # Independent expectation, not a call to the production mapping helper.
    channel, stamp = url.rsplit("/", 2)[-2:]
    digits = stamp[1:]
    expected_input = {
        "channel_id": channel,
        "message_ts": digits[:-6] + "." + digits[-6:],
        "limit": 100,
        "response_format": "concise",
    }
else:
    expected_input = {**connector["fixed_arguments"], connector["url_argument"]: url}
assert data["authorized_tool_name"] == connector["tool_name"]
assert data["authorized_tool_arguments"] == expected_input
assert os.environ["ENABLE_TOOL_SEARCH"] == "false"
event = {
    "hook_event_name": "PreToolUse",
    "session_id": flag("--session-id"),
    "tool_name": connector["tool_name"],
    "tool_use_id": "tool-1",
    "tool_input": expected_input,
}
if mode in {"sleep", "ignore", "child"}:
    child = None
    if mode == "ignore":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    if mode == "child":
        child = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(60)",
            ]
        )

        def cleanup(*unused):
            child.kill()
            child.wait(timeout=1)
            raise SystemExit(0)

        signal.signal(signal.SIGTERM, cleanup)
    time.sleep(60)
    raise SystemExit(0)
if mode == "oversize":
    os.write(sys.stdout.fileno(), b"x" * 2000000)
    time.sleep(5)
    raise SystemExit(0)
if mode == "stderr":
    os.write(sys.stderr.fileno(), b"untrusted-secret" * 10000)
    time.sleep(5)
    raise SystemExit(0)
if mode == "invalidstream":
    print("not-json", flush=True)
    raise SystemExit(0)
if mode == "wrongtool":
    event["tool_name"] = "Bash"
if mode == "wrongurl":
    selector = (
        "message_ts" if policy["profile"]["schema_version"] == 2 else connector["url_argument"]
    )
    event["tool_input"][selector] += "0"
if mode == "extra":
    event["tool_input"]["cursor"] = "next"
hook_ok = False
if mode != "nohook":
    command = [hook["command"], *hook["args"]]
    if mode == "missinghook":
        command = ["/nonexistent-efren-bot-hook"]
    elif mode == "hookcrash":
        command = [sys.executable, "-c", "raise SystemExit(3)"]
    elif mode == "hooktimeout":
        command = [sys.executable, "-c", "import time; time.sleep(60)"]
    elif mode == "hookbadjson":
        command = [sys.executable, "-c", "print('{}')"]
    try:
        attempts = 2 if mode == "twice" else 1
        for _ in range(attempts):
            result = subprocess.run(
                command,
                input=json.dumps(event).encode(),
                capture_output=True,
                timeout=hook["timeout"],
                check=False,
            )
            hook_ok = (
                result.returncode == 0
                and json.loads(result.stdout)
                .get("hookSpecificOutput", {})
                .get("permissionDecision")
                == "allow"
            )
    except (OSError, ValueError, subprocess.TimeoutExpired):
        hook_ok = False
emit({"type": "system", "subtype": "init"})
if hook_ok or mode in {"nohook", "twice"}:
    emit(
        {
            "type": "assistant",
            "message": {
                "id": "assistant-1",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tool-1",
                        "name": event["tool_name"],
                        "input": event["tool_input"],
                    }
                ],
            },
        }
    )
    emit(
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tool-1",
                        "is_error": mode == "toolerror",
                        "content": "RAW_SLACK_SECRET_NOT_TO_PERSIST",
                    }
                ]
            },
        }
    )
if mode == "turns":
    for i in range(5):
        emit({"type": "assistant", "message": {"id": f"extra-{i}", "content": []}})
result = {
    "summary": "Synthetic proposal",
    "proposed_actions": ["Review original"],
    "missing_context": [],
    "evidence_refs": [url],
    "warnings": [],
}
if mode == "invalidfinal":
    result["evidence_refs"] = [url + "0"]
emit(
    {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": json.dumps(result),
        "total_cost_usd": 0.0,
    }
)
if mode == "duplicateresult":
    emit({"type": "result", "subtype": "success", "is_error": False, "result": json.dumps(result)})
