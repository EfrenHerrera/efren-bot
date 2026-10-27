"""Fail before Compose can create missing bind sources. Does not approve a profile."""

from efren_bot.bridge.init import BRIDGE_DIR
from efren_bot.bridge.profile import ProfileError, load_profile, load_token
from efren_bot.bridge.proof import EvidenceError, verified_identity


def main():
    try:
        load_token(BRIDGE_DIR / "token", host=True)
    except (ValueError, OSError):
        raise SystemExit("bridge-up blocked: token_unavailable") from None
    try:
        profile = load_profile(BRIDGE_DIR / "profile.json", host=True)
        verified_identity(profile, BRIDGE_DIR)
    except (ProfileError, EvidenceError) as exc:
        raise SystemExit("bridge-up blocked: " + exc.reason) from None
    except (ValueError, OSError):
        raise SystemExit("bridge-up blocked: configuration_unavailable") from None


if __name__ == "__main__":
    main()
