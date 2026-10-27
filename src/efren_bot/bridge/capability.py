"""Local client checks, NOT a claim that effective managed policy was observed."""

import hashlib
import os
import pwd
import re
import selectors
import signal
import stat
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from efren_bot.bridge.processes import process_identity, terminate_owned
from efren_bot.bridge.profile import version

FLAGS = (
    "--restricted",
    "--setting-sources",
    "--settings",
    "--tools",
    "--permission-mode",
    "--permission-prompts",
    "--disable-slash-commands",
    "--no-chrome",
    "--no-session-persistence",
    "--output-format",
    "--verbose",
    "--include-hook-events",
    "--model",
    "--system-prompt",
    "--session-id",
    "--max-turns",
)
# Official CLI reference: --help is not exhaustive; --max-turns is print-only.
# Keep this exception closed, not inferred from missing help entries or profile input.
# https://code.claude.com/docs/en/cli-reference
DOCUMENTED_HIDDEN_FLAGS = frozenset({"--max-turns"})


def child_environment(directory: Path):
    # No os.environ copy, API keys, provider switches, endpoints, proxies or HTTP secret.
    return {
        "HOME": pwd.getpwuid(os.getuid()).pw_dir,
        "PATH": "/usr/bin:/bin",
        "LANG": "en_US.UTF-8",
        "LC_ALL": "en_US.UTF-8",
        "TMPDIR": str(directory),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "APP_ENV": "local",
        # Official MCP docs: direct definitions, no deferred ToolSearch exception.
        "ENABLE_TOOL_SEARCH": "false",
    }


def binary_digest(path: Path):
    target = path.resolve(strict=True)
    info = target.stat()
    if (
        not stat.S_ISREG(info.st_mode)
        or not os.access(target, os.X_OK)
        or info.st_mode & 0o022
        or info.st_uid not in {0, os.getuid()}
    ):
        raise ValueError("unsafe client")
    with target.open("rb") as binary:
        return hashlib.file_digest(binary, "sha256").hexdigest()


def metadata_output(path, flag, directory):
    """Fixed metadata-only commands, with separate byte caps and a total deadline."""
    if flag not in {"--version", "--help"} or not Path(path).is_absolute():
        raise ValueError("invalid metadata command")
    process = subprocess.Popen(
        [path, flag],
        cwd=directory,
        env=child_environment(directory),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        shell=False,
        close_fds=True,
    )
    identity = None
    output = bytearray()
    counts = {"stdout": 0, "stderr": 0}
    deadline = time.monotonic() + 5
    try:
        identity = process_identity(process.pid)
        if identity is None or identity["pgid"] != process.pid:
            raise ValueError("client identity unavailable")
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            while selector.get_map():
                if time.monotonic() >= deadline:
                    raise ValueError("client metadata timeout")
                for key, _ in selector.select(timeout=0.05):
                    raw = os.read(key.fileobj.fileno(), 4096)
                    if not raw:
                        selector.unregister(key.fileobj)
                        continue
                    counts[key.data] += len(raw)
                    if counts[key.data] > 65536:
                        raise ValueError("client metadata limit")
                    if key.data == "stdout":
                        output.extend(raw)
        if process.wait(timeout=max(0.001, deadline - time.monotonic())) != 0:
            raise ValueError("client unavailable")
        return output.decode("utf-8", errors="strict")
    finally:
        if identity is not None:
            terminate_owned(process, identity)
        else:
            # No poll/wait has occurred yet: this Popen still owns an unreaped
            # fresh child PID, so its new session cannot be a reused foreign PID.
            try:
                if os.getpgid(process.pid) == process.pid:
                    os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=2)
        process.stdout.close()
        process.stderr.close()


def probe_binary(profile, directory):
    digest = binary_digest(Path(profile.cli.path))
    if digest != profile.cli.verified_sha256:
        raise ValueError("client drift")
    outputs = []
    for flag in ("--version", "--help"):
        # Metadata-only official invocations. Never auth/status/MCP/model prompts.
        outputs.append(metadata_output(profile.cli.path, flag, directory))
    match = re.fullmatch(r"([0-9]+\.[0-9]+\.[0-9]+) \(Claude Code\)\s*", outputs[0])
    if (
        not match
        or match[1] != profile.cli.verified_version
        or version(match[1]) < version("2.1.295")
        or any(flag not in outputs[1] for flag in FLAGS if flag not in DOCUMENTED_HIDDEN_FLAGS)
        or binary_digest(Path(profile.cli.path)) != digest
    ):
        raise ValueError("client incompatible")
    return match[1], digest


@dataclass(frozen=True)
class Capability:
    cli_version: str
    cli_sha256: str
    policy_verified: bool
    reason: str | None


def assess(profile, directory):
    from efren_bot.bridge.proof import EvidenceError, verified_identity

    try:
        # No Claude metadata/model invocation before a reviewed native receipt exists.
        verified_identity(profile, directory.parent)
    except EvidenceError as exc:
        return Capability(
            profile.cli.verified_version, profile.cli.verified_sha256, False, exc.reason
        )
    cli_version, digest = probe_binary(profile, directory)
    return Capability(cli_version, digest, True, None)
