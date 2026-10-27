"""One host runner; durable launch journal; never kill an unknown/reused PID."""

import ctypes
import errno
import fcntl
import os
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

from efren_bot.bridge.contracts import canonical, strict_json
from efren_bot.bridge.policy import write_exclusive
from efren_bot.bridge.profile import own_file


class RecoveryRequired(RuntimeError):
    pass


def group_alive(pgid):
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError as exc:
        raise RecoveryRequired("process identity uncertain") from exc


def process_identity(pid):
    """Kernel start identity, not ps's second-resolution time or a guessed PID."""
    if sys.platform == "darwin":

        class BSDInfo(ctypes.Structure):
            _fields_ = (
                [
                    (name, ctypes.c_uint32)
                    for name in (
                        "flags status xstatus pid ppid uid gid ruid rgid svuid svgid rfu".split()
                    )
                ]
                + [("comm", ctypes.c_char * 16), ("name", ctypes.c_char * 32)]
                + [
                    (name, ctypes.c_uint32)
                    for name in "nfiles pgid pjobc e_tdev e_tpgid nice".split()
                ]
                + [("start_sec", ctypes.c_uint64), ("start_usec", ctypes.c_uint64)]
            )

        library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        library.proc_pidinfo.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint64,
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        library.proc_pidinfo.restype = ctypes.c_int
        info = BSDInfo()
        size = library.proc_pidinfo(pid, 3, 0, ctypes.byref(info), ctypes.sizeof(info))
        if size == ctypes.sizeof(info) and info.pid == pid and info.uid == os.getuid():
            return {
                "pid": pid,
                "pgid": info.pgid,
                "start": f"darwin:{info.start_sec}:{info.start_usec}",
            }
        if ctypes.get_errno() not in {0, errno.ESRCH, errno.ENOENT}:
            raise RecoveryRequired("process identity uncertain")
    elif sys.platform.startswith("linux"):
        try:
            data = Path(f"/proc/{pid}/stat").read_text()
            fields = data[data.rfind(")") + 2 :].split()
            boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
            if Path(f"/proc/{pid}").stat().st_uid != os.getuid():
                raise RecoveryRequired("process identity uncertain")
            return {"pid": pid, "pgid": int(fields[2]), "start": f"linux:{boot}:{fields[19]}"}
        except FileNotFoundError:
            return None
    else:
        raise RecoveryRequired("unsupported process identity")
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    raise RecoveryRequired("process identity uncertain")


def checked_directory(directory):
    if not directory.is_absolute() or any(p.is_symlink() for p in [directory, *directory.parents]):
        raise RecoveryRequired("unsafe operational directory")
    info = directory.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RecoveryRequired("unsafe operational directory")


class HostLock:
    def __init__(self, directory):
        self.directory = directory
        self.journal = directory / "active.json"
        self.fd = None

    def __enter__(self):
        checked_directory(self.directory)
        fd = os.open(self.directory / "runner.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        self.fd = fd
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
            ):
                raise RecoveryRequired("unsafe lock")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.recover()
            return self
        except Exception:
            os.close(fd)
            self.fd = None
            raise

    def __exit__(self, *args):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def sync(self):
        fd = os.open(self.directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def recover(self):
        if not self.journal.exists() and not self.journal.is_symlink():
            return
        try:
            data = strict_json(own_file(self.journal, host=True, maximum=1024))
            if set(data) != {"state", "run_id", "identity"} or data["state"] != "running":
                raise RecoveryRequired("launch outcome uncertain")
            identity = data["identity"]
            if (
                type(identity) is not dict
                or set(identity) != {"pid", "pgid", "start"}
                or type(identity["pid"]) is not int
                or identity["pid"] <= 1
                or type(identity["pgid"]) is not int
                or identity["pgid"] != identity["pid"]
                or type(identity["start"]) is not str
            ):
                raise RecoveryRequired("process identity uncertain")
            # Existing PID (even matching) or live group => manual recovery. In
            # particular a reused PID is NEVER signalled or silently discarded.
            if process_identity(identity["pid"]) is not None or group_alive(identity["pgid"]):
                raise RecoveryRequired("previous group not confirmed extinct")
            self.clear()
        except (ValueError, OSError, KeyError, TypeError) as exc:
            raise RecoveryRequired("invalid launch journal") from exc

    def launching(self, run_id):
        write_exclusive(
            self.journal, {"state": "launching", "run_id": str(run_id), "identity": None}
        )
        self.sync()  # durable BEFORE Popen; crash in launch gap blocks future claims

    def running(self, run_id, identity):
        fd = os.open(self.journal, os.O_WRONLY | os.O_NOFOLLOW)
        try:
            os.ftruncate(fd, 0)
            os.write(
                fd, canonical({"state": "running", "run_id": str(run_id), "identity": identity})
            )
            os.fsync(fd)
        finally:
            os.close(fd)

    def clear(self):
        self.journal.unlink()
        self.sync()


def terminate_owned(process, identity):
    # Reap our own already-exited child before inspecting the PID. macOS may not
    # expose proc_pidinfo before waitpid(WNOHANG) can reap it. On uncertainty,
    # wait boundedly for ONLY this Popen child, without signalling an unknown PID.
    # Reaping alone is not extinction: reinspect PID identity and the group below.
    process.poll()
    try:
        current = process_identity(process.pid)
    except RecoveryRequired as exc:
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            raise exc from None
        current = process_identity(process.pid)
    if current is not None and current != identity:
        raise RecoveryRequired("PID reused; manual recovery required")
    if identity["pgid"] != process.pid:
        raise RecoveryRequired("not an owned group")
    pgid = identity["pgid"]
    if group_alive(pgid):
        os.killpg(pgid, signal.SIGTERM)
    limit = time.monotonic() + 2
    while process.poll() is None and time.monotonic() < limit:
        time.sleep(0.02)
    if group_alive(pgid):
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=2)
    # Reaping the leader is not evidence that descendants are gone.
    limit = time.monotonic() + 2
    while group_alive(pgid) and time.monotonic() < limit:
        time.sleep(0.02)
    if group_alive(pgid):
        raise RecoveryRequired("group extinction uncertain")
