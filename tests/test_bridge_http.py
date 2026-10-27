from uuid import uuid4

import pytest
from bridge_helpers import TOKEN, URL, write_profile
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event

from efren_bot.api import create_app
from efren_bot.config import Settings


@pytest.fixture
def boundary(tmp_path, request):
    tmp_path.chmod(0o700)
    token = tmp_path / "token"
    token.write_text(TOKEN + "\n")
    token.chmod(0o600)
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "before_cursor_execute")
    def no_database(*args):
        raise AssertionError("SQL forbidden for rejected requests")

    settings = Settings(
        claude_bridge_enabled=getattr(request, "param", True),
        claude_bridge_token_file=str(token),
        claude_bridge_profile_file=str(tmp_path / "profile.json"),
    )
    client = TestClient(create_app(settings, engine=engine), base_url="http://127.0.0.1:8000")
    yield client, tmp_path
    client.close()
    engine.dispose()


def browser_headers(**overrides):
    return {"Origin": "http://127.0.0.1:5173", "Authorization": "Bearer " + TOKEN, **overrides}


@pytest.mark.parametrize(
    "headers,code",
    [
        ({"Host": "api:8000"}, 403),
        ({"Host": "evil.test"}, 403),
        ({"Host": "127.0.0.1:8001"}, 403),
        ({"Origin": "null"}, 403),
        ({"Origin": "http://evil.test"}, 403),
        ({"Sec-Fetch-Site": "cross-site"}, 403),
        ({"Sec-Fetch-Site": "Cross-Site"}, 403),
        ({"Authorization": "Bearer wrong"}, 401),
        ({"Authorization": "Bearer " + TOKEN + " "}, 401),
        ({"Authorization": "x"}, 401),
    ],
)
def test_reject_before_sql(boundary, headers, code):
    client, _ = boundary
    response = client.post(
        "/api/bridge/runs",
        headers=browser_headers(**headers),
        json={"requested_slack_permalink": URL, "idempotency_key": str(uuid4())},
    )
    assert response.status_code == code
    assert response.headers["cache-control"] == "no-store"
    assert TOKEN not in response.text and URL not in response.text


@pytest.mark.parametrize(
    "name,values,code",
    [
        ("Host", ["127.0.0.1:8000", "evil.test"], 403),
        ("Origin", ["http://127.0.0.1:5173"] * 2, 403),
        ("Authorization", ["Bearer " + TOKEN] * 2, 401),
    ],
)
def test_duplicate_security_headers(boundary, name, values, code):
    client, _ = boundary
    headers = [(k, v) for k, v in browser_headers().items() if k.lower() != name.lower()]
    headers.extend((name, v) for v in values)
    assert client.get("/api/bridge/runs/" + str(uuid4()), headers=headers).status_code == code


@pytest.mark.parametrize(
    "raw,media,code",
    [
        ('{"idempotency_key":"secret","idempotency_key":"other"}', "application/json", 422),
        ('{"bad":NaN}', "application/json", 422),
        ('{"bad":1.0}', "application/json", 422),
        ("[]", "application/json", 422),
        ('{"provider":"secret"}', "application/json", 422),
        ("x" * 4097, "application/json", 413),
        ("{}", "text/plain", 415),
        ("{}", "application/x-www-form-urlencoded", 415),
    ],
)
def test_strict_body_no_echo_no_sql(boundary, raw, media, code):
    client, directory = boundary
    write_profile(directory)
    response = client.post(
        "/api/bridge/runs", content=raw, headers=browser_headers(**{"Content-Type": media})
    )
    assert response.status_code == code
    assert "secret" not in response.text and TOKEN not in response.text


def test_status_pending_without_database_and_get_origin(boundary):
    client, _ = boundary
    response = client.get("/api/bridge/status", headers={"Origin": "http://localhost:5173"})
    assert response.json() == {
        "mode": "manual_claude_slack",
        "enabled": True,
        "configuration": "pending",
        "reason": "profile_missing",
    }
    assert client.get("/api/bridge/status").status_code == 403
    implicit = {
        "Host": "localhost:5173",
        "Sec-Fetch-Site": "Same-Origin",
        "Authorization": "Bearer " + TOKEN,
    }
    assert client.get("/api/bridge/status", headers=implicit).status_code == 200
    implicit.pop("Authorization")
    assert client.get("/api/bridge/status", headers=implicit).status_code == 200
    assert client.get("/healthz").json() == {"status": "ok"}


@pytest.mark.parametrize("host", ["127.0.0.1:5173", "localhost:5173"])
@pytest.mark.parametrize(
    "boundary,configuration,reason",
    [(True, "pending", "profile_missing"), (False, "disabled", "disabled")],
    indirect=["boundary"],
)
def test_browser_public_status_without_origin_or_bearer(boundary, host, configuration, reason):
    client, _ = boundary
    response = client.get(
        "/api/bridge/status", headers={"Host": host, "Sec-Fetch-Site": "same-origin"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "mode": "manual_claude_slack",
        "enabled": configuration != "disabled",
        "configuration": configuration,
        "reason": reason,
    }
    assert response.headers["cache-control"] == "no-store"
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("authorization", [None, "Bearer wrong", "Bearer " + TOKEN])
@pytest.mark.parametrize("origin", [None, "http://127.0.0.1:5173"])
def test_public_status_does_not_require_available_token(boundary, authorization, origin):
    client, directory = boundary
    (directory / "token").unlink()
    headers = {"Host": "127.0.0.1:5173", "Sec-Fetch-Site": "same-origin"}
    if authorization is not None:
        headers["Authorization"] = authorization
    if origin is not None:
        headers["Origin"] = origin
    response = client.get("/api/bridge/status", headers=headers)
    assert response.status_code == 200
    assert response.json() == {
        "mode": "manual_claude_slack",
        "enabled": True,
        "configuration": "pending",
        "reason": "token_unavailable",
    }


@pytest.mark.parametrize(
    "overrides",
    [
        {"Origin": "http://evil.test"},
        {"Origin": "null"},
        {"Sec-Fetch-Site": "cross-site"},
        {"Sec-Fetch-Site": "Cross-Site", "Origin": "http://127.0.0.1:5173"},
        {"Sec-Fetch-Site": "same-site"},
        {"Sec-Fetch-Site": "none"},
        {"Host": "127.0.0.1:8000"},
        {"Host": "localhost:8000"},
        {"Host": "api:8000"},
        {"Host": "evil.test", "X-Forwarded-Host": "127.0.0.1:5173"},
        {"Host": "127.0.0.1:5174"},
    ],
)
def test_public_status_rejects_untrusted_browser_context(boundary, overrides):
    client, _ = boundary
    response = client.get(
        "/api/bridge/status",
        headers={"Host": "127.0.0.1:5173", "Sec-Fetch-Site": "same-origin", **overrides},
    )
    assert response.status_code == 403
    assert response.json() == {"error": {"code": "forbidden", "message": "forbidden"}}
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("host", ["127.0.0.1:5173", "localhost:5173"])
def test_public_status_requires_origin_or_same_origin_fetch_metadata(boundary, host):
    client, _ = boundary
    assert client.get("/api/bridge/status", headers={"Host": host}).status_code == 403


@pytest.mark.parametrize("name", ["Host", "Origin", "Sec-Fetch-Site"])
def test_public_status_rejects_duplicate_context_headers(boundary, name):
    client, _ = boundary
    headers = [
        ("Host", "127.0.0.1:5173"),
        ("Origin", "http://127.0.0.1:5173"),
        ("Sec-Fetch-Site", "same-origin"),
    ]
    headers.append(next(header for header in headers if header[0] == name))
    assert client.get("/api/bridge/status", headers=headers).status_code == 403


@pytest.mark.parametrize("authorization", [None, "Bearer wrong"])
def test_browser_fallback_run_and_unknown_paths_still_require_token(boundary, authorization):
    client, _ = boundary
    headers = {"Host": "127.0.0.1:5173", "Sec-Fetch-Site": "same-origin"}
    if authorization is not None:
        headers["Authorization"] = authorization
    for path in ("/api/bridge/runs/" + str(uuid4()), "/api/bridge/unknown"):
        response = client.get(path, headers=headers)
        assert response.status_code == 401
        assert response.json() == {"error": {"code": "unauthorized", "message": "unauthorized"}}
    for path in ("/api/bridge/runs", "/api/bridge/runs/" + str(uuid4()) + "/cancel"):
        response = client.post(
            path, json={}, headers={**headers, "Origin": "http://127.0.0.1:5173"}
        )
        assert response.status_code == 401


def test_runner_origin_absent_and_host_exact(boundary):
    client, _ = boundary
    assert (
        client.post("/api/bridge/runner/claim", json={}, headers=browser_headers()).status_code
        == 403
    )
    assert (
        client.post(
            "/api/bridge/runner/claim",
            json={},
            headers={
                "Host": "localhost:8000",
                "Authorization": "Bearer " + TOKEN,
            },
        ).status_code
        == 403
    )
    response = client.post(
        "/api/bridge/runner/claim", json={}, headers={"Authorization": "Bearer " + TOKEN}
    )
    assert response.status_code == 422


def test_profile_url_rejected_without_fetch_or_sql(boundary, monkeypatch):
    import socket

    client, directory = boundary
    write_profile(directory)
    monkeypatch.setattr(
        socket, "create_connection", lambda *a, **kw: pytest.fail("network forbidden")
    )
    response = client.post(
        "/api/bridge/runs",
        headers=browser_headers(),
        json={
            "idempotency_key": str(uuid4()),
            "requested_slack_permalink": "https://evil.test/a",
        },
    )
    assert response.status_code == 422
    assert "evil.test" not in response.text


def test_disabled_status_no_secret_no_sql(boundary):
    client, _ = boundary
    # Missing profile never reaches a DB, and missing token remains generic.
    response = client.get("/api/bridge/status", headers=browser_headers())
    assert set(response.json()) == {"mode", "enabled", "configuration", "reason"}
    assert (
        client.get("/api/bridge/status?token=" + TOKEN, headers=browser_headers()).status_code
        == 422
    )
