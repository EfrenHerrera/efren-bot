from pydantic import BaseModel

from efren_bot.schemas import DemoEventInput


class DemoFixture(BaseModel):
    id: str
    label: str
    event: DemoEventInput


def demo_fixtures() -> list[DemoFixture]:
    """Fresh, stable synthetic inputs; no clock, UUID generation or external data."""
    shared = {
        "workspace_id": "demo-workspace",
        "channel_id": "demo-channel",
        "actor_id": "ana",
        "source_url": None,
    }
    return [
        DemoFixture(
            id="request_video",
            label="Petición de video sin contexto",
            event=DemoEventInput(
                **shared,
                event_id="evt-request-video-001",
                message_id="msg-video-001",
                thread_id="msg-video-001",
                text="@efren sube el video",
                occurred_at="2026-01-15T15:00:00Z",
            ),
        ),
        DemoFixture(
            id="thanks",
            label="Agradecimiento informativo",
            event=DemoEventInput(
                **shared,
                event_id="evt-thanks-001",
                message_id="msg-thanks-001",
                thread_id="msg-thanks-001",
                text="@efren gracias",
                occurred_at="2026-01-15T15:01:00Z",
            ),
        ),
        DemoFixture(
            id="reply",
            label="Respuesta sin nueva mención",
            event=DemoEventInput(
                **shared,
                event_id="evt-reply-001",
                message_id="msg-video-reply-001",
                thread_id="msg-video-001",
                text="Es el de la sesión del lunes.",
                occurred_at="2026-01-15T15:02:00Z",
            ),
        ),
    ]
