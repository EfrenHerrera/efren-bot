"""HTTP surfaces of the plant: hardened local operations edge + signed WhatsApp webhook."""

import hashlib
import hmac
import json

import pytest
from factory_helpers import POLICY, PROFILES, item, projects, record
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from efren_bot.collection.http import install_collection
from efren_bot.factory import effects as fx
from efren_bot.factory.executor import ScriptedExecutor
from efren_bot.factory.http import FactoryOperations, install_factory_webhooks
from efren_bot.factory.service import FactoryService

pytestmark = pytest.mark.integration
HEADERS = {"Host": "127.0.0.1:8000", "Origin": "http://127.0.0.1:5173", "X-Efren-Local": "1"}
SECRET = "app-secret"
VERIFY = "verify-me"


@pytest.fixture
def plant(pg_engine):
    from efren_bot.db import session_factory

    with pg_engine.begin() as connection:
        assert connection.scalar(text("SELECT current_database()")) == "efren_bot_test"
        connection.execute(
            text("TRUNCATE factory_effects, factory_jobs, factory_admissions, factory_items")
        )
    sessions = session_factory(pg_engine)
    gateway = fx.RecordingGateway()
    service = FactoryService(
        sessions,
        projects=projects(),
        profiles=PROFILES,
        policy=POLICY,
        executor=ScriptedExecutor(lambda spec: record(spec)),
        gateway=gateway,
    )
    app = FastAPI()
    install_factory_webhooks(app, service, whatsapp_app_secret=SECRET, whatsapp_verify_token=VERIFY)
    install_collection(app, sessions, factory=FactoryOperations(service, sessions))
    client = TestClient(app)
    token = client.get("/api/collection/session", headers=HEADERS).json()["token"]
    headers = {**HEADERS, "X-Collection-Token": token}

    def call(operation, body=None):
        return client.post(f"/api/collection/factory/{operation}", headers=headers, json=body or {})

    return client, service, gateway, call


def wa(body, message_id="wamid.1"):
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"wa_id": "521", "profile": {"name": "Ana"}}],
                            "messages": [
                                {
                                    "id": message_id,
                                    "from": "521",
                                    "timestamp": "1790000000",
                                    "type": "text",
                                    "text": {"body": body},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }


def signed(client, payload, secret=SECRET, signature=None):
    raw = json.dumps(payload).encode()
    sig = signature or "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return client.post(
        "/api/factory/webhooks/whatsapp",
        content=raw,
        headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
    )


# ---------------------------------------------------------------- webhook


def test_whatsapp_webhook_accepts_only_correctly_signed_bodies(plant):
    client, service, _, call = plant
    payload = wa("por favor cambia el botón de la landing a verde")
    assert signed(client, payload, signature="sha256=" + "0" * 64).status_code == 401
    assert signed(client, payload, secret="wrong").status_code == 401
    assert client.post("/api/factory/webhooks/whatsapp", json=payload).status_code == 401
    ok = signed(client, payload)
    assert ok.status_code == 202 and ok.json() == {"received": 1, "duplicates": 0}
    assert signed(client, payload).json()["duplicates"] == 1
    assert call("list").json()["items_by_status"] == {"admitted": 1}


def test_whatsapp_webhook_fails_closed_without_configuration(pg_engine):
    from efren_bot.db import session_factory

    sessions = session_factory(pg_engine)
    service = FactoryService(
        sessions,
        projects=projects(),
        profiles=PROFILES,
        policy=POLICY,
        executor=ScriptedExecutor(lambda s: record(s)),
        gateway=fx.RecordingGateway(),
    )
    app = FastAPI()
    install_factory_webhooks(app, service, whatsapp_app_secret="", whatsapp_verify_token="")
    client = TestClient(app)
    assert client.post("/api/factory/webhooks/whatsapp", json={}).status_code == 503
    assert client.get("/api/factory/webhooks/whatsapp").status_code == 503


def test_whatsapp_verification_challenge(plant):
    client, *_ = plant
    url = "/api/factory/webhooks/whatsapp"
    good = client.get(
        url, params={"hub.mode": "subscribe", "hub.verify_token": VERIFY, "hub.challenge": "42"}
    )
    assert good.status_code == 200 and good.text == "42"
    bad = client.get(
        url, params={"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "42"}
    )
    assert bad.status_code == 403


def test_signed_garbage_is_a_422_not_a_crash(plant):
    client, *_ = plant
    bad = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "type": "text",
                                    "timestamp": "x",
                                    "text": {"body": "hola hola hola"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    assert signed(client, bad).status_code == 422
    raw = b"not json"
    sig = "sha256=" + hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    resp = client.post(
        "/api/factory/webhooks/whatsapp", content=raw, headers={"X-Hub-Signature-256": sig}
    )
    assert resp.status_code == 422


def test_there_is_no_unauthenticated_route_that_mutates_the_plant(plant):
    client, *_ = plant
    for path in ("/api/factory/overview", "/api/factory/jobs/x", "/api/factory/intake/fixture"):
        assert client.post(path, json={}).status_code in {404, 405}
        assert client.get(path).status_code in {404, 405}


# ------------------------------------------------- hardened operations edge


def test_operations_require_the_local_capability(plant):
    client, *_ = plant
    assert client.post("/api/collection/factory/list", headers=HEADERS, json={}).status_code == 401
    assert client.post("/api/collection/factory/list", json={}).status_code == 403
    evil = {**HEADERS, "Origin": "https://evil.test"}
    assert client.post("/api/collection/factory/list", headers=evil, json={}).status_code == 403


def test_operations_validate_strictly_and_do_not_echo_input(plant):
    *_, call = plant
    bad = call("effect", {"id": "not-a-uuid", "action": "approve", "secret-field": "private-text"})
    assert bad.status_code == 422 and "private-text" not in bad.text
    assert call("nope", {}).status_code == 404
    assert call("list", {"unexpected": 1}).status_code == 422


def test_awaiting_items_show_reasons_and_a_person_can_admit_them(plant):
    client, service, _, call = plant
    signed(client, wa("por favor implementa algo nuevo para ventas"))
    listing = call("list").json()
    waiting = listing["awaiting_admission"]
    assert len(waiting) == 1 and waiting[0]["admission"]["decision"] == "ask_context"
    assert {p["name"] for p in listing["projects"]} == {
        "landing",
        "payments-orchestrator",
        "etl-lambdas",
    }
    item_id = waiting[0]["id"]
    refused = call("admission", {"id": item_id, "action": "admit"})
    assert refused.status_code == 422 and refused.json() == {"error": "project_required"}
    ok = call("admission", {"id": item_id, "action": "admit", "project": "etl-lambdas"})
    assert ok.status_code == 200 and ok.json()["job_id"]


def test_effect_decision_requires_the_exact_fingerprint(plant):
    client, service, gateway, call = plant
    service.ingest([item(project_hint="Landing Web")])
    service.process_one()
    pending = call("list").json()["pending_effects"]
    assert [e["kind"] for e in pending] == ["update_notion"]
    effect = pending[0]
    wrong = call("effect", {"id": effect["id"], "action": "approve", "fingerprint": "f" * 64})
    assert wrong.status_code == 409 and wrong.json() == {"error": "fingerprint_mismatch"}
    ok = call(
        "effect",
        {
            "id": effect["id"],
            "action": "approve",
            "fingerprint": effect["fingerprint"],
            "text": "dale",
        },
    )
    assert ok.status_code == 200 and ok.json()["state"] == "approved"
    assert call("list").json()["pending_effects"] == []
    assert [k for k, _, _ in gateway.executed] == ["open_pr"]  # the web process performs nothing
    assert service.run_approved_effects() == 1  # the host worker does
    assert [k for k, _, _ in gateway.executed] == ["open_pr", "update_notion"]


def test_job_detail_and_control(plant):
    client, service, _, call = plant
    job_id = str(service.ingest([item(project_hint="Landing Web")])[0].job_id)
    assert call("control", {"id": job_id, "action": "pause"}).status_code == 200
    assert call("detail", {"id": job_id}).json()["status"] == "paused"
    assert call("control", {"id": job_id, "action": "bogus"}).status_code == 422
    assert call("detail", {"id": "00000000-0000-0000-0000-000000000000"}).status_code == 404
    assert call("control", {"id": job_id, "action": "stop"}).status_code == 200
    assert call("control", {"id": job_id, "action": "pause"}).status_code == 409
