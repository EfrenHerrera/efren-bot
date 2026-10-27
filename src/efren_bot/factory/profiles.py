"""Project profiles: the axis that says how *this kind* of project is worked on.

The execution unit (scraft-ops) owns the checks and risk rules; the plant only needs
the matching hints to route a request to a profile. Both read the same JSON shape.
"""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

PROFILE_SCHEMA = "scraft.factory.profile/1"
DEFAULT_DIR = Path(__file__).parent / "profiles"


class ProfileMatch(BaseModel):
    model_config = ConfigDict(extra="ignore")
    keywords: list[str] = Field(default_factory=list)
    repos: list[str] = Field(default_factory=list)


class Profile(BaseModel):
    model_config = ConfigDict(extra="ignore")
    schema_: str = Field(alias="schema")
    name: str
    kind: str = ""
    topology: str = "single-repo"
    description: str = ""
    match: ProfileMatch = Field(default_factory=ProfileMatch)
    effects: dict[str, str] = Field(default_factory=dict)
    concurrency: int = 1
    executor: str = ""


class ProfileRegistry:
    def __init__(self, profiles: dict[str, Profile]):
        self._profiles = profiles

    @classmethod
    def load(cls, *dirs: Path | str) -> "ProfileRegistry":
        """Later directories override earlier ones, mirroring ``scraft-ops --profile-dir``."""
        profiles: dict[str, Profile] = {}
        for directory in (DEFAULT_DIR, *map(Path, dirs)):
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.json")):
                profile = Profile.model_validate(json.loads(path.read_text()))
                if profile.schema_ != PROFILE_SCHEMA:
                    raise ValueError(f"{path.name}: unsupported profile schema")
                profiles[profile.name] = profile
        return cls(profiles)

    def get(self, name: str) -> Profile | None:
        return self._profiles.get(name)

    def names(self) -> list[str]:
        return sorted(self._profiles)
