"""Closed host GitLab reader. Destinations never come from model-generated endpoints."""

import hashlib
import json
import re
import subprocess
from pathlib import PurePosixPath
from urllib.parse import quote, urlencode, urlsplit

from efren_bot.support.model import redact

PROJECTS = {
    "konfio/organization/guilds/core/core": "40652545",
    "konfio/organization/scope/p01/contexts/c01/domains/web/konfio-app-web": "64374983",
}
URL = re.compile(r"https://gitlab\.com/[^\s<>|\"']+/-/merge_requests/[0-9]+")
SHA = re.compile(r"[0-9a-f]{40}")
MAX_CALLS = 60


class GitlabError(Exception):
    pass


def parse_url(value):
    url = urlsplit(value)
    match = re.fullmatch(r"/([a-zA-Z0-9_./-]+)/-/merge_requests/([1-9][0-9]{0,11})", url.path)
    if (
        url.scheme != "https"
        or url.netloc != "gitlab.com"
        or url.query
        or url.fragment
        or not match
        or any(p in {".", "..", ""} for p in match[1].split("/"))
    ):
        raise ValueError("invalid MR URL")
    return match[1], match[2]


def links(text):
    result = []
    for value in URL.findall(text):
        try:
            project, iid = parse_url(value)
        except ValueError:
            continue
        canonical = f"https://gitlab.com/{project}/-/merge_requests/{iid}"
        if canonical not in result:
            result.append(canonical)
    return result


def validate_path(path):
    value = PurePosixPath(path)
    if (
        len(path) > 500
        or value.is_absolute()
        or ".." in value.parts
        or "\\" in path
        or any(ord(char) < 32 for char in path)
        or "%" in path
        or "\x00" in path
        or path != str(value)
    ):
        raise ValueError("invalid source path")
    fixed = {
        "AGENTS.md",
        "CLAUDE.md",
        ".ath/rules.md",
        ".gitlab-ci.yml",
        ".claude/skills/review-commit-project-rules/SKILL.md",
        "Makefile",
        "package.json",
        "pyproject.toml",
        "ruff.toml",
        "tsconfig.json",
    }
    if path in fixed:
        return
    if (
        value.parts[0] not in {"core", "tests", "factories", "apps", "packages", "docs"}
        or any(p.startswith(".") for p in value.parts)
        or value.suffix
        not in {
            ".py",
            ".ts",
            ".tsx",
            ".js",
            ".jsx",
            ".json",
            ".md",
            ".rst",
            ".yml",
            ".yaml",
            ".toml",
            ".sql",
            ".css",
            ".scss",
        }
        or value.name.lower() in {"credentials.json", "secrets.json", "auth.json"}
    ):
        raise ValueError("source path outside scope")


def added_lines(diff):
    new = 0
    result = []
    for line in diff.splitlines():
        match = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", line)
        if match:
            new = int(match[1])
        elif line.startswith("+") and not line.startswith("+++"):
            result.append(new)
            new += 1
        elif not line.startswith(("-", "\\")):
            new += 1
    return result


def source(sources, kind, text, **metadata):
    identifier = f"s{len(sources) + 1}"
    sources.append({"id": identifier, "kind": kind, "text": redact(text), **metadata})
    return identifier


class Gitlab:
    def __init__(self, project, iid):
        if project not in PROJECTS or not re.fullmatch(r"[1-9][0-9]{0,11}", iid):
            raise ValueError("project not approved")
        self.project, self.iid = project, iid
        self.prefix = f"projects/{PROJECTS[project]}"
        self.root = f"{self.prefix}/merge_requests/{iid}"
        self.calls = 0

    def _get(self, suffix):
        if getattr(self, "before_read", None):
            self.before_read()
        self.calls += 1
        if self.calls > MAX_CALLS:
            raise GitlabError("gitlab_read_budget")
        args = ["glab", "api", "--hostname", "gitlab.com", "--method", "GET", suffix]
        try:
            process = subprocess.run(args, capture_output=True, timeout=45)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise GitlabError("gitlab_read_failed") from error
        if process.returncode or len(process.stdout) > 4000000:
            raise GitlabError("gitlab_read_failed")
        return process.stdout

    def get(self, path):
        try:
            return json.loads(self._get(path))
        except ValueError as error:
            raise GitlabError("gitlab_invalid_json") from error

    def metadata(self):
        return self.get(self.root)

    def file(self, path, sha, *, start=1, end=None):
        validate_path(path)
        if not SHA.fullmatch(sha):
            raise ValueError("invalid immutable ref")
        if start < 1 or (end is not None and (end < start or end - start > 500)):
            raise ValueError("invalid source range")
        body = self._get(
            f"{self.prefix}/repository/files/{quote(path, safe='')}/raw?" + urlencode({"ref": sha})
        )
        if end is not None:
            body = b"\n".join(body.splitlines()[start - 1 : end])
        if len(body) > 60000 or b"\x00" in body:
            raise GitlabError("source_file_budget")
        return body.decode("utf-8")

    def capture(self):
        mr = self.metadata()
        refs = mr.get("diff_refs")
        if not refs or any(
            not SHA.fullmatch(str(refs.get(k, ""))) for k in ("head_sha", "base_sha", "start_sha")
        ):
            raise GitlabError("gitlab_diff_not_ready")
        versions = self.get(self.root + "/versions?per_page=100")
        version = next(
            (
                v
                for v in versions
                if all(
                    v.get(f"{side}_commit_sha") == refs[f"{side}_sha"]
                    for side in ("head", "base", "start")
                )
            ),
            None,
        )
        if version is None:
            raise GitlabError("gitlab_version_missing")
        data = self.get(self.root + f"/versions/{version['id']}")
        if any(
            data.get(f"{side}_commit_sha") != refs[f"{side}_sha"]
            for side in ("head", "base", "start")
        ):
            raise GitlabError("gitlab_version_changed")
        limitations, sources, diffs = [], [], []
        budget = 95000
        if data.get("state") != "collected" or data.get("overflow"):
            limitations.append("Diff no disponible por completo en GitLab.")
        for d in data.get("diffs", []):
            try:
                validate_path(d["new_path"])
                validate_path(d["old_path"])
            except ValueError:
                limitations.append("Diff fuera del alcance de archivos: " + d["new_path"])
                diffs.append(
                    {
                        "path": d["new_path"],
                        "old_path": d["old_path"],
                        "deleted": d["deleted_file"],
                        "added_lines": [],
                    }
                )
                continue
            text = d.get("diff", "")
            if d.get("too_large") or d.get("collapsed") or not text:
                limitations.append("Diff omitido: " + d["new_path"])
            excerpt = text[: max(0, budget)]
            budget -= len(excerpt)
            if excerpt != text:
                limitations.append("Presupuesto de diff agotado: " + d["new_path"])
            diffs.append(
                {
                    "path": d["new_path"],
                    "old_path": d["old_path"],
                    "deleted": d["deleted_file"],
                    "added_lines": added_lines(excerpt),
                }
            )
            if excerpt:
                source(sources, "diff", excerpt, path=d["new_path"], sha=refs["head_sha"])
        expected = str(mr.get("changes_count", ""))
        if expected.isdigit() and int(expected) != len(diffs):
            limitations.append("El número de archivos no coincide con changes_count.")
        notes = []
        for page in range(1, 4):
            discussions = self.get(self.root + f"/discussions?per_page=100&page={page}")
            for discussion in discussions:
                for note in discussion.get("notes", []):
                    if note.get("system"):
                        continue
                    position = note.get("position") or {}
                    notes.append(
                        {
                            "discussion_id": discussion["id"],
                            "note_id": str(note["id"]),
                            "resolved": note.get("resolved"),
                            "path": position.get("new_path"),
                            "line": position.get("new_line"),
                        }
                    )
                    if sum(len(s["text"]) for s in sources if s["kind"] == "discussion") < 45000:
                        source(
                            sources,
                            "discussion",
                            note.get("body", "")[:6000],
                            discussion_id=discussion["id"],
                            note_id=str(note["id"]),
                            resolved=note.get("resolved"),
                        )
                    else:
                        limitations.append("Historial de discusiones acotado por presupuesto.")
            if len(discussions) < 100:
                break
        else:
            limitations.append("Paginación de discusiones incompleta.")
        jobs = []
        pipelines = self.get(self.root + "/pipelines?per_page=20")
        matching = next((p for p in pipelines if p.get("sha") == refs["head_sha"]), None)
        if matching:
            raw_jobs = self.get(f"{self.prefix}/pipelines/{matching['id']}/jobs?per_page=100")
            jobs = [
                {k: j.get(k) for k in ("id", "name", "status", "allow_failure", "web_url")}
                for j in raw_jobs
            ]
            source(
                sources,
                "ci",
                json.dumps(
                    {
                        "pipeline_id": matching["id"],
                        "status": matching["status"],
                        "sha": matching["sha"],
                        "jobs": jobs,
                    }
                ),
            )
            if len(raw_jobs) == 100:
                limitations.append("Listado de jobs paginado, no completo.")
        else:
            limitations.append("Sin evidencia de pipeline para este head.")
        for path in (
            "AGENTS.md",
            ".ath/rules.md",
            ".claude/skills/review-commit-project-rules/SKILL.md",
        ):
            try:
                text = self.file(path, refs["head_sha"])
            except GitlabError:
                continue
            source(sources, "rules", text, path=path, sha=refs["head_sha"])
        return {
            "refs": refs,
            "version_id": str(version["id"]),
            "title": mr["title"],
            "mr_state": mr["state"],
            "description": redact((mr.get("description") or "")[:10000]),
            "diffs": diffs,
            "notes": notes,
            "jobs": jobs,
            "sources": sources,
            "limitations": sorted(set(limitations)),
            "read_calls": self.calls,
            "digest": hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest(),
        }
