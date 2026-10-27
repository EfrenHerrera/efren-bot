import pytest
from conftest import TEST_URL, require_test_database
from pydantic import ValidationError

from efren_bot.config import Settings
from efren_bot.schemas import DemoEventInput


@pytest.mark.parametrize(
    "field,value",
    [
        ("event_id", " "),
        ("message_id", 123),
        ("actor_id", "x" * 201),
        ("text", "\n"),
        ("text", "x" * 16001),
        ("text", "null\x00text"),
        ("event_id", "null\x00id"),
        ("occurred_at", "2026-01-15T15:00:00"),
        ("occurred_at", 1768489200),
        ("occurred_at", "1768489200"),
        ("source_url", "file:///etc/passwd"),
        ("source_url", "javascript:alert(1)"),
        ("source_url", "https://example.test/" + "x" * 2050),
        ("provider", "fixture"),
        ("owner_id", "efren"),
        ("owner", "someone"),
    ],
)
def test_invalid_input(event_input, field, value):
    payload = event_input.model_dump(mode="json")
    payload[field] = value
    with pytest.raises(ValidationError):
        DemoEventInput.model_validate(payload)


def test_canonical_input(event_input):
    payload = dict(reversed(list(event_input.model_dump(mode="json").items())))
    payload["occurred_at"] = "2026-01-15T09:00:00-06:00"
    payload.pop("source_url")
    assert (
        DemoEventInput.model_validate(payload).canonical_payload()
        == event_input.canonical_payload()
    )
    payload["text"] = " @efren sube el video "
    assert DemoEventInput.model_validate(payload).text == payload["text"]
    payload["event_id"] = "a:b|C"
    assert DemoEventInput.model_validate(payload).event_id == "a:b|C"


@pytest.mark.parametrize(
    "name,value",
    [
        ("app_env", "prod"),
        ("demo_owner_id", "someone"),
        ("app_timezone", "No/SuchZone"),
        ("worker_poll_interval_seconds", 0.09),
        ("worker_poll_interval_seconds", 61),
        ("worker_poll_interval_seconds", float("nan")),
        ("worker_poll_interval_seconds", float("inf")),
        ("database_url", "sqlite:///local.db"),
        ("database_url", "postgresql+psycopg://user@external.example/demo"),
        ("database_url", TEST_URL + "?host=external.example"),
    ],
)
def test_invalid_settings(name, value):
    with pytest.raises(ValidationError):
        Settings(**{name: value})


def test_environment_guard(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize(
    "url",
    [
        TEST_URL.replace("efren_bot_test", "efren_bot"),
        TEST_URL.replace("127.0.0.1", "db"),
        TEST_URL.replace(":55433/", ":55432/"),
        TEST_URL.replace(":55433/", "/"),
        TEST_URL + "?host=external.example",
    ],
)
def test_database_guard(url):
    with pytest.raises(ValueError):
        require_test_database(url)


def test_valid_settings():
    assert Settings().worker_poll_interval_seconds == 1.0
    require_test_database(TEST_URL)
