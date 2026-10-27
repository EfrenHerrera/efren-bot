import pytest
from fastapi.testclient import TestClient

from efren_bot.api import create_app
from efren_bot.collection.service import CollectionService

pytestmark = pytest.mark.integration
HEADERS = {"Host": "127.0.0.1:8000", "Origin": "http://127.0.0.1:5173", "X-Efren-Local": "1"}


def test_conversation_routes_require_capability_and_do_not_echo_invalid_input(database, pg_engine):
    with TestClient(create_app(engine=pg_engine)) as client:
        token = client.get("/api/collection/session", headers=HEADERS).json()["token"]
        headers = {**HEADERS, "X-Collection-Token": token}
        assert (
            client.post("/api/collection/conversations/list", headers=HEADERS, json={}).status_code
            == 401
        )
        assert (
            client.post("/api/collection/conversations/list", headers=headers, json={}).json()[
                "total"
            ]
            == 0
        )
        invalid = client.post(
            "/api/collection/conversations/group-save",
            headers=headers,
            json={"title": "private-invalid-content", "unknown": True},
        )
        assert invalid.status_code == 422 and "private-invalid-content" not in invalid.text
        assert (
            client.post(
                "/api/collection/conversations/list",
                headers={**headers, "Content-Type": "application/json"},
                content='{"view":"all","view":"mentions"}',
            ).status_code
            == 422
        )


def test_capability_host_origin_and_json_before_commands(database, pg_engine):
    service = CollectionService(database)
    service.heartbeat()
    with TestClient(create_app(engine=pg_engine)) as client:
        assert client.get("/api/collection/status").status_code == 403
        assert (
            client.get(
                "/api/collection/session", headers={**HEADERS, "Origin": "https://evil.test"}
            ).status_code
            == 403
        )
        assert (
            client.get(
                "/api/collection/session", headers={**HEADERS, "Host": "evil.test:8000"}
            ).status_code
            == 403
        )
        assert client.get("/api/collection/status", headers=HEADERS).status_code == 401
        session = client.get("/api/collection/session", headers=HEADERS)
        token = session.json()["token"]
        assert session.headers["cache-control"] == "no-store"
        headers = {**HEADERS, "X-Collection-Token": token}
        assert (
            client.post(
                "/api/collection/run", headers=headers, json={"channel_id": "outside"}
            ).status_code
            == 422
        )
        assert (
            client.get("/api/collection/status?token=not_allowed", headers=headers).status_code
            == 422
        )
        assert client.post("/api/collection/activate", headers=headers, json={}).status_code == 200
        assert client.post("/api/collection/pause", headers=headers, json={}).status_code == 200
        assert client.post("/api/collection/run", headers=headers, json={}).status_code == 200
        state = client.get("/api/collection/status", headers=headers).json()
        assert state["paused"] is True
        assert state["active_run"]["status"] == "queued"
        assert "token" not in state
        assert client.post("/api/collection/resume", headers=headers, json={}).status_code == 200


def test_runner_absence_does_not_enqueue_a_fake_success(database, pg_engine):
    with TestClient(create_app(engine=pg_engine)) as client:
        token = client.get("/api/collection/session", headers=HEADERS).json()["token"]
        result = client.post(
            "/api/collection/run", headers={**HEADERS, "X-Collection-Token": token}, json={}
        )
        assert result.status_code == 409
        assert result.json() == {"error": "runner_unavailable"}


def test_inbox_contracts_are_closed_and_protected(database, pg_engine):
    with TestClient(create_app(engine=pg_engine)) as client:
        token = client.get("/api/collection/session", headers=HEADERS).json()["token"]
        headers = {**HEADERS, "X-Collection-Token": token}
        assert (
            client.post("/api/collection/inbox/list", headers=HEADERS, json={}).status_code == 401
        )
        assert (
            client.post("/api/collection/inbox/list", headers=headers, json={}).json()["total"] == 0
        )
        assert (
            client.post("/api/collection/sources/list", headers=headers, json={}).status_code == 200
        )
        invalid = client.post(
            "/api/collection/inbox/list",
            headers=headers,
            json={"query": "private-test", "unexpected": "private-test"},
        )
        assert invalid.status_code == 422 and "private-test" not in invalid.text
        assert (
            client.post(
                "/api/collection/inbox/list",
                headers={**headers, "Content-Type": "application/json"},
                content='{"offset":0,"offset":1}',
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/collection/sources/save",
                headers=headers,
                json={"channel_id": "C9999999999", "mode": "full"},
            ).status_code
            == 409
        )
