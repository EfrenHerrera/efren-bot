"""Exec-form PreToolUse boundary. One exact read attempt, denied by default."""

import fcntl
import os
import re
import stat
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from pydantic import AwareDatetime, model_validator

from efren_bot.bridge.contracts import Closed, Fingerprint, canonical, strict_json
from efren_bot.bridge.profile import Profile, load_profile, own_file


class RunPolicy(Closed):
    run_id: UUID
    deadline_at: AwareDatetime
    profile_file: str
    profile: Profile
    profile_fingerprint: Fingerprint
    requested_slack_permalink: str

    @model_validator(mode="after")
    def valid(self):
        if self.profile.fingerprint != self.profile_fingerprint:
            raise ValueError("invalid snapshot")
        if not Path(self.profile_file).is_absolute():
            raise ValueError("invalid path")
        self.profile.arguments(self.requested_slack_permalink)
        return self


def write_exclusive(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        raw = canonical(data)
        with os.fdopen(fd, "wb", closefd=False) as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
    finally:
        os.close(fd)


def read_policy(path):
    policy = RunPolicy.from_json(strict_json(own_file(path, host=True, maximum=65536)))
    if load_profile(Path(policy.profile_file), host=True).fingerprint != policy.profile_fingerprint:
        raise ValueError("profile drift")
    return policy


def validate_budget(data):
    if (
        set(data) != {"used", "violation", "tool_use_id"}
        or type(data["used"]) is not bool
        or type(data["violation"]) is not bool
        or data["tool_use_id"] is not None
        and not isinstance(data["tool_use_id"], str)
    ):
        raise ValueError("invalid budget")
    return data


def budget_fd(path, flags):
    fd = os.open(path, flags | os.O_NOFOLLOW | os.O_NONBLOCK)
    info = os.fstat(fd)
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_size > 1024
    ):
        os.close(fd)
        raise ValueError("invalid budget")
    return fd


def budget_state(path):
    fd = budget_fd(path, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        return validate_budget(strict_json(os.read(fd, 1025)))
    finally:
        os.close(fd)


def decide(policy_path: Path, event: dict):
    """The stable budget inode is locked; all changes fsync before permission allow."""
    budget = policy_path.parent / "budget.json"
    fd = budget_fd(budget, os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        info = os.fstat(fd)
        if info.st_ino != budget.lstat().st_ino:
            raise ValueError("budget changed")
        state = validate_budget(strict_json(os.read(fd, 1025)))
        valid = False
        try:
            policy = read_policy(policy_path)
            tool_id = event.get("tool_use_id")
            valid = (
                not state["used"]
                and not state["violation"]
                and not set(event)
                - {
                    "hook_event_name",
                    "session_id",
                    "tool_name",
                    "tool_input",
                    "tool_use_id",
                    "transcript_path",
                    "cwd",
                    "permission_mode",
                }
                and datetime.now(UTC) < policy.deadline_at
                and event.get("hook_event_name") == "PreToolUse"
                and event.get("session_id") == str(policy.run_id)
                and event.get("tool_name") == policy.profile.connector.tool_name
                and type(tool_id) is str
                and 1 <= len(tool_id) <= 256
                and re.fullmatch(r"[A-Za-z0-9_-]+", tool_id) is not None
                and canonical(event.get("tool_input"))
                == canonical(policy.profile.arguments(policy.requested_slack_permalink))
            )
        except (ValueError, OSError, KeyError, TypeError):
            valid = False
        if valid:
            state["used"], state["tool_use_id"] = True, tool_id
        else:
            state["violation"] = True
        raw = canonical(state)
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
        os.write(fd, raw)
        os.fsync(fd)
        return "allow" if valid else "deny"
    finally:
        os.close(fd)


def main():
    decision, code = "deny", 2
    try:
        if len(sys.argv) != 2:
            raise ValueError("invalid invocation")
        raw = sys.stdin.buffer.read(65537)
        # Invalid JSON still poisons the budget: never accept a subsequent final result.
        try:
            event = strict_json(raw) if len(raw) <= 65536 else {}
        except ValueError:
            event = {}
        decision = decide(Path(sys.argv[1]), event)
        code = 0 if decision == "allow" else 2
    except Exception:
        pass  # onFailure:block, no exception/raw input in stdout or stderr
    sys.stdout.buffer.write(
        canonical(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": decision,
                }
            }
        )
    )
    sys.stdout.buffer.write(b"\n")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
