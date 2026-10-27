"""Create ONLY the bridge's own secret. No credential/configuration inspection."""

import os
import secrets
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BRIDGE_DIR = ROOT / ".local" / "bridge"


def initialize(directory=BRIDGE_DIR):
    directory = Path(directory)
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    for path in [directory, *directory.parents]:
        if path.is_symlink():
            raise ValueError("unsafe directory")
    info = directory.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError("unsafe directory")
    fd = os.open(directory / "token", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        os.write(fd, (secrets.token_hex(32) + "\n").encode("ascii"))
        os.fsync(fd)
    finally:
        os.close(fd)


def main():
    try:
        initialize()
    except (OSError, ValueError):
        raise SystemExit("bridge-init blocked: existing token or unsafe own directory") from None
    print("Bridge secret created; profile approval and policy verification remain required.")


if __name__ == "__main__":
    main()
