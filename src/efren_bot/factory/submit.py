"""Submit one request by hand, bypassing no criteria.

Useful to drive a controlled test without Slack or Notion:

    python -m efren_bot.factory.submit --project landing --text "Cambiar el botón a verde"

The item goes through the same funnel as any source (source kind ``manual``, always treated as a
work request, project given explicitly), so sensitive wording still goes to the human gate.
"""

import argparse
import json
import sys
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from efren_bot.config import Settings
from efren_bot.db import make_engine, session_factory
from efren_bot.factory.intake import IntakeItem
from efren_bot.factory.service import FactoryService
from efren_bot.factory.wiring import build_service


def submit(
    service: FactoryService, text: str, project: str, external_id: str | None = None
) -> dict:
    stamp = datetime.now(UTC)
    item = IntakeItem(
        source_kind="manual",
        external_id=external_id or f"manual-{stamp:%Y%m%dT%H%M%S%f}",
        title=text.strip().splitlines()[0][:80] if text.strip() else "",
        text=text,
        occurred_at=stamp,
        attrs={"project_hint": project, "human_flagged": True},
    )
    result = service.ingest([item])[0]
    return {
        "item_id": str(result.item_id),
        "decision": result.decision,
        "duplicate": result.duplicate,
        "job_id": str(result.job_id) if result.job_id else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Submit one request through the factory funnel")
    parser.add_argument("--project", required=True, help="registered project name")
    parser.add_argument("--text", required=True)
    parser.add_argument("--external-id", default=None)
    args = parser.parse_args(argv)
    try:
        settings = Settings()
        engine = make_engine(settings)
        try:
            service = build_service(settings, session_factory(engine))
            if service.projects.get(args.project) is None:
                print(f"Unknown project {args.project!r}", file=sys.stderr)
                return 2
            print(json.dumps(submit(service, args.text, args.project, args.external_id)))
        finally:
            engine.dispose()
    except (ValidationError, SQLAlchemyError):
        print("Invalid configuration or database unavailable", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
