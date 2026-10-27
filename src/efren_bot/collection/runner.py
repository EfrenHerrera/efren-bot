"""Host-only deterministic collector; runs independently of the browser."""

import hashlib
import json
import signal
import threading
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from efren_bot.collection.models import CollectionCapture, CollectionMessage, CollectionRun
from efren_bot.collection.reader import collect
from efren_bot.collection.service import CollectionService
from efren_bot.collection.transport import USER_ID, NativeSlack, TransportError
from efren_bot.config import Settings
from efren_bot.db import make_engine, session_factory

RUNNER_LOCK = 771061103
SCOPE = f"slack-account:{USER_ID}:default-workspace"


def execute_run(sessions, run, source):
    added, pages = 0, 0

    def capture(operation, arguments, response):
        nonlocal pages
        with sessions.begin() as session:
            row = CollectionCapture(
                run_id=run["id"],
                operation=operation,
                arguments=arguments,
                response=response,
                observed_at=datetime.now(UTC),
            )
            session.add(row)
            session.flush()
            identifier = row.id
            current = session.get(CollectionRun, run["id"])
            current.page_count += 1
            pages += 1
            return identifier

    def accept(capture_id, row):
        nonlocal added
        serial = {k: v.isoformat() if isinstance(v, datetime) else v for k, v in row.items()}
        sha = hashlib.sha256(
            json.dumps(serial, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        with sessions.begin() as session:
            identifier = session.scalar(
                insert(CollectionMessage)
                .values(
                    **row,
                    source_scope=SCOPE,
                    capture_id=capture_id,
                    sha256=sha,
                    observed_at=datetime.now(UTC),
                )
                .on_conflict_do_nothing()
                .returning(CollectionMessage.id)
            )
            if identifier:
                added += 1
                session.get(CollectionRun, run["id"]).added_count += 1

    result = collect(
        source.read,
        run["window_start"],
        run["window_end"],
        capture,
        accept,
        progress=run.get("progress"),
        sources=run.get("sources"),
    )
    return {**result, "added": added, "pages": pages}


def main():
    settings = Settings()
    root = Path(__file__).resolve().parents[3]
    runtime = root / ".local/collection/runtime"
    if not (runtime / "opencode.json").is_file():
        raise SystemExit("Collection runtime missing: see docs/slack-collection.md")
    engine = make_engine(settings)
    sessions = session_factory(engine)
    service = CollectionService(sessions)
    stop = threading.Event()
    for name in (signal.SIGINT, signal.SIGTERM):
        signal.signal(name, lambda *_: stop.set())
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as lock:
        if not lock.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": RUNNER_LOCK}):
            raise SystemExit("Collection runner already active")
        service.recover()

        def pulse():
            while not stop.is_set():
                try:
                    service.heartbeat()
                except Exception:
                    pass
                stop.wait(10)

        thread = threading.Thread(target=pulse, daemon=True)
        thread.start()
        try:
            while not stop.is_set():
                run = service.claim()
                if run:
                    result = {"status": "failed", "error_code": "collection_failed"}
                    try:
                        with NativeSlack(runtime) as source:
                            result = execute_run(sessions, run, source)
                    except TransportError:
                        result["status"], result["error_code"] = "failed", "native_transport_failed"
                    except Exception:
                        result["status"], result["error_code"] = "failed", "collection_failed"
                    service.finish(run["id"], **result)
                    print(
                        json.dumps(
                            {
                                "run_id": str(run["id"]),
                                "status": result["status"],
                                "pages": result.get("pages", 0),
                            }
                        ),
                        flush=True,
                    )
                stop.wait(2)
        finally:
            stop.set()
            thread.join(timeout=12)
            lock.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": RUNNER_LOCK})
    engine.dispose()


if __name__ == "__main__":
    main()
