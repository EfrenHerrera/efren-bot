"""Offline import of the two audited local indexes; no Slack/network access."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.dialects.postgresql import insert

from efren_bot.collection.models import CollectionCapture, CollectionMessage, CollectionRun
from efren_bot.collection.reader import stamp_datetime
from efren_bot.collection.runner import SCOPE

CHANNELS = {
    "C08MAH1JNC8": "crd-wc-devs",
    "C07SRBE0V1T": "crd-wc-tech",
    "C0B8HEZF54M": "tech-tribe-wc",
    "C05N151EB1T": "wc-issues-support",
    "C0C7N8SD0M7": "wc-validacion-facturas",
}
INDEXES = (
    "derived/messages.jsonl",
    "thread-expansion-20261025T011719Z/derived/messages-expanded.jsonl",
)


def own_path(root, relative):
    path = root / relative
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("archive_path_invalid")
    return path


def import_archive(sessions, root: Path):
    reads = {}

    def load(path):
        raw = path.read_bytes()
        reads[path] = hashlib.sha256(raw).hexdigest()
        return raw

    indexes = []
    for relative in INDEXES:
        path = own_path(root, relative)
        base = path.parent.parent
        manifest = json.loads(load(own_path(base, "derived/derived-manifest.json")))
        raw = load(path)
        entry = manifest["artifacts"][str(path.relative_to(base))]
        if entry["sha256"] != hashlib.sha256(raw).hexdigest() or entry["bytes"] != len(raw):
            raise ValueError("archive_index_hash_mismatch")
        indexes.append((base, raw))
    digest = hashlib.sha256(b"\n".join(raw for _, raw in indexes)).hexdigest()
    run_id = uuid5(NAMESPACE_URL, "efrenbot:local-archive:" + digest)
    now = datetime.now(UTC)
    added = 0
    capture_ids = {}
    with sessions.begin() as s:
        if s.get(CollectionRun, run_id):
            return {"already_imported": True, "added_variants": 0, "run_id": str(run_id)}
        # Serialize repeat imports without touching the collection runner's lock or watermark.
        from sqlalchemy import text

        s.execute(text("SELECT pg_advisory_xact_lock(771061104)"))
        if s.get(CollectionRun, run_id):
            return {"already_imported": True, "added_variants": 0, "run_id": str(run_id)}
        run = CollectionRun(
            id=run_id,
            trigger="import",
            status="succeeded",
            created_at=now,
            started_at=now,
            finished_at=now,
            window_start=datetime(2026, 10, 11, tzinfo=UTC),
            window_end=datetime(2026, 10, 25, 0, 6, 58, tzinfo=UTC),
            added_count=0,
            page_count=0,
            coverage=[{"scope": "local_archive", "state": "audited_indexes_imported"}],
            sources={},
        )
        s.add(run)
        s.flush()
        for base, raw in indexes:
            for line in raw.decode("utf-8").splitlines():
                record = json.loads(line)
                for variant in record["variants"]:
                    cid = variant["channel_id"]
                    if cid not in CHANNELS:
                        raise ValueError("archive_scope_invalid")
                    stamp = variant["ts"]
                    occurred = stamp_datetime(stamp)
                    rendered = variant["rendered_record"]
                    if (
                        hashlib.sha256(rendered.encode()).hexdigest()
                        != variant["rendered_record_sha256"]
                    ):
                        raise ValueError("archive_record_hash_mismatch")
                    path = own_path(base, variant["capture_path"])
                    if path not in capture_ids:
                        payload = json.loads(load(path))
                        if payload["channel_id"] != cid:
                            raise ValueError("archive_capture_scope_invalid")
                        identifier = uuid5(run_id, str(path.relative_to(root)))
                        observed = datetime.fromisoformat(
                            payload["finished_at"].replace("Z", "+00:00")
                        )
                        if observed.tzinfo is None:
                            raise ValueError("archive_time_invalid")
                        s.add(
                            CollectionCapture(
                                id=identifier,
                                run_id=run.id,
                                operation="archive",
                                arguments={
                                    "capture_path": str(path.relative_to(root)),
                                    "sha256": reads[path],
                                },
                                response=payload,
                                observed_at=observed,
                            )
                        )
                        s.flush()
                        capture_ids[path] = (identifier, observed)
                    capture_id, observed = capture_ids[path]
                    parent = variant.get("parent_ts", variant.get("thread_ts"))
                    if parent:
                        stamp_datetime(parent)
                    links = variant.get("links") or record.get("links", [])
                    url = None
                    for link in links:
                        parsed = urlsplit(link.get("url", ""))
                        if (
                            parsed.scheme == "https"
                            and parsed.hostname
                            and parsed.hostname.endswith(".slack.com")
                            and not parsed.username
                            and not parsed.password
                            and not parsed.port
                            and parsed.path == f"/archives/{cid}/p{stamp.replace('.', '')}"
                        ):
                            url = link["url"]
                            break
                    values = {
                        "channel_id": cid,
                        "channel_name": CHANNELS[cid],
                        "message_id": stamp,
                        "thread_id": parent,
                        "actor_id": variant.get("author_id"),
                        "text": variant["rendered_text"],
                        "occurred_at": occurred,
                        "source_url": url,
                    }
                    serial = {
                        k: v.isoformat() if isinstance(v, datetime) else v
                        for k, v in values.items()
                    }
                    sha = hashlib.sha256(
                        json.dumps(serial, sort_keys=True, ensure_ascii=False).encode()
                    ).hexdigest()
                    result = s.scalar(
                        insert(CollectionMessage)
                        .values(
                            **values,
                            source_scope=SCOPE,
                            capture_id=capture_id,
                            observed_at=observed,
                            sha256=sha,
                            is_historical=True,
                            provenance={
                                "archive": "slack-history-pilot",
                                "capture_path": str(path.relative_to(root)),
                                "capture_sha256": reads[path],
                                "locator": variant.get("locator"),
                                "imported_at": now.isoformat(),
                                "context_only": variant.get("base_window_classification")
                                == "context_only",
                            },
                        )
                        .on_conflict_do_nothing()
                        .returning(CollectionMessage.id)
                    )
                    added += result is not None
        if any(hashlib.sha256(path.read_bytes()).hexdigest() != sha for path, sha in reads.items()):
            raise ValueError("archive_changed_during_import")
        run.added_count = added
        run.page_count = len(capture_ids)
    return {
        "already_imported": False,
        "added_variants": added,
        "captures": len(capture_ids),
        "run_id": str(run_id),
        "originals_unchanged": True,
    }


def main():
    from efren_bot.config import Settings
    from efren_bot.db import make_engine, session_factory

    engine = make_engine(Settings())
    root = Path.home() / ".local/share/efren-bot/research/slack/20261025T000658Z"
    print(json.dumps(import_archive(session_factory(engine), root)))
    engine.dispose()


if __name__ == "__main__":
    main()
