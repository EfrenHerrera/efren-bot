"""Admission criteria: deterministic, versioned and explainable.

Triage turns an ``IntakeItem`` into one of four decisions and always says why:

- ``admit``        it is work, the project and role are known, nothing needs a person first
- ``ask_context``  it looks like work but something required is missing or ambiguous
- ``inbox``        a person must decide whether this is admitted (sensitive or changed)
- ``discard``      not a request, duplicate, or explicitly not ready

No model is involved: a funnel that guesses cannot be audited. A model may later *propose*
into the inbox, never admit on its own.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from efren_bot.factory.intake import IntakeItem, normalize_text
from efren_bot.factory.profiles import ProfileRegistry
from efren_bot.factory.projects import Project, ProjectRegistry

POLICY_PATH = Path(__file__).parent / "policy.json"


@dataclass(frozen=True)
class AdmissionPolicy:
    version: str
    min_text_chars: int
    work_markers: tuple[str, ...]
    information_markers: tuple[str, ...]
    human_admission_markers: tuple[str, ...]
    role_markers: dict[str, tuple[str, ...]]
    source_rules: dict[str, dict]

    @classmethod
    def load(cls, path: str | Path = POLICY_PATH) -> "AdmissionPolicy":
        data = json.loads(Path(path).read_text())
        return cls(
            version=data["version"],
            min_text_chars=int(data["min_text_chars"]),
            work_markers=tuple(data["work_markers"]),
            information_markers=tuple(data["information_markers"]),
            human_admission_markers=tuple(data["human_admission_markers"]),
            role_markers={k: tuple(v) for k, v in data["role_markers"].items()},
            source_rules=dict(data["source_rules"]),
        )


@dataclass
class Admission:
    decision: str  # admit | ask_context | inbox | discard
    reasons: list[str] = field(default_factory=list)
    project: str | None = None
    profile: str | None = None
    role: str | None = None
    policy_version: str = ""


@dataclass(frozen=True)
class PriorVersion:
    """What the plant already knows about an earlier version of the same external item."""

    admitted: bool


def _has(text: str, markers: tuple[str, ...]) -> list[str]:
    return [m for m in markers if m in text]


def _word_hit(text: str, marker: str) -> bool:
    # Short markers like "ok" must match whole words, not substrings of other words.
    if len(marker) > 3 or not marker.isalpha():
        return marker in text
    return f" {marker} " in f" {text} "


def resolve_project(
    item: IntakeItem, projects: ProjectRegistry, text: str
) -> tuple[Project | None, str]:
    """Explicit hints first; declared keywords second; ambiguity is never guessed away."""
    hint = item.attrs.get("project_hint")
    if hint:
        match = projects.get(hint) or next(
            (p for p in projects.projects if hint in p.notion_projects), None
        )
        if match:
            return match, f"project from explicit hint {hint!r}"
        return None, f"project hint {hint!r} matches no registered project"
    channel = item.attrs.get("channel")
    if channel:
        by_channel = [p for p in projects.projects if channel in p.slack_channels]
        if len(by_channel) == 1:
            return by_channel[0], f"project from Slack channel {channel!r}"
    hits = [p for p in projects.projects if any(k.lower() in text for k in p.keywords)]
    if len(hits) == 1:
        return hits[0], f"project from keywords of {hits[0].name!r}"
    if len(hits) > 1:
        return None, "ambiguous project: " + ", ".join(sorted(p.name for p in hits))
    return None, "no registered project matches this request"


def pick_role(text: str, policy: AdmissionPolicy) -> str:
    for role in ("review", "research", "support"):
        if _has(text, policy.role_markers.get(role, ())):
            return role
    return "development"


def triage(
    item: IntakeItem,
    *,
    policy: AdmissionPolicy,
    projects: ProjectRegistry,
    profiles: ProfileRegistry,
    prior: PriorVersion | None = None,
) -> Admission:
    result = Admission(decision="discard", policy_version=policy.version)
    text = normalize_text(item.text)
    rules = policy.source_rules.get(item.source_kind, {})

    if rules.get("require_human_flag") and not item.attrs.get("human_flagged"):
        result.reasons.append("not flagged by a person as requiring attention")
        return result
    if rules.get("require_ready") and not item.attrs.get("ready"):
        result.reasons.append(f"task status {item.attrs.get('status')!r} is not ready")
        return result

    markers = [m for m in policy.work_markers if _word_hit(text, m)]
    always_work = bool(rules.get("always_work"))
    if rules.get("require_work_marker") and not markers:
        result.reasons.append("no work request marker in the message")
        return result
    if not always_work and not rules.get("require_human_flag"):
        informational = [m for m in policy.information_markers if _word_hit(text, m)]
        if informational and not markers:
            result.reasons.append("informational message, not a request")
            return result
    if not (always_work or markers or item.attrs.get("human_flagged")):
        result.decision = "inbox"
        result.reasons.append("unclear whether this is a request; a person decides")
        return result

    if len(text) < policy.min_text_chars:
        result.decision = "ask_context"
        result.reasons.append("request is too short to act on")
        return result

    project, why = resolve_project(item, projects, text)
    result.reasons.append(why)
    if project is None:
        result.decision = "ask_context"
        return result
    profile = profiles.get(project.profile)
    if profile is None:
        result.decision = "ask_context"
        result.reasons.append(f"project {project.name!r} uses unknown profile {project.profile!r}")
        return result
    result.project, result.profile = project.name, profile.name
    result.role = pick_role(text, policy)

    if prior is not None and prior.admitted:
        result.decision = "inbox"
        result.reasons.append("changed after it was already admitted; a person decides")
        return result
    sensitive = [m for m in policy.human_admission_markers if _word_hit(text, m)]
    if sensitive:
        result.decision = "inbox"
        result.reasons.append("sensitive wording needs a person first: " + ", ".join(sensitive))
        return result

    result.decision = "admit"
    result.reasons.append(f"work request (role {result.role})")
    return result
