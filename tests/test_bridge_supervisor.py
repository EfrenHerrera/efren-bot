import os
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from bridge_helpers import THREAD_URL, URL, synthetic_profile, thread_profile_data, write_profile

from efren_bot.bridge.capability import (
    Capability,
    assess,
    child_environment,
    metadata_output,
    probe_binary,
)
from efren_bot.bridge.contracts import BridgeClaim, BridgeRunView, canonical
from efren_bot.bridge.policy import write_exclusive
from efren_bot.bridge.processes import HostLock, RecoveryRequired, process_identity
from efren_bot.bridge.profile import Profile
from efren_bot.bridge.runner import Pulse
from efren_bot.bridge.supervisor import Supervisor, arguments, settings_for, validate_settings

FAKE = Path(__file__).parent / "fakes" / "bridge_cli.py"


def claim_for(profile, *, seconds=10, url=URL):
    now = datetime.now(UTC)
    return BridgeClaim(
        run=BridgeRunView(
            id=uuid4(),
            requested_slack_permalink=url,
            profile_id=profile.profile_id,
            profile_version=profile.profile_version,
            profile_fingerprint=profile.fingerprint,
            status="running",
            cancel_requested=False,
            created_at=now,
            started_at=now,
            finished_at=None,
            deadline_at=now + timedelta(seconds=seconds),
            result=None,
            error_code=None,
        ),
        lease_token=uuid4(),
        lease_expires_at=now + timedelta(seconds=min(seconds, 15)),
    )


def pulse_for(claim, cancel=False):
    return Pulse(
        cancel_requested=cancel,
        lease_expires_at=claim.lease_expires_at,
        deadline_at=claim.run.deadline_at,
    )


@pytest.fixture
def supervisor_setup(tmp_path):
    profile_file = write_profile(tmp_path)
    runs = tmp_path / "runs"
    runs.mkdir(mode=0o700)
    return profile_file, runs


def execute_fake(setup, mode, heartbeat=None, seconds=10, stop=None, profile=None):
    profile_file, runs = setup
    profile = profile or synthetic_profile()
    url = THREAD_URL if profile.schema_version == 2 else URL
    claim = claim_for(profile, seconds=seconds, url=url)
    launched = []

    def launch(argv, **kwargs):
        assert kwargs["shell"] is False and kwargs["start_new_session"] is True
        assert kwargs["close_fds"] is True and url not in argv
        assert kwargs["env"] == child_environment(kwargs["cwd"])
        process = subprocess.Popen([sys.executable, str(FAKE), mode, *argv[1:]], **kwargs)
        launched.append(process)
        return process

    with HostLock(runs.parent) as lock:
        supervisor = Supervisor(
            runs, profile_file, lock, _launch=launch, _probe=lambda *args: ("2.1.309", "b" * 64)
        )
        callback = heartbeat or (lambda: pulse_for(claim))
        result = supervisor.execute(claim, profile, callback, stop)
        assert not lock.journal.exists()
    assert all(p.poll() is not None for p in launched)
    assert not list(runs.iterdir())
    return result, launched


@pytest.mark.parametrize(
    "mode", ["success", "wrongtool", "wrongurl", "extra", "twice", "nohook", "toolerror"]
)
def test_native_thread_binding_fake_protocol(supervisor_setup, mode, capsys):
    profile_file, _ = supervisor_setup
    data = thread_profile_data()
    write_profile(profile_file.parent, data)
    result, _ = execute_fake(supervisor_setup, mode, profile=Profile.from_json(data))
    if mode == "success":
        assert result.outcome == "succeeded"
        assert result.result.evidence_refs == [THREAD_URL]
        assert any("100 mensajes" in w for w in result.result.warnings)
        assert "RAW_SLACK_SECRET" not in result.result.model_dump_json()
    else:
        assert result.outcome == "failed" and result.result is None
    assert capsys.readouterr() == ("", "")


def test_success_environment_no_stream_persistence(supervisor_setup, monkeypatch, capsys):
    for name in (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "HTTPS_PROXY",
        "OPENAI_API_KEY",
        "CLAUDE_BRIDGE_TOKEN_FILE",
    ):
        monkeypatch.setenv(name, "secret-never-to-child")
    result, _ = execute_fake(supervisor_setup, "success")
    assert result.outcome == "succeeded" and result.result.evidence_refs == [URL]
    assert "contexto puede ser parcial" in result.result.warnings[0]
    assert "RAW_SLACK_SECRET" not in result.result.model_dump_json()
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "mode",
    [
        "wrongtool",
        "wrongurl",
        "extra",
        "twice",
        "nohook",
        "toolerror",
        "invalidfinal",
        "oversize",
        "stderr",
        "turns",
        "invalidstream",
        "duplicateresult",
        "missinghook",
        "hookcrash",
        "hooktimeout",
        "hookbadjson",
    ],
)
def test_hostile_cli_never_succeeds(supervisor_setup, mode):
    result, _ = execute_fake(supervisor_setup, mode)
    assert result.outcome == "failed" and result.result is None
    assert result.error_code in {"policy_denied", "cli_failed", "invalid_result", "output_limit"}


@pytest.mark.parametrize("mode", ["sleep", "ignore", "child"])
def test_timeout_terminates_and_reaps_group(supervisor_setup, mode):
    result, processes = execute_fake(supervisor_setup, mode, seconds=0.5)
    assert result.outcome == "failed" and result.error_code in {"timeout", "interrupted"}
    for process in processes:
        with pytest.raises(ProcessLookupError):
            os.killpg(process.pid, 0)


def test_cancel_and_lease_loss_stop_before_next_claim(supervisor_setup):
    calls = 0

    def cancel():
        nonlocal calls
        calls += 1
        now = datetime.now(UTC)
        return Pulse(
            cancel_requested=calls > 1,
            lease_expires_at=now + timedelta(seconds=15),
            deadline_at=now + timedelta(seconds=10),
        )

    result, _ = execute_fake(supervisor_setup, "child", heartbeat=cancel)
    assert result.outcome == "cancelled"

    def unavailable():
        raise OSError("do-not-echo")

    result, processes = execute_fake(supervisor_setup, "sleep", heartbeat=unavailable)
    assert result.error_code == "interrupted" and not processes
    stopped = threading.Event()
    stopped.set()
    result, _ = execute_fake(supervisor_setup, "sleep", stop=stopped)
    assert result.error_code == "interrupted"


def test_settings_closed_and_fail_closed_hook(supervisor_setup):
    profile, runs = supervisor_setup
    path = runs / "policy.json"
    settings = settings_for(path, sys.executable, "https://connector.example.invalid")
    validate_settings(
        canonical(settings), path, sys.executable, "https://connector.example.invalid"
    )
    assert settings["hooks"]["PreToolUse"][0]["hooks"][0]["onFailure"] == "block"
    settings["hooks"]["PreToolUse"][0]["hooks"][0].pop("onFailure")
    with pytest.raises(ValueError):
        validate_settings(
            canonical(settings), path, sys.executable, "https://connector.example.invalid"
        )


def test_real_capability_not_inferred_from_mock_probe(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "efren_bot.bridge.capability.probe_binary", lambda *a: ("2.1.309", "b" * 64)
    )
    capability = assess(synthetic_profile(), tmp_path)
    assert capability == Capability("2.1.309", "b" * 64, False, "policy_proof_missing")


@pytest.mark.parametrize(
    "missing",
    [
        None,
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
    ],
)
def test_probe_hidden_max_turns_preserves_required_help_and_proof(tmp_path, monkeypatch, missing):
    profile = synthetic_profile()
    # Independent synthetic help matching the observed 2.1.309 surface: the official
    # print-only --max-turns flag is supported but not advertised by --help.
    help_flags = (
        "--restricted --setting-sources --settings --tools --permission-mode "
        "--permission-prompts --disable-slash-commands --no-chrome "
        "--no-session-persistence --output-format --verbose --include-hook-events "
        "--model --system-prompt --session-id"
    ).split()
    if missing is not None:
        help_flags.remove(missing)
    calls = []

    def metadata(path, flag, directory):
        assert path == profile.cli.path and directory == tmp_path
        calls.append(flag)
        assert flag in {"--version", "--help"}
        return "2.1.309 (Claude Code)\n" if flag == "--version" else "\n".join(help_flags)

    monkeypatch.setattr("efren_bot.bridge.capability.binary_digest", lambda path: "b" * 64)
    monkeypatch.setattr("efren_bot.bridge.capability.metadata_output", metadata)
    if missing is not None:
        with pytest.raises(ValueError, match="client incompatible"):
            probe_binary(profile, tmp_path)
    else:
        assert probe_binary(profile, tmp_path) == ("2.1.309", "b" * 64)
        argv = arguments(profile, claim_for(profile).run, tmp_path / "settings.json")
        assert "-p" in argv and argv.count("--max-turns") == 1
        assert argv[argv.index("--max-turns") + 1] == str(profile.limits.max_turns)
        assert assess(profile, tmp_path) == Capability(
            "2.1.309", "b" * 64, False, "policy_proof_missing"
        )
    assert calls == ["--version", "--help"]


def test_host_single_instance_and_uncertain_launch_recovery(tmp_path):
    tmp_path.chmod(0o700)
    with HostLock(tmp_path):
        with pytest.raises(BlockingIOError), HostLock(tmp_path):
            pass
    with HostLock(tmp_path) as lock:
        lock.launching(uuid4())
    with pytest.raises(RecoveryRequired), HostLock(tmp_path):
        pass


def test_reused_pid_never_killed_or_silently_recovered(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    identity = {"pid": 1000001, "pgid": 1000001, "start": "old-start"}
    write_exclusive(
        tmp_path / "active.json", {"state": "running", "run_id": str(uuid4()), "identity": identity}
    )
    monkeypatch.setattr(
        "efren_bot.bridge.processes.process_identity", lambda pid: {**identity, "start": "reused"}
    )
    monkeypatch.setattr(os, "killpg", lambda *args: pytest.fail("must not signal unknown group"))
    with pytest.raises(RecoveryRequired), HostLock(tmp_path):
        pass
    assert (tmp_path / "active.json").exists()


def test_kernel_identity_of_own_process():
    identity = process_identity(os.getpid())
    assert identity["pid"] == os.getpid() and identity["pgid"] == os.getpgid(0)
    assert identity["start"].startswith(("darwin:", "linux:"))


@pytest.mark.parametrize("boundary", ["deadline", "lease"])
def test_blocked_heartbeat_cannot_extend_process_life(supervisor_setup, monkeypatch, boundary):
    from efren_bot.bridge.processes import terminate_owned

    stopped = []
    began = time.monotonic()
    calls = 0

    def record_stop(process, identity):
        terminate_owned(process, identity)
        stopped.append(time.monotonic() - began)

    monkeypatch.setattr("efren_bot.bridge.supervisor.terminate_owned", record_stop)

    def blocked():
        nonlocal calls
        calls += 1
        if calls > 1:
            time.sleep(1)  # deliberately exceeds the run/lease boundary
        now = datetime.now(UTC)
        return Pulse(
            cancel_requested=False,
            lease_expires_at=now + timedelta(seconds=0.25 if boundary == "lease" else 10),
            deadline_at=now + timedelta(seconds=10),
        )

    result, _ = execute_fake(
        supervisor_setup,
        "sleep",
        heartbeat=blocked,
        seconds=0.3 if boundary == "deadline" else 10,
    )
    assert stopped and stopped[0] < 0.85
    assert result.error_code == ("timeout" if boundary == "deadline" else "interrupted")


def test_recovery_clears_only_confirmed_extinct_group(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    write_exclusive(
        tmp_path / "active.json",
        {
            "state": "running",
            "run_id": str(uuid4()),
            "identity": {"pid": 1000001, "pgid": 1000001, "start": "old-start"},
        },
    )
    monkeypatch.setattr("efren_bot.bridge.processes.process_identity", lambda pid: None)
    monkeypatch.setattr("efren_bot.bridge.processes.group_alive", lambda pgid: False)
    with HostLock(tmp_path):
        assert not (tmp_path / "active.json").exists()


def test_owned_exit_transition_reaps_before_one_identity_retry(monkeypatch):
    from efren_bot.bridge.processes import terminate_owned

    class Owned:
        pid = 1000001
        polls = 0

        def poll(self):
            self.polls += 1
            return None if self.polls == 1 else 0

        def wait(self, timeout):
            return 0

    inspections = 0

    def transient(pid):
        nonlocal inspections
        inspections += 1
        if inspections == 1:
            raise RecoveryRequired("exit transition")
        return None

    monkeypatch.setattr("efren_bot.bridge.processes.process_identity", transient)
    monkeypatch.setattr("efren_bot.bridge.processes.group_alive", lambda pgid: False)
    monkeypatch.setattr(
        os, "killpg", lambda *a: pytest.fail("no signal after confirmed extinction")
    )
    terminate_owned(Owned(), {"pid": Owned.pid, "pgid": Owned.pid, "start": "own-start"})
    assert inspections == 2


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_metadata_probe_also_caps_streams_and_reaps(tmp_path, monkeypatch, stream):
    original = subprocess.Popen
    launched = []

    def launch(argv, **kwargs):
        assert argv == ["/synthetic/client", "--help"]
        code = (
            "import sys,time;time.sleep(.05);"
            f"sys.{stream}.write('x'*200000);sys.{stream}.flush();time.sleep(60)"
        )
        process = original([sys.executable, "-c", code], **kwargs)
        launched.append(process)
        return process

    monkeypatch.setattr("efren_bot.bridge.capability.subprocess.Popen", launch)
    with pytest.raises(ValueError, match="client metadata limit"):
        metadata_output("/synthetic/client", "--help", tmp_path)
    assert launched and launched[0].poll() is not None
    with pytest.raises(ProcessLookupError):
        os.killpg(launched[0].pid, 0)
