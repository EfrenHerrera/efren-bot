"""Host-only reviewed native evidence. Not remote attestation or an account check."""

import hashlib
import hmac
import os
import pwd
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from efren_bot.bridge.contracts import canonical, strict_json
from efren_bot.bridge.policy import write_exclusive
from efren_bot.bridge.profile import load_token, own_file

PROOF = "policy-proof.json"
REVIEW = "policy-review.json"
CASES = {"allowed", "wrong_scope", "failures"}
SIGNATURE = (
    '=anchor apple generic and identifier "com.anthropic.claude-code" '
    'and certificate leaf[subject.OU] = "Q6L2SF6YDW"'
)


class EvidenceError(ValueError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def digest(data):
    return hashlib.sha256(canonical(data)).hexdigest()


def control_digest():
    # Also pins the receipt validator and native harness, not just hook source.
    root = Path(__file__).parent
    return digest(
        {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in (
                "capability.py",
                "policy.py",
                "profile.py",
                "proof.py",
                "runner.py",
                "supervisor.py",
                "verify.py",
                "verify_fixture.py",
                "contracts.py",
                "processes.py",
                "stream.py",
                "preflight.py",
                "init.py",
            )
        }
    )


def policy_absence():
    """Fixed policy paths only; never read credential/config contents or scan HOME."""
    if sys.platform != "darwin":
        raise EvidenceError("policy_platform_unsupported")
    user = pwd.getpwuid(os.getuid())
    system = Path("/Library/Application Support/ClaudeCode")
    managed = Path("/Library/Managed Preferences")
    paths = [
        system / "managed-settings.json",
        system / "managed-settings.d",
        system / "managed-mcp.json",
        managed / "com.anthropic.claudecode.plist",
        managed / user.pw_name / "com.anthropic.claudecode.plist",
        Path("/Library/Preferences/com.anthropic.claudecode.plist"),
        Path(user.pw_dir) / "Library/Preferences/com.anthropic.claudecode.plist",
        Path(user.pw_dir) / "Library/Managed Preferences/com.anthropic.claudecode.plist",
        Path(user.pw_dir) / ".claude/remote-settings.json",
    ]
    for path in paths:
        try:
            # Parent links could redirect a documented policy path.
            if any(parent.is_symlink() for parent in path.parents):
                raise EvidenceError("managed_policy_unreviewed")
            path.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise EvidenceError("managed_policy_unreviewed") from exc
        raise EvidenceError("managed_policy_unreviewed")
    return digest([str(path) for path in paths])


def review_state(profile, directory):
    try:
        data = strict_json(own_file(directory / REVIEW, host=True, maximum=16384))
    except FileNotFoundError as exc:
        raise EvidenceError("policy_review_missing") from exc
    except (OSError, ValueError) as exc:
        raise EvidenceError("policy_review_invalid") from exc
    if (
        set(data)
        != {
            "schema_version",
            "profile_fingerprint",
            "operator",
            "account_scope",
            "effective_managed_settings",
            "basis",
        }
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or data["profile_fingerprint"] != profile.fingerprint
        or data["account_scope"] != "personal_subscription"
        or type(data["effective_managed_settings"]) is not dict
        or data["effective_managed_settings"] != {}
        or any(
            type(data[key]) is not str
            or not 8 <= len(data[key].strip()) <= 2000
            or any(ord(c) < 32 for c in data[key])
            for key in ("operator", "basis")
        )
    ):
        raise EvidenceError("policy_review_invalid")
    return {"review_sha256": digest(data), "policy_paths_sha256": policy_absence()}


def identity(profile, directory):
    from efren_bot.bridge.capability import binary_digest
    from efren_bot.bridge.supervisor import settings_for

    # Developer identity observed on the officially updated binary. A fake CLI's
    # --version/help/native-looking JSON cannot replace Apple signature verification.
    if sys.platform != "darwin":
        raise EvidenceError("policy_platform_unsupported")
    result = subprocess.run(
        [
            "/usr/bin/codesign",
            "--verify",
            "--strict",
            "-R",
            SIGNATURE,
            str(Path(profile.cli.path).resolve(strict=True)),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=5,
        check=False,
        env={"PATH": "/usr/bin:/bin"},
    )
    if result.returncode != 0:
        raise EvidenceError("official_signature_unverified")
    cli_digest = binary_digest(Path(profile.cli.path))
    if cli_digest != profile.cli.verified_sha256:
        raise EvidenceError("policy_evidence_drift")
    return {
        "profile_fingerprint": profile.fingerprint,
        "cli_path": str(Path(profile.cli.path).resolve(strict=True)),
        "cli_version": profile.cli.verified_version,
        "cli_sha256": cli_digest,
        "python_path": str(Path(sys.executable).resolve(strict=True)),
        "python_sha256": binary_digest(Path(sys.executable)),
        "control_sha256": control_digest(),
        "settings_sha256": digest(
            settings_for(
                Path("/BRIDGE-RUN/policy.json"), "/BRIDGE-PYTHON", profile.connector.server_url
            )
        ),
        **review_state(profile, directory),
    }


def validate_observations(observations):
    if type(observations) is not dict or set(observations) != CASES:
        raise EvidenceError("native_probe_incomplete")
    for case, value in observations.items():
        expected = {"allowed": 5, "wrong_scope": 2, "failures": 5}[case]
        if (
            type(value) is not dict
            or set(value) != {"attempts", "executed", "hook_events", "native_init"}
            or type(value["attempts"]) is not int
            or value["attempts"] != expected
            or type(value["executed"]) is not int
            or value["executed"] != (5 if case == "allowed" else 0)
            or type(value["hook_events"]) is not int
            or value["hook_events"] < expected
            or value["native_init"] is not True
        ):
            raise EvidenceError("native_probe_incomplete")


def seal(profile, directory, observations, observed_identity):
    """Only the native command calls this after interactive digest review."""
    validate_observations(observations)
    if identity(profile, directory) != observed_identity:
        raise EvidenceError("policy_evidence_drift")
    now = datetime.now(UTC)
    payload = {
        "schema_version": 1,
        "identity": observed_identity,
        "observations": observations,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=24)).isoformat(),
    }
    key = load_token(directory / "token", host=True).encode("ascii")
    mac = hmac.new(key, canonical(payload), "sha256").hexdigest()
    write_exclusive(directory / PROOF, {"payload": payload, "mac": mac})


def verified_identity(profile, directory):
    try:
        data = strict_json(own_file(directory / PROOF, host=True, maximum=16384))
    except FileNotFoundError as exc:
        raise EvidenceError("policy_proof_missing") from exc
    except (OSError, ValueError) as exc:
        raise EvidenceError("policy_proof_invalid") from exc
    if set(data) != {"payload", "mac"} or type(data["mac"]) is not str:
        raise EvidenceError("policy_proof_invalid")
    key = load_token(directory / "token", host=True).encode("ascii")
    expected = hmac.new(key, canonical(data["payload"]), "sha256").hexdigest()
    if not hmac.compare_digest(data["mac"], expected):
        raise EvidenceError("policy_proof_invalid")
    payload = data["payload"]
    try:
        if (
            set(payload)
            != {"schema_version", "identity", "observations", "created_at", "expires_at"}
            or type(payload["schema_version"]) is not int
            or payload["schema_version"] != 1
        ):
            raise ValueError()
        created = datetime.fromisoformat(payload["created_at"])
        expires = datetime.fromisoformat(payload["expires_at"])
        now = datetime.now(UTC)
        if not created <= now < expires or expires - created > timedelta(hours=24):
            raise EvidenceError("policy_proof_stale")
        validate_observations(payload["observations"])
    except (ValueError, TypeError, KeyError) as exc:
        if isinstance(exc, EvidenceError):
            raise
        raise EvidenceError("policy_proof_invalid") from exc
    current = identity(profile, directory)
    if current != payload["identity"] or current["cli_sha256"] != profile.cli.verified_sha256:
        raise EvidenceError("policy_evidence_drift")
    return current
