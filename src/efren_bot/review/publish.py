"""One admitted, exact inline comment. Never approve, resolve or merge an MR."""

import json
import subprocess

from efren_bot.review.gitlab import SHA, Gitlab, validate_path


class PublicationUncertain(Exception):
    pass


def publish_comment(project, iid, approved, marker):
    client = Gitlab(project, iid)
    refs = approved["refs"]
    finding = approved["finding"]
    if any(not SHA.fullmatch(str(refs.get(k, ""))) for k in ("head_sha", "base_sha", "start_sha")):
        raise ValueError("invalid approved refs")
    validate_path(finding["path"])
    if not isinstance(finding["line"], int) or finding["line"] < 1:
        raise ValueError("invalid line")
    body = approved["body"]
    if not body.strip() or len(body) > 5000:
        raise ValueError("invalid approved body")
    payload = {
        "body": body + f"\n\n<!-- efrenbot-review:{marker} -->",
        "position": {
            "position_type": "text",
            **refs,
            "new_path": finding["path"],
            "old_path": approved["old_path"],
            "new_line": finding["line"],
        },
    }
    try:
        result = subprocess.run(
            [
                "glab",
                "api",
                "--hostname",
                "gitlab.com",
                "--method",
                "POST",
                client.root + "/discussions",
                "--input",
                "-",
            ],
            input=json.dumps(payload).encode(),
            capture_output=True,
            timeout=45,
        )
        if result.returncode:
            raise PublicationUncertain("publication_unconfirmed")
        identifier = json.loads(result.stdout).get("id")
        if not isinstance(identifier, str) or not identifier:
            raise PublicationUncertain("publication_unconfirmed")
        return identifier
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        raise PublicationUncertain("publication_unconfirmed") from error
