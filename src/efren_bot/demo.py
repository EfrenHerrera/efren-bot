"""Enqueue stable fixtures through the same backend ingestion, without processing."""

import argparse
import json

from sqlalchemy.exc import SQLAlchemyError

from efren_bot.config import Settings
from efren_bot.db import make_engine, session_factory
from efren_bot.fixtures import demo_fixtures
from efren_bot.ingestion import IdentityConflict, ingest


def main(argv: list[str] | None = None) -> int:
    settings = Settings()  # guard even when no fixtures have been selected
    fixtures = demo_fixtures()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixtures", nargs="*", help="request_video, thanks, reply; default: all")
    args = parser.parse_args(argv)
    selected = args.fixtures or [fixture.id for fixture in fixtures]
    by_id = {fixture.id: fixture for fixture in fixtures}
    if any(name not in by_id for name in selected):
        parser.error("unknown fixture; use request_video, thanks or reply")
    engine = make_engine(settings)
    try:
        sessions = session_factory(engine)
        for name in selected:
            receipt = ingest(sessions, by_id[name].event)
            print(json.dumps({"fixture": name, **receipt.model_dump(mode="json")}))
        print("Fixtures persisted; projection is performed by the separate worker.")
    except IdentityConflict:
        print("Fixture identity conflicts with previously accepted content")
        return 1
    except SQLAlchemyError:
        print("Local database unavailable; no acceptance claimed for failed input")
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
