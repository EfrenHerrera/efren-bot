"""Project registry: which repository, which profile, which words.

Loaded from an explicit JSON file (``FACTORY_PROJECTS_FILE``). Nothing is discovered from
the filesystem and nothing is inferred from a message: a request resolves to a project only
through an explicit hint or through the project's own declared keywords.
"""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from efren_bot.factory.contracts import FallbackExecutor, JobPolicy


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    profile: str
    repo_path: str
    base_ref: str = "main"
    keywords: list[str] = Field(default_factory=list)
    notion_projects: list[str] = Field(default_factory=list)
    slack_channels: list[str] = Field(default_factory=list)
    executor: str = ""
    fallback_executors: list[FallbackExecutor] = Field(default_factory=list, max_length=1)
    model: str = ""
    effort: str = ""

    @model_validator(mode="after")
    def valid_execution_policy(self):
        JobPolicy(
            executor=self.executor,
            fallback_executors=self.fallback_executors,
            model=self.model,
            effort=self.effort,
        )
        return self


class ProjectRegistry:
    def __init__(self, projects: list[Project]):
        names = [p.name for p in projects]
        if len(names) != len(set(names)):
            raise ValueError("duplicate project names")
        self.projects = projects

    @classmethod
    def load(cls, path: str | Path) -> "ProjectRegistry":
        data = json.loads(Path(path).read_text())
        return cls([Project.model_validate(p) for p in data.get("projects", [])])

    def get(self, name: str) -> Project | None:
        return next((p for p in self.projects if p.name == name), None)
