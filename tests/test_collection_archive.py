import hashlib
import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from efren_bot.collection.archive import INDEXES, import_archive
from efren_bot.collection.inbox import InboxService, ListInput
from efren_bot.collection.models import CollectionMessage

pytestmark = pytest.mark.integration


def archive_fixture(root):
    now = datetime.now(UTC).isoformat()
    for relative in INDEXES:
        base = (root / relative).parent.parent
        base.mkdir(parents=True, exist_ok=True)
        capture = {
            "channel_id": "C08MAH1JNC8",
            "operation": "slack_read_channel",
            "arguments": {},
            "response": {},
            "finished_at": now,
        }
        (base / "capture.json").write_text(json.dumps(capture))
        record = "synthetic-record"
        variant = {
            "channel_id": "C08MAH1JNC8",
            "ts": "1767225600.000001",
            "rendered_text": "synthetic body",
            "rendered_record": record,
            "rendered_record_sha256": hashlib.sha256(record.encode()).hexdigest(),
            "capture_path": "capture.json",
            "author_id": "synthetic-author",
            "thread_ts": None,
        }
        path = root / relative
        path.parent.mkdir(exist_ok=True)
        raw = (json.dumps({"variants": [variant]}) + "\n").encode()
        path.write_bytes(raw)
        (path.parent / "derived-manifest.json").write_text(
            json.dumps(
                {
                    "artifacts": {
                        str(path.relative_to(base)): {
                            "sha256": hashlib.sha256(raw).hexdigest(),
                            "bytes": len(raw),
                        }
                    }
                }
            )
        )


def test_import_is_offline_atomic_idempotent_and_not_new(database, tmp_path):
    archive_fixture(tmp_path)
    before = {
        p: hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.rglob("*") if p.is_file()
    }
    first = import_archive(database, tmp_path)
    assert first["added_variants"] == 1
    assert import_archive(database, tmp_path)["already_imported"]
    assert InboxService(database).list(ListInput(review="new"))["total"] == 0
    assert InboxService(database).list(ListInput(origin="historical"))["total"] == 1
    assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before}


def test_unverified_index_cannot_partially_import(database, tmp_path):
    archive_fixture(tmp_path)
    with (tmp_path / INDEXES[-1]).open("a") as file:
        file.write("tampered")
    with pytest.raises(ValueError, match="archive_index_hash_mismatch"):
        import_archive(database, tmp_path)
    with database() as s:
        assert s.scalar(select(func.count()).select_from(CollectionMessage)) == 0
