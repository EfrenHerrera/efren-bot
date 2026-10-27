import pytest
from pydantic import ValidationError

from efren_bot.api import create_app
from efren_bot.classification import ASK_CONTEXT, classify
from efren_bot.demo import main as demo_main
from efren_bot.fixtures import demo_fixtures
from efren_bot.schemas import DemoEventInput
from efren_bot.worker import Worker


def test_stable_literal_fixtures(event_input):
    fixtures = demo_fixtures()
    assert [f.id for f in fixtures] == ["request_video", "thanks", "reply"]
    assert fixtures[0].event == event_input
    assert fixtures[0].event.text == "@efren sube el video"
    assert fixtures[1].event.text == "@efren gracias"
    assert fixtures[2].event.text == "Es el de la sesión del lunes."
    assert fixtures[2].event.thread_id == fixtures[0].event.message_id
    assert "@efren" not in fixtures[2].event.text
    assert [classify(f.event).intent for f in fixtures] == [
        "task_request",
        "acknowledgement",
        "thread_reply",
    ]
    assert ASK_CONTEXT == "Pedir qué video debe subirse y a qué destino"
    assert demo_fixtures() == fixtures
    fixtures[0].event.text = "mutated"
    assert demo_fixtures()[0].event == event_input


@pytest.mark.parametrize(
    "patch",
    [
        {"text": "@efren sube el video a youtube"},
        {"text": "@efren SubE el video"},
        {"text": "@efren gracias por ayudarme"},
        {"message_id": "a-separate-request"},
        {"channel_id": "another-channel"},
        {"actor_id": "someone-else"},
    ],
)
def test_not_a_general_classifier(event_input, patch):
    data = DemoEventInput.model_validate(event_input.model_dump() | patch)
    assert classify(data).intent == "ignored"
    assert "revisión manual" in classify(data).summary


def test_event_alias_does_not_change_classification(event_input):
    data = DemoEventInput.model_validate(event_input.model_dump() | {"event_id": "alias"})
    assert classify(data).intent == "task_request"


@pytest.mark.parametrize("factory", [create_app, Worker, lambda: demo_main([])])
def test_construction_guards_local_mode(monkeypatch, factory):
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(ValidationError):
        factory()
