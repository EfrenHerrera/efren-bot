"""Inert, stdio-only native verifier fixture. No Slack, networking or model shell."""

import fcntl
import os
import sys
import time
from pathlib import Path

from efren_bot.bridge.contracts import canonical, strict_json

TOOLS = ("read", "wrong", "crash", "missing", "timeout", "malformed")
PREFIX = "mcp__bridgeprobe__"
URL = "https://example.slack.com/archives/C1/p1"


def record(path, value):
    fd = os.open(path, os.O_APPEND | os.O_WRONLY | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.write(fd, canonical({"tool": value}) + b"\n")
    finally:
        os.close(fd)


def mcp(directory):
    while raw := sys.stdin.buffer.readline(65537):
        if len(raw) > 65536:
            return
        request = strict_json(raw)
        method, identifier = request.get("method"), request.get("id")
        if identifier is None:
            continue
        if method == "initialize":
            result = {
                "protocolVersion": request["params"]["protocolVersion"],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "bridgeprobe", "version": "1"},
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {
                "tools": [
                    {
                        "name": name,
                        "description": "Inert local bridge verification marker; no external IO.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"permalink": {"type": "string"}}
                            if name == "read"
                            else {},
                            "required": ["permalink"] if name == "read" else [],
                            "additionalProperties": False,
                        },
                    }
                    for name in TOOLS
                ]
            }
        elif method == "tools/call" and request.get("params", {}).get("name") in TOOLS:
            # A forbidden native call is harmless but observable. Only our marker is written.
            record(directory / "executed.jsonl", request["params"]["name"])
            result = {"content": [{"type": "text", "text": "local fixture marker"}]}
        else:
            result = {}
        sys.stdout.buffer.write(
            canonical({"jsonrpc": "2.0", "id": identifier, "result": result}) + b"\n"
        )
        sys.stdout.buffer.flush()


def main():
    mode, directory = sys.argv[1], Path(sys.argv[2])
    if mode == "mcp":
        mcp(directory)
        return
    raw = sys.stdin.buffer.read(65537)
    if len(raw) > 65536:
        raise SystemExit(2)
    event = strict_json(raw)
    name = event.get("tool_name")
    if mode == "audit":
        if name not in {PREFIX + tool for tool in TOOLS}:
            raise SystemExit(2)
        # No input, text, transcript or model output saved.
        record(directory / "attempts.jsonl", name.removeprefix(PREFIX))
        print("{}")
    elif mode == "timeout":
        time.sleep(10)
    elif mode == "malformed":
        print("{not-json")
    else:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
