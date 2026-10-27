from uuid import uuid4

import pytest

from efren_bot.collection.transport import TransportError
from efren_bot.support.model import NativeText, sanitize, validate


def context():
    identifier = str(uuid4())
    return {"trigger_id": identifier, "messages": [{"id": identifier, "text": "synthetic"}]}


def test_validation_requires_trigger_and_rejects_fabricated_evidence():
    data = context()
    raw = {"action": "support", "title": "Synthetic", "reason": "Reported", "evidence_ids": []}
    with pytest.raises(ValueError):
        validate("classify", data, raw)
    raw["evidence_ids"] = [str(uuid4())]
    with pytest.raises(ValueError):
        validate("classify", data, raw)
    raw["evidence_ids"] = [data["trigger_id"]]
    assert validate("classify", data, raw)["action"] == "support"


def test_sanitization_preserves_ids_and_json_structure():
    data = {
        "text": (
            "Bearer private-token contact a@example.test RFC HERA900101ABC "
            "CURP HERA900101HMCRRF01 phone 5512345678"
        ),
        "id": "5512345678",
        "evidence_ids": ["5512345678"],
        "nested": [{"text": 'password="secret"'}],
    }
    clean = sanitize(data)
    assert "private-token" not in clean["text"] and "example.test" not in clean["text"]
    assert "HERA900101ABC" not in clean["text"] and "HERA900101HMCRRF01" not in clean["text"]
    assert "5512345678" not in clean["text"] and clean["id"] == "5512345678"
    assert clean["evidence_ids"] == ["5512345678"]


def test_native_text_denies_tools_pins_model_and_uses_generate_only(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (tmp_path / "profile.json").write_text('{"providerID":"synthetic","id":"test"}')
    calls = []

    def api(self, method, path, data=None, **kwargs):
        calls.append((method, path, data))
        if path == "/api/session":
            return {
                "data": {
                    "id": "ses_synthetic",
                    "agent": "build",
                    "model": {"providerID": "synthetic", "id": "test", "variant": "default"},
                    "permissions": [{"action": "*", "resource": "*", "effect": "deny"}],
                }
            }
        if path.endswith("/generate"):
            return {
                "data": {
                    "text": (
                        '{"action":"ignore","title":"Thanks",'
                        '"reason":"No new support","evidence_ids":[]}'
                    )
                }
            }
        if path.startswith("/api/session?"):
            return {"data": [{"id": "ses_synthetic", "time": {"archived": 1}}]}
        return {}

    monkeypatch.setattr(NativeText, "api", api)
    with NativeText(runtime) as model:
        assert model.generate("classify", context())["action"] == "ignore"
    assert any(path.endswith("/generate") for _, path, _ in calls)
    assert not any("/prompt" in path or "/rpc" in path for _, path, _ in calls)
    assert calls[-2][2] == {"archived": True}


def test_wrong_model_or_widened_permissions_fail_before_generation(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (tmp_path / "profile.json").write_text('{"providerID":"synthetic","id":"test"}')
    calls = []

    def api(self, method, path, data=None, **kwargs):
        calls.append(path)
        if path == "/api/session":
            return {
                "data": {
                    "id": "ses_bad",
                    "agent": "build",
                    "model": {"providerID": "other", "id": "model"},
                    "permissions": [],
                }
            }
        if path.startswith("/api/session?"):
            return {"data": [{"id": "ses_bad", "time": {"archived": 1}}]}
        return {}

    monkeypatch.setattr(NativeText, "api", api)
    with pytest.raises(TransportError):
        with NativeText(runtime):
            pass
    assert not any("/generate" in path for path in calls)
