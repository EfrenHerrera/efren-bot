"""Shared builders for factory tests: projects, items, run records."""

from datetime import UTC, datetime

from efren_bot.factory.contracts import RunRecord
from efren_bot.factory.intake import IntakeItem
from efren_bot.factory.profiles import ProfileRegistry
from efren_bot.factory.projects import Project, ProjectRegistry
from efren_bot.factory.triage import AdmissionPolicy

POLICY = AdmissionPolicy.load()
PROFILES = ProfileRegistry.load()


def projects(tmp_path="/tmp/none") -> ProjectRegistry:
    return ProjectRegistry(
        [
            Project(
                name="landing",
                profile="frontend",
                repo_path=str(tmp_path),
                keywords=["landing", "pricing page", "botón", "boton"],
                notion_projects=["Landing Web"],
                slack_channels=["web-team"],
            ),
            Project(
                name="payments-orchestrator",
                profile="orchestrator-multirepo",
                repo_path=str(tmp_path),
                keywords=["orquestador", "orchestrator", "temporal", "kafka"],
                notion_projects=["Payments"],
            ),
            Project(
                name="etl-lambdas",
                profile="lambdas",
                repo_path=str(tmp_path),
                keywords=["lambda", "etl"],
            ),
        ]
    )


def item(
    source="notion", text="Cambiar el botón de la landing a verde", external_id="ext-1", **attrs
) -> IntakeItem:
    base = {"ready": True, "status": "Ready", "human_flagged": True}
    base.update(attrs)
    return IntakeItem(
        source_kind=source,
        external_id=external_id,
        title=text[:40],
        text=text,
        occurred_at=datetime(2026, 10, 27, 12, 0, tzinfo=UTC),
        attrs=base,
    )


def record(spec, **overrides) -> RunRecord:
    """A succeeded, passive, auto-PR run record for a job spec (what scraft-ops would return)."""
    base = {
        "schema": "scraft.factory.run/1",
        "job_id": spec.job_id,
        "profile": spec.profile,
        "role": spec.role,
        "status": "succeeded",
        "executor": "fake",
        "branch": f"factory/{spec.job_id}",
        "worktree": f"/tmp/wt/{spec.job_id}",
        "base_ref": spec.repo.base_ref,
        "head_sha": "a" * 40,
        "checks": [{"name": "test", "status": "pass", "mandatory": True}],
        "risk": {"tier": "passive", "review_mode": "direct", "changed_files": ["a.txt"]},
        "requires_human": False,
        "effects": [
            {"kind": "open_pr", "policy": "auto"},
            {"kind": "update_notion", "policy": "human"},
            {"kind": "post_slack", "policy": "human"},
            {"kind": "merge", "policy": "forbidden"},
            {"kind": "deploy", "policy": "forbidden"},
        ],
    }
    base.update(overrides)
    return RunRecord.model_validate(base)
