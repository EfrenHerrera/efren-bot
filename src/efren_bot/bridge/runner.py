"""Outbound-only host runner. No DB access, no automatic external-read retries."""

import os
import signal
import subprocess
import threading
from pathlib import Path
from uuid import uuid4

import httpx
from pydantic import AwareDatetime

from efren_bot.bridge.capability import assess
from efren_bot.bridge.contracts import (
    BridgeClaim,
    BridgeRunView,
    Closed,
    canonical,
    strict_json,
)
from efren_bot.bridge.init import BRIDGE_DIR
from efren_bot.bridge.processes import HostLock, checked_directory
from efren_bot.bridge.profile import ProfileError, load_profile, load_token
from efren_bot.bridge.proof import PROOF, REVIEW, EvidenceError, verified_identity
from efren_bot.bridge.supervisor import Supervisor
from efren_bot.config import Settings


class ClaimResponse(Closed):
    claim: BridgeClaim | None


class Pulse(Closed):
    cancel_requested: bool
    lease_expires_at: AwareDatetime
    deadline_at: AwareDatetime


class RunResponse(Closed):
    run: BridgeRunView


class ContactLost(RuntimeError):
    pass


class BridgeClient:
    def __init__(self, token, url="http://127.0.0.1:8000", *, _transport=None):
        if url != "http://127.0.0.1:8000":
            raise ValueError("noncanonical API")
        self.client = httpx.Client(
            base_url=url,
            trust_env=False,
            follow_redirects=False,
            timeout=2,
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
            transport=_transport,
        )

    def close(self):
        self.client.close()

    def post(self, path, data, cls):
        if not path.startswith("/api/bridge/runner/") or "?" in path:
            raise ValueError("invalid runner route")
        try:
            self.client.cookies.clear()
            with self.client.stream("POST", path, content=canonical(data)) as response:
                if response.status_code != 200:
                    raise ContactLost("runner contact lost")
                raw = bytearray()
                for part in response.iter_bytes():
                    raw.extend(part)
                    if len(raw) > 65536:
                        raise ContactLost("runner response limit")
                return cls.from_json(strict_json(bytes(raw)))
        except (httpx.HTTPError, ValueError) as exc:
            raise ContactLost("runner contact lost") from exc


class Runner:
    def __init__(self, client, supervisor, profile_file, *, runner_id=None):
        self.client, self.supervisor, self.profile_file = client, supervisor, profile_file
        self.runner_id = runner_id or uuid4()

    def once(self, profile, capability, stop_event=None):
        if capability.policy_verified is not True or capability.reason is not None:
            raise ValueError("capability_unavailable")
        current = load_profile(self.profile_file, host=True)
        if current.fingerprint != profile.fingerprint:
            raise ValueError("profile_mismatch")
        verified_identity(profile, self.profile_file.parent)
        response = self.client.post(
            "/api/bridge/runner/claim",
            {
                "runner_id": str(self.runner_id),
                "profile_fingerprint": profile.fingerprint,
                "cli_version": capability.cli_version,
                "cli_sha256": capability.cli_sha256,
                "policy_verified": True,
            },
            ClaimResponse,
        )
        if response.claim is None:
            return False
        claim = response.claim
        data = {
            "runner_id": str(self.runner_id),
            "lease_token": str(claim.lease_token),
            "profile_fingerprint": profile.fingerprint,
        }
        route = "/api/bridge/runner/runs/" + str(claim.run.id)

        def heartbeat():
            verified_identity(profile, self.profile_file.parent)
            return self.client.post(route + "/heartbeat", data, Pulse)

        verified_identity(profile, self.profile_file.parent)
        outcome = self.supervisor.execute(claim, profile, heartbeat, stop_event)
        # Group is confirmed extinct/reaped before HTTP complete or another claim.
        # Failure of complete is not retried and never causes another external read.
        if load_profile(self.profile_file, host=True).fingerprint != profile.fingerprint:
            raise ValueError("profile_mismatch")
        verified_identity(profile, self.profile_file.parent)
        self.client.post(
            route + "/complete",
            {
                **data,
                "outcome": outcome.outcome,
                "result": outcome.result.model_dump(mode="json") if outcome.result else None,
                "error_code": outcome.error_code,
            },
            RunResponse,
        )
        return True


def run_loop(settings, stop, directory=BRIDGE_DIR):
    """Pending is an idle state, not a compatible presence or an authorization."""
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    checked_directory(directory)
    client = None
    previous_reason = None
    last_profile = None
    capability = None
    token_path = Path(settings.claude_bridge_token_file)
    profile_path = Path(settings.claude_bridge_profile_file)
    try:
        with HostLock(directory) as lock:
            runs = directory / "runs"
            runs.mkdir(mode=0o700, exist_ok=True)
            checked_directory(runs)
            while not stop.is_set():
                reason = None
                try:
                    token = load_token(token_path, host=True)
                except (OSError, ValueError):
                    reason = "token_unavailable"
                if reason is None:
                    try:
                        profile = load_profile(profile_path, host=True)
                    except ProfileError as exc:
                        reason = exc.reason
                if reason is None:
                    revision = [profile.fingerprint]
                    for name in (PROOF, REVIEW):
                        try:
                            info = (directory / name).lstat()
                            revision.append(
                                (info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
                            )
                        except FileNotFoundError:
                            revision.append(None)
                    if last_profile != revision:
                        last_profile = revision
                        try:
                            capability = assess(profile, runs)
                        except (ValueError, OSError, subprocess.SubprocessError):
                            capability = None
                    if capability is None or not capability.policy_verified:
                        reason = capability.reason if capability else "capability_unavailable"
                    else:
                        try:
                            verified_identity(profile, directory)
                        except EvidenceError as exc:
                            reason = exc.reason
                if reason is not None:
                    if previous_reason != reason:
                        print("bridge-runner pending: " + reason, flush=True)
                        previous_reason = reason
                    stop.wait(1)  # local configuration only; no API/client/model calls
                    continue
                if client is None:
                    client = BridgeClient(token, settings.claude_bridge_api_url)
                    runner = Runner(client, Supervisor(runs, profile_path, lock), profile_path)
                runner.once(profile, capability, stop)
                stop.wait(1)  # idle queue polling only; external reads never auto-retry
    finally:
        if client:
            client.close()


def main():
    settings = Settings(
        claude_bridge_token_file=os.environ.get(
            "CLAUDE_BRIDGE_TOKEN_FILE", str(BRIDGE_DIR / "token")
        ),
        claude_bridge_profile_file=os.environ.get(
            "CLAUDE_BRIDGE_PROFILE_FILE", str(BRIDGE_DIR / "profile.json")
        ),
    )  # APP_ENV=local and API URL validated before any child/contact
    if not settings.claude_bridge_enabled:
        print("bridge-runner disabled")
        return
    stop = threading.Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *args: stop.set())
    try:
        run_loop(settings, stop)
    except (ValueError, OSError, RuntimeError):
        raise SystemExit(
            "bridge-runner blocked: capability/configuration/contact unavailable; no fallback"
        ) from None


if __name__ == "__main__":
    main()
