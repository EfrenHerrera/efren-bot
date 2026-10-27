"""Short, globally serialized bridge transactions. No network/process operations."""

from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select, text

from efren_bot.bridge.contracts import BridgeRunView
from efren_bot.bridge.profile import ProfileError, load_profile, load_token
from efren_bot.models import BridgePresence, BridgeRun, utcnow

TERMINAL = {"succeeded", "failed", "cancelled"}


class BridgeError(Exception):
    def __init__(self, code, status=409):
        self.code, self.status = code, status
        super().__init__(code)


def view(run):
    return BridgeRunView.model_validate(
        {name: getattr(run, name) for name in BridgeRunView.model_fields}
    )


def finish(run, now, status, error=None, result=None):
    run.status, run.error_code, run.result = status, error, result
    run.finished_at = now


class BridgeService:
    def __init__(self, settings, sessions):
        self.settings, self.sessions = settings, sessions

    def token(self):
        try:
            return load_token(Path(self.settings.claude_bridge_token_file), host=False)
        except (OSError, ValueError):
            return None

    def profile(self):
        if not self.settings.claude_bridge_enabled:
            raise BridgeError("bridge_disabled", 503)
        try:
            return load_profile(Path(self.settings.claude_bridge_profile_file), host=False)
        except ProfileError as exc:
            raise BridgeError("bridge_not_configured", 503) from exc

    @contextmanager
    def transaction(self):
        with self.sessions.begin() as session:
            session.execute(text("SELECT pg_advisory_xact_lock(6283761201)"))
            now = utcnow()  # after acquiring lock, not request arrival time
            runs = session.scalars(
                select(BridgeRun)
                .where(BridgeRun.status.in_(["queued", "running"]))
                .with_for_update()
            ).all()
            for run in runs:
                lease_expired = run.status == "running" and run.lease_expires_at <= now
                if lease_expired or run.deadline_at <= now:
                    if run.cancel_requested:
                        finish(run, now, "cancelled")
                    else:
                        finish(
                            run,
                            now,
                            "failed",
                            "timeout" if run.deadline_at <= now else "interrupted",
                        )
            session.flush()
            yield session, now

    @staticmethod
    def ready(session, now, profile):
        presence = session.get(BridgePresence, 1)
        return bool(
            presence
            and presence.profile_fingerprint == profile.fingerprint
            and now - presence.seen_at <= timedelta(seconds=15)
        )

    def status(self):
        reason = "disabled"
        if self.settings.claude_bridge_enabled:
            if self.token() is None:
                reason = "token_unavailable"
            else:
                try:
                    profile = load_profile(
                        Path(self.settings.claude_bridge_profile_file), host=False
                    )
                except ProfileError as exc:
                    reason = exc.reason
                else:
                    with self.transaction() as (session, now):
                        reason = None if self.ready(session, now, profile) else "runner_unavailable"
        return {
            "mode": "manual_claude_slack",
            "enabled": self.settings.claude_bridge_enabled,
            "configuration": "disabled"
            if reason == "disabled"
            else "pending"
            if reason
            else "ready",
            "reason": reason,
        }

    def create(self, data):
        profile = self.profile()
        try:
            profile.arguments(data.requested_slack_permalink)
        except ValueError as exc:
            raise BridgeError("invalid_request", 422) from exc
        with self.transaction() as (session, now):
            if self.profile().fingerprint != profile.fingerprint:
                raise BridgeError("profile_mismatch")
            existing = session.scalar(
                select(BridgeRun).where(BridgeRun.idempotency_key == data.idempotency_key)
            )
            if existing:
                if (
                    existing.requested_slack_permalink != data.requested_slack_permalink
                    or existing.profile_fingerprint != profile.fingerprint
                ):
                    raise BridgeError("idempotency_conflict")
                return view(existing), False
            if not self.ready(session, now, profile):
                raise BridgeError("runner_unavailable", 503)
            run = BridgeRun(
                id=uuid4(),
                idempotency_key=data.idempotency_key,
                requested_slack_permalink=data.requested_slack_permalink,
                profile_id=profile.profile_id,
                profile_version=profile.profile_version,
                profile_fingerprint=profile.fingerprint,
                status="queued",
                cancel_requested=False,
                created_at=now,
                deadline_at=now + timedelta(seconds=profile.limits.run_timeout_seconds),
            )
            session.add(run)
            session.flush()
            return view(run), True

    @staticmethod
    def get_run(session, run_id):
        run = session.get(BridgeRun, run_id, with_for_update=True)
        if run is None:
            raise BridgeError("run_not_found", 404)
        return run

    def read(self, run_id, *, cancel=False):
        with self.transaction() as (session, now):
            run = self.get_run(session, run_id)
            if cancel and run.status not in TERMINAL:
                run.cancel_requested = True
                if run.status == "queued":
                    finish(run, now, "cancelled")
            return view(run)

    def claim(self, data):
        profile = self.profile()
        if data.profile_fingerprint != profile.fingerprint:
            raise BridgeError("profile_mismatch")
        if (
            data.cli_version != profile.cli.verified_version
            or data.cli_sha256 != profile.cli.verified_sha256
            or not data.policy_verified
        ):
            raise BridgeError("capability_unavailable")
        with self.transaction() as (session, now):
            if self.profile().fingerprint != profile.fingerprint:
                raise BridgeError("profile_mismatch")
            presence = session.get(BridgePresence, 1)
            if presence is None:
                presence = BridgePresence(id=1)
                session.add(presence)
            presence.runner_id, presence.seen_at = data.runner_id, now
            presence.profile_fingerprint = profile.fingerprint
            if session.scalar(select(BridgeRun.id).where(BridgeRun.status == "running")):
                return None
            queued = session.scalars(
                select(BridgeRun)
                .where(BridgeRun.status == "queued")
                .order_by(BridgeRun.created_at, BridgeRun.id)
                .with_for_update()
            ).all()
            for run in queued:
                if run.profile_fingerprint != profile.fingerprint:
                    finish(run, now, "failed", "profile_mismatch")
                    continue
                run.status, run.runner_id, run.lease_token = "running", data.runner_id, uuid4()
                run.started_at = now
                run.lease_expires_at = min(now + timedelta(seconds=15), run.deadline_at)
                return {
                    "run": view(run),
                    "lease_token": run.lease_token,
                    "lease_expires_at": run.lease_expires_at,
                }
            return None

    def lease(self, run_id, data, *, complete=False):
        profile = self.profile()  # re-read independently, outside DB transaction
        error = None
        result = None
        with self.transaction() as (session, now):
            run = self.get_run(session, run_id)
            if run.runner_id != data.runner_id or run.lease_token != data.lease_token:
                error = BridgeError("lease_lost")
            elif run.status in TERMINAL:
                error = BridgeError("run_terminal")
            elif (
                data.profile_fingerprint != profile.fingerprint
                or run.profile_fingerprint != profile.fingerprint
                or self.profile().fingerprint != profile.fingerprint
            ):
                error = BridgeError("profile_mismatch")
            elif complete:
                if data.result is not None:
                    try:
                        data.result.for_run(
                            run.requested_slack_permalink, profile.limits.max_result_bytes
                        )
                    except ValueError as exc:
                        raise BridgeError("invalid_result", 422) from exc
                if run.cancel_requested:
                    finish(run, now, "cancelled")
                else:
                    finish(
                        run,
                        now,
                        data.outcome,
                        data.error_code,
                        data.result.model_dump(mode="json") if data.result else None,
                    )
                result = {"run": view(run)}
            else:
                run.lease_expires_at = min(now + timedelta(seconds=15), run.deadline_at)
                # An active runner is also fresh presence; no synthetic ready from config.
                presence = session.get(BridgePresence, 1)
                if presence and presence.runner_id == data.runner_id:
                    presence.seen_at = now
                result = {
                    "cancel_requested": run.cancel_requested,
                    "lease_expires_at": run.lease_expires_at,
                    "deadline_at": run.deadline_at,
                }
        # Reconciliation must commit even when the expired caller receives a conflict.
        if error:
            raise error
        return result
