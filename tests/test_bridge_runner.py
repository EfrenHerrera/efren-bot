import select
import subprocess
import sys

import httpx
import pytest
from bridge_helpers import TOKEN, profile_data, synthetic_profile, write_profile

from efren_bot.bridge.capability import Capability
from efren_bot.bridge.init import initialize
from efren_bot.bridge.processes import process_identity, terminate_owned
from efren_bot.bridge.runner import BridgeClient, ClaimResponse, ContactLost, Runner, run_loop
from efren_bot.config import Settings


@pytest.mark.parametrize("status", [301, 302, 307, 401, 409, 503])
def test_http_no_redirect_no_retry_no_origin(status):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.headers["host"] == "127.0.0.1:8000"
        assert "origin" not in request.headers
        assert request.headers["authorization"] == "Bearer " + TOKEN
        return httpx.Response(status, headers={"Location": "https://never-visit.invalid"})

    client = BridgeClient(TOKEN, _transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(ContactLost):
            client.post("/api/bridge/runner/claim", {}, ClaimResponse)
        assert len(requests) == 1
    finally:
        client.close()


@pytest.mark.parametrize("raw", [b"x" * 65537, b'{"claim":null,"claim":null}', b'{"claim":NaN}'])
def test_http_response_limit_and_strict_json(raw):
    client = BridgeClient(
        TOKEN, _transport=httpx.MockTransport(lambda r: httpx.Response(200, content=raw))
    )
    try:
        with pytest.raises(ContactLost):
            client.post("/api/bridge/runner/claim", {}, ClaimResponse)
    finally:
        client.close()


def test_api_url_is_not_configurable_to_network():
    for url in ("http://localhost:8000", "https://127.0.0.1:8000", "http://evil.test"):
        with pytest.raises(ValueError):
            BridgeClient(TOKEN, url)


def test_capability_gate_before_any_contact_or_launch(tmp_path):
    path = write_profile(tmp_path)

    class Forbidden:
        def __getattr__(self, name):
            pytest.fail("unverified capability must not contact API or launch a process")

    runner = Runner(Forbidden(), Forbidden(), path)
    with pytest.raises(ValueError, match="capability_unavailable"):
        runner.once(
            synthetic_profile(), Capability("2.1.309", "b" * 64, False, "capability_unavailable")
        )


@pytest.mark.parametrize("configuration", ["missing", "unapproved", "capability"])
def test_pending_idle_no_contact_and_no_repeat_probe(tmp_path, monkeypatch, configuration):
    initialize(tmp_path)
    if configuration != "missing":
        data = profile_data()
        data["approved"] = configuration != "unapproved"
        write_profile(tmp_path, data)
    calls = []

    def unavailable(profile, runs):
        calls.append(profile.fingerprint)
        return Capability("2.1.309", "b" * 64, False, "capability_unavailable")

    monkeypatch.setattr("efren_bot.bridge.runner.assess", unavailable)
    monkeypatch.setattr(
        "efren_bot.bridge.runner.BridgeClient", lambda *a: pytest.fail("no API contact")
    )

    class Stop:
        count = 0

        def is_set(self):
            return self.count >= 3

        def wait(self, seconds):
            self.count += 1

    run_loop(
        Settings(
            claude_bridge_enabled=True,
            claude_bridge_token_file=str(tmp_path / "token"),
            claude_bridge_profile_file=str(tmp_path / "profile.json"),
        ),
        Stop(),
        tmp_path,
    )
    assert len(calls) == (1 if configuration == "capability" else 0)
    assert not (tmp_path / "active.json").exists()


def test_main_real_process_stays_idle_unapproved_and_exits_cleanly(tmp_path):
    initialize(tmp_path)
    data = profile_data()
    data["approved"] = False
    path = write_profile(tmp_path, data)
    # All fake data in an own temporary directory; no global config or credentials.
    env = {
        "PATH": "/usr/bin:/bin",
        "APP_ENV": "local",
        "CLAUDE_BRIDGE_ENABLED": "true",
        "CLAUDE_BRIDGE_TOKEN_FILE": str(tmp_path / "token"),
        "CLAUDE_BRIDGE_PROFILE_FILE": str(path),
    }
    # The entrypoint's host operational directory is injected only in this test's
    # Python command, never via a production env/HTTP executable replacement.
    code = (
        "from pathlib import Path;from threading import Event;"
        "import signal;from efren_bot.bridge.runner import run_loop;"
        "from efren_bot.config import Settings;s=Event();"
        "signal.signal(signal.SIGTERM,lambda *a:s.set());"
        f"run_loop(Settings(),s,Path({str(tmp_path)!r}))"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", code],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    identity = process_identity(process.pid)
    try:
        readable, _, _ = select.select([process.stdout], [], [], 3)
        assert readable, "idle runner did not announce its pending state"
        assert process.stdout.readline() == b"bridge-runner pending: profile_unapproved\n"
        assert process.poll() is None
    finally:
        terminate_owned(process, identity)
        stdout, stderr = process.communicate(timeout=2)
    assert process.returncode == 0 and stdout == b"" and stderr == b""
    assert not (tmp_path / "active.json").exists()
