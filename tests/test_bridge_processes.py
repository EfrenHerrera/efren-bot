"""Exit-transition regressions; synthetic identities never reach OS signalling."""

import errno
import os
import subprocess
import sys
import time
from uuid import uuid4

import pytest

from efren_bot.bridge import processes
from efren_bot.bridge.processes import HostLock, RecoveryRequired, terminate_owned

IDENTITY = {"pid": 1000001, "pgid": 1000001, "start": "own-start"}


class ExitingChild:
    pid = IDENTITY["pid"]

    def __init__(self, *, timeout=False):
        self.returncode = None
        self.waits = []
        self.timeout = timeout

    def poll(self):
        return self.returncode

    def wait(self, timeout):
        self.waits.append(timeout)
        if self.timeout:
            raise subprocess.TimeoutExpired("own-child", timeout)
        self.returncode = 0
        return 0


@pytest.mark.parametrize("after_reap", ["absent", "reused", "unknown"])
def test_exit_transition_waits_for_own_child_before_identity_retry(monkeypatch, after_reap):
    child = ExitingChild()
    inspections = []

    def inspect(pid):
        assert pid == child.pid
        inspections.append(child.returncode)
        if child.returncode is None or after_reap == "unknown":
            raise RecoveryRequired("process identity uncertain")
        return None if after_reap == "absent" else {**IDENTITY, "start": "reused"}

    monkeypatch.setattr(processes, "process_identity", inspect)
    monkeypatch.setattr(processes, "group_alive", lambda pgid: False)
    monkeypatch.setattr(os, "killpg", lambda *a: pytest.fail("must not signal"))
    if after_reap == "absent":
        terminate_owned(child, IDENTITY)
    else:
        message = "PID reused" if after_reap == "reused" else "uncertain"
        with pytest.raises(RecoveryRequired, match=message):
            terminate_owned(child, IDENTITY)
    assert inspections == [None, 0]
    assert child.waits and all(timeout == 2 for timeout in child.waits)


def test_unknown_live_child_wait_is_bounded_and_preserves_journal(tmp_path, monkeypatch):
    child = ExitingChild(timeout=True)
    tmp_path.chmod(0o700)

    def unknown(pid):
        raise RecoveryRequired("process identity uncertain")

    monkeypatch.setattr(processes, "process_identity", unknown)
    monkeypatch.setattr(os, "killpg", lambda *a: pytest.fail("must not signal unknown group"))
    with HostLock(tmp_path) as lock:
        run_id = uuid4()
        lock.launching(run_id)
        lock.running(run_id, IDENTITY)
        before = lock.journal.read_bytes()
        with pytest.raises(RecoveryRequired, match="uncertain"):
            terminate_owned(child, IDENTITY)
        assert lock.journal.read_bytes() == before
    assert child.waits == [2]
    with pytest.raises(RecoveryRequired), HostLock(tmp_path):
        pytest.fail("uncertain journal must fence the next runner")
    assert (tmp_path / "active.json").read_bytes() == before


def test_killpg_permission_error_never_means_extinction(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    child = ExitingChild()
    child.returncode = 0
    calls = []

    def denied(pgid, sig):
        assert pgid == IDENTITY["pgid"]
        calls.append(sig)
        raise PermissionError(errno.EPERM, "not evidence of absence")

    monkeypatch.setattr(os, "killpg", denied)
    monkeypatch.setattr(processes, "process_identity", lambda pid: None)
    with HostLock(tmp_path) as lock:
        run_id = uuid4()
        lock.launching(run_id)
        lock.running(run_id, IDENTITY)
        with pytest.raises(RecoveryRequired, match="uncertain"):
            terminate_owned(child, IDENTITY)
        assert lock.journal.exists()
    with pytest.raises(RecoveryRequired), HostLock(tmp_path):
        pytest.fail("EPERM must fence recovery")
    assert calls == [0, 0]


def test_signal_permission_error_is_not_ignored(monkeypatch):
    child = ExitingChild()
    calls = []

    def denied(pgid, sig):
        calls.append((pgid, sig))
        raise PermissionError(errno.EPERM, "signal blocked")

    monkeypatch.setattr(processes, "process_identity", lambda pid: IDENTITY)
    monkeypatch.setattr(processes, "group_alive", lambda pgid: True)
    monkeypatch.setattr(os, "killpg", denied)
    with pytest.raises(PermissionError):
        terminate_owned(child, IDENTITY)
    assert calls == [(child.pid, processes.signal.SIGTERM)]


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS exit transition regression")
def test_macos_real_owned_exit_transition_reaps_and_confirms_group():
    for _ in range(8):
        child = subprocess.Popen(
            [sys.executable, "-c", "import sys;sys.stdin.buffer.read(1)"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env={"PATH": "/usr/bin:/bin"},
        )
        try:
            identity = processes.process_identity(child.pid)
            assert identity and identity["pgid"] == child.pid
            child.stdin.write(b"x")
            child.stdin.close()
            deadline = time.monotonic() + 2
            while child.poll() is None and time.monotonic() < deadline:
                try:
                    processes.process_identity(child.pid)
                except RecoveryRequired:
                    break  # inspect while exiting, not only after waitpid can reap
            terminate_owned(child, identity)
            assert child.returncode is not None
            assert processes.process_identity(child.pid) is None
            assert not processes.group_alive(child.pid)
        finally:
            # Only this Popen's own unreaped child, even when the assertion fails.
            if child.poll() is None:
                child.kill()
            child.wait(timeout=2)
