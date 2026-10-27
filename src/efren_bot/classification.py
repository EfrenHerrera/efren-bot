from dataclasses import dataclass
from typing import Literal

from efren_bot.fixtures import demo_fixtures
from efren_bot.schemas import DemoEventInput

ASK_CONTEXT = "Pedir qué video debe subirse y a qué destino"
REVIEW_REPLY = "Revisar la respuesta del hilo y confirmar qué video y a qué destino debe subirse"


@dataclass(frozen=True)
class Classification:
    intent: Literal["task_request", "acknowledgement", "thread_reply", "ignored"]
    summary: str


RESULTS = {
    "request_video": Classification("task_request", "Demo: petición de video sin video ni destino"),
    "thanks": Classification("acknowledgement", "Demo: agradecimiento informativo; sin tarea"),
    "reply": Classification("thread_reply", "Demo: nueva respuesta en el hilo; revisión pendiente"),
}


def classify(data: DemoEventInput) -> Classification:
    """Not NLP. Only the exact three canonical synthetic messages are understood.

    Event aliases do not change message identity. Everything else is accepted as
    evidence, but requires human review; we make no general interpretation claim.
    """
    for fixture in demo_fixtures():
        if data.canonical_payload(message=True) == fixture.event.canonical_payload(message=True):
            return RESULTS[fixture.id]
    return Classification(
        "ignored", "Fuera de los fixtures demo: requiere revisión manual; sin tarea"
    )
