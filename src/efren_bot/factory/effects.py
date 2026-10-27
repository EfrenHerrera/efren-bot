"""Effects: the only way the factory touches the outside world, and always gated.

An effect is a *concrete, fingerprinted* action. A human approves a fingerprint, not a
sentence: if the payload changes, the approval no longer applies. ``merge`` and ``deploy`` do
not exist here on purpose.
"""

import hashlib
import json
import subprocess
from collections.abc import Callable
from typing import Any, Protocol

from efren_bot.factory.contracts import RunRecord

PROPOSABLE = ("open_pr", "update_notion", "post_slack")


def fingerprint(kind: str, payload: dict) -> str:
    canon = json.dumps([kind, payload], sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()


class EffectFailed(Exception):
    """The effect definitely did not happen."""


class EffectUncertain(Exception):
    """The effect may or may not have happened; never retried blindly."""


class EffectGateway(Protocol):
    def execute(self, kind: str, payload: dict, idempotency_key: str) -> dict: ...


class RecordingGateway:
    """Performs nothing; remembers everything. The default for every rehearsal."""

    def __init__(self, *, fail_kinds: set[str] | None = None):
        self.executed: list[tuple[str, dict, str]] = []
        self._fail = fail_kinds or set()

    def execute(self, kind: str, payload: dict, idempotency_key: str) -> dict:
        if kind in self._fail:
            raise EffectFailed(f"{kind} rejected by the recording gateway")
        if any(key == idempotency_key for _, _, key in self.executed):
            return {"status": "already_executed", "idempotency_key": idempotency_key}
        self.executed.append((kind, payload, idempotency_key))
        return {"status": "recorded", "idempotency_key": idempotency_key}


class GlabGateway:
    """Real ``open_pr`` through git + glab. Unverified against a live GitLab until the
    integration run on the connected machine; every other kind is refused explicitly.
    """

    def __init__(self, *, runner: Callable[..., subprocess.CompletedProcess] = subprocess.run):
        self._run = runner

    def execute(self, kind: str, payload: dict, idempotency_key: str) -> dict:
        if kind != "open_pr":
            raise EffectFailed(f"glab gateway does not perform {kind}")
        branch, base = payload["branch"], payload["base_ref"]
        worktree = payload["worktree"]
        push = self._run(
            ["git", "-C", worktree, "push", "--set-upstream", "origin", branch],
            capture_output=True,
            timeout=120,
        )
        if push.returncode:
            raise EffectFailed("push failed")
        try:
            created = self._run(
                [
                    "glab",
                    "mr",
                    "create",
                    "--source-branch",
                    branch,
                    "--target-branch",
                    base,
                    "--title",
                    payload["title"],
                    "--description",
                    payload["body"],
                    "--yes",
                ],
                capture_output=True,
                cwd=worktree,
                timeout=120,
            )
        except subprocess.TimeoutExpired as exc:
            raise EffectUncertain("merge request creation timed out") from exc
        if created.returncode:
            raise EffectUncertain("merge request creation did not confirm")
        return {"status": "created", "output": created.stdout.decode(errors="replace")[-500:]}


class NotionGateway:
    """Real ``update_notion`` through a NotionClient."""

    def __init__(self, client: Any):
        self._client = client

    def execute(self, kind: str, payload: dict, idempotency_key: str) -> dict:
        if kind != "update_notion":
            raise EffectFailed(f"notion gateway does not perform {kind}")
        try:
            return self._client.update_status(payload["page_id"], payload["status"])
        except Exception as exc:  # noqa: BLE001 - network outcome is unknowable here
            raise EffectUncertain("notion update did not confirm") from exc


class CompositeGateway:
    """Routes each effect kind to the gateway that owns it; unknown kinds are refused."""

    def __init__(self, routes: dict[str, EffectGateway]):
        self._routes = routes

    def execute(self, kind: str, payload: dict, idempotency_key: str) -> dict:
        gateway = self._routes.get(kind)
        if gateway is None:
            raise EffectFailed(f"no gateway is configured for {kind}")
        return gateway.execute(kind, payload, idempotency_key)


def title_of(brief: str, job_key: str) -> str:
    first = brief.strip().splitlines()[0] if brief.strip() else job_key
    return (first[:70] + "…") if len(first) > 70 else first


def build_effects(
    record: RunRecord,
    *,
    source_kind: str,
    source_ref: str,
    brief: str,
    job_key: str,
    repo_path: str,
) -> list[tuple[str, dict]]:
    """Effects worth proposing for this run. Nothing is proposed for a run that did not succeed."""
    if record.status != "succeeded":
        return []
    out: list[tuple[str, dict]] = []
    body = _body(record, source_kind, source_ref)
    if record.branch and record.head_sha:
        out.append(
            (
                "open_pr",
                {
                    "branch": record.branch,
                    "base_ref": record.base_ref,
                    "head_sha": record.head_sha,
                    "worktree": record.worktree,
                    "repo_path": repo_path,
                    "title": title_of(brief, job_key),
                    "body": body,
                },
            )
        )
    if source_kind == "notion":
        out.append(("update_notion", {"page_id": source_ref, "status": "In review"}))
    if source_kind == "slack":
        out.append(("post_slack", {"channel_message": source_ref, "text": _slack_text(record)}))
    return out


def _body(record: RunRecord, source_kind: str, source_ref: str) -> str:
    lines = [f"Source: {source_kind} {source_ref}", f"Run: {record.job_id}", ""]
    if record.risk:
        lines.append(f"Risk: {record.risk.tier} ({record.risk.changed_lines} lines)")
    for check in record.checks:
        lines.append(f"- {check.name}: {check.status}")
    if record.review and record.review.verdict:
        lines.append(f"Review: {record.review.verdict}")
    return "\n".join(lines)


def _slack_text(record: RunRecord) -> str:
    return f"Preparé un cambio en la rama {record.branch} ({record.head_sha[:8]})."
