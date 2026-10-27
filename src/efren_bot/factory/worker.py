"""Factory worker: pull sources, run queued jobs, reclaim stale work. Opt-in process."""

import argparse
import json
import time

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from efren_bot.config import Settings
from efren_bot.db import make_engine, session_factory
from efren_bot.factory.service import FactoryService
from efren_bot.factory.wiring import (
    build_notion_client,
    build_service,
    last_seen,
    pull_adapters,
)


def pull_once(service: FactoryService, adapters: dict, sources: list[str]) -> dict[str, int]:
    """Fetch new items from each named pull source and run them through the funnel."""
    counts: dict[str, int] = {}
    for name in sources:
        adapter = adapters.get(name)
        if adapter is None:
            counts[name] = -1  # unknown or not configured: reported, never silently skipped
            continue
        items = adapter.fetch(last_seen(service.sessions, name))
        counts[name] = sum(1 for r in service.ingest(items) if not r.duplicate)
    return counts


def tick(
    service: FactoryService, adapters: dict, sources: list[str], *, admission_only: bool = False
) -> dict:
    pulled = pull_once(service, adapters, sources)
    if admission_only:  # read-only rehearsal: decide admissions, run nothing, perform nothing
        return {"pulled": pulled, "ran": 0, "effects": 0, "reclaimed": 0, "expired": 0}
    ran = 0
    while service.process_one() is not None:
        ran += 1
        if ran >= 20:  # bounded per tick so pulls and reclaims keep happening
            break
    return {
        "pulled": pulled,
        "ran": ran,
        "effects": service.run_approved_effects(),
        "reclaimed": service.reclaim_stale(),
        "expired": service.expire_effects(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Factory worker (mocked unless configured)")
    parser.add_argument("--once", action="store_true")
    parser.add_argument(
        "--pull", default="", help="comma-separated pull sources, e.g. slack,notion"
    )
    parser.add_argument(
        "--admission-only",
        action="store_true",
        help="pull and triage only: no job runs, no effects, nothing leaves the database",
    )
    args = parser.parse_args(argv)
    sources = [s for s in args.pull.split(",") if s]
    try:
        settings = Settings()
        engine = make_engine(settings)
        sessions = session_factory(engine)
        notion = build_notion_client(settings)
        service = build_service(settings, sessions, notion_client=notion)
        adapters = pull_adapters(
            sessions,
            notion_client=notion,
            notion_status_property=settings.factory_notion_status_property,
        )
        while True:
            print(
                json.dumps(tick(service, adapters, sources, admission_only=args.admission_only)),
                flush=True,
            )
            if args.once:
                return 0
            time.sleep(settings.worker_poll_interval_seconds)
    except ValidationError:
        print("Invalid local configuration", flush=True)
        return 1
    except SQLAlchemyError:
        print("Local database unavailable", flush=True)
        return 1
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
