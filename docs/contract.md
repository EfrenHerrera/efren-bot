# Contrato de la base local

Incremento autorizado posterior: [recolección Slack local](slack-collection.md),
con endpoints/tablas independientes. No modifica el contrato fixture de este documento.
Revisiones de MR tienen [contrato separado](mr-review.md), corte/cola/ejecutor propios;
su autorización no amplía fixture/work ni fuentes de soporte.

Contrato implementado para esta base local, no una V1 completa. JSON sobre HTTP, strings
UUID para referencias internas y fechas ISO 8601 con zona, salida siempre UTC (`Z`
o `+00:00`). No hay autenticación multiusuario ni fuentes reales.

## Identidad canónica

La inspección inicial no encontró helpers, modelos ni identificadores previos.

| Concepto | Identidad y significado |
| --- | --- |
| Entrega | Un intento HTTP; varios intentos pueden llevar el mismo evento. No es un mensaje nuevo. |
| Evento aceptado | PK UUID nativo (UUID4); identidad externa única `(provider, workspace_id, channel_id, event_id)`. |
| Mensaje | PK UUID nativo; único `(provider, workspace_id, channel_id, message_id)`. Puede aparecer en eventos alias distintos. |
| Hilo | Raíz externa string `thread_id`; en raíz coincide con su `message_id`, en replies conserva el de la raíz. Scope `(provider, workspace_id, channel_id, thread_id)`. |
| Tarea / actividad / outbox | PK UUID nativo; FKs UUID a eventos/mensajes/tareas, no strings externos convertidos a UUID. |

IDs externos no vacíos, opacos, sensibles a mayúsculas; no parsear Slack timestamps,
no concatenar con separadores ambiguos: usar columnas/tuplas compuestas. El proveedor
lo fija el servidor a `fixture` y dueño a `DEMO_OWNER_ID=efren`; el cliente no puede
enviar `provider`, `owner` ni campos adicionales. No buscar identidades de otros tenants.

El `event_id` **de entrada** es string externo. `source_event_id` de una tarea y
`event_id` en actividades/mensajes **de salida** son UUID internos del evento canónico,
consultables en `GET /api/events/{uuid}`. El payload guardado conserva los IDs externos.

## Ingesta

`POST /api/demo/events`, modelo Pydantic con extras prohibidos:

```json
{
  "event_id": "evt-request-video-001",
  "workspace_id": "demo-workspace",
  "channel_id": "demo-channel",
  "message_id": "msg-video-001",
  "thread_id": "msg-video-001",
  "actor_id": "ana",
  "text": "@efren sube el video",
  "occurred_at": "2026-01-15T15:00:00Z",
  "source_url": null
}
```

Todos los campos salvo `source_url` son obligatorios; IDs no blancos, `text` no vacío.
`occurred_at` debe incluir zona (Pydantic `AwareDatetime`), se normaliza a UTC.
`source_url` es `http`/`https` válido o null (omisión equivale a null); nunca `file:`,
`javascript:` u otro esquema. Es metadato: backend/worker no lo visitan ni hacen previews.
El panel puede mostrar un enlace seguro (`noopener noreferrer`), no cargarlo automáticamente.

Respuesta `{ "id": "<UUID interno del evento aceptado>", "status": "accepted|duplicate" }`:

- **202** `accepted`: primer mensaje, evento + mensaje + outbox guardados atómicamente.
- **200** `duplicate`: misma identidad de evento y mismo payload normalizado. Mismo
  UUID, sin nuevos eventos/outbox/actividades/tareas.
- **200** `duplicate`: otro `event_id` para el mismo mensaje exacto (comparar todos
  los campos salvo `event_id`). Guardar el evento alias y su payload con UUID propio,
  enlazado al mensaje canónico, **sin** nuevo outbox. Permite detectar futuros conflictos
  del alias; tarea/actividad conservan el primer evento como fuente.
- **409**: identidad de evento reutilizada con otro payload, o identidad de mensaje
  reutilizada con contenido distinto (incluye actor, raíz, fecha, texto y fuente).
  No persistir cambios parciales ni sobrescribir contenido. Ediciones no se soportan.
- **422**: validación; **503**: DB indisponible, sin afirmar aceptación.

Comparación exacta sobre modelo validado serializado canónicamente (claves ordenadas,
UTC, defaults explícitos), no bytes HTTP ni igualdad semántica. Orden de claves y offsets
equivalentes no generan colisión; no recortar texto ni cambiar mayúsculas. Constraints
únicos más comparación posterior al conflicto deben cubrir solicitudes concurrentes.

## Consultas

`GET /api/overview` (200; DB fallida -> 503, no `database:ok` ficticio):

```text
{
  mode: "local_demo",
  classifier: "deterministic_demo",
  database: "ok",
  counts: {tasks, needs_context, ready, updates, pending_events, failed_events},
  tasks: [Task],
  activities: [Activity],
  integrations: []
}
Task = {
  id: UUID, title: string, state: "needs_context" | "ready",
  next_action: string, source_url: http(s) | null,
  source_event_id: UUID, thread_id: string,
  updated_at: UTC ISO, has_new_reply: boolean
}
Activity = {
  id: UUID, intent: string, summary: string,
  event_id: UUID, thread_id: string, occurred_at: UTC ISO
}
```

Contadores enteros no negativos: `tasks` total; `needs_context`/`ready` por estado;
`updates` tareas con `has_new_reply`; `pending_events` outbox no procesado ni agotado
(incluye backoff); `failed_events` outbox agotado. Conteos y listas de una lectura
coherente. Base pequeña sin paginación: tareas por `updated_at DESC, id`, actividades
por `occurred_at DESC, id`. `integrations` siempre vacío, no tarjetas de integraciones falsas.

`GET /api/tasks/{uuid}` -> `{ "task": Task, "messages": [Message] }`:

```text
Message = {event_id: UUID, actor_id: string, text: string,
           occurred_at: UTC ISO, source_url: http(s) | null}
```

Mensajes únicos de la raíz y sus replies, ordenados por `occurred_at ASC, id`;
no duplicar entregas/alias. Reply actualiza `has_new_reply=true` y `updated_at`;
consultar detalle no lo limpia (no existe endpoint de marcado como leído en esta base).

`GET /api/events/{uuid}` -> `{id: UUID, provider: "fixture", owner_id: "efren",
payload: DemoEventInput, accepted_at: UTC ISO}`. Mostrar payload validado aceptado,
no una nueva consulta al proveedor. UUID desconocido -> 404; UUID mal formado -> 422.
La misma regla aplica a detalle de tarea.

`GET /healthz` -> 200 `{"status":"ok"}`, liveness sin tocar DB.
`GET /readyz` -> 200 `{"status":"ok","database":"ok"}` tras `SELECT 1`,
503 si falla; no filtrar credenciales ni detalles de conexión.

## Fixtures y clasificación mínima

`GET /api/demo/fixtures` -> lista `[{id: string, label: string, event: DemoEventInput}]`.
Web envía ese `event` a `POST /api/demo/events`; la CLI usa los mismos fixtures y la
ingesta backend compartida directamente, sin HTTP ni procesamiento implícito. No existe
endpoint de importar una URL ni un fetch arbitrario. Fixtures estables y sintéticas:

| id | Mensaje / raíz | Resultado al procesar |
| --- | --- | --- |
| `request_video` | `msg-video-001`, raíz igual; `@efren sube el video` | Una tarea `needs_context`, acción «Pedir qué video debe subirse y a qué destino». |
| `thanks` | `msg-thanks-001`, raíz igual; `@efren gracias` | Actividad, ninguna tarea. |
| `reply` | `msg-video-reply-001`, raíz `msg-video-001`; `Es el de la sesión del lunes.` | Misma tarea, sin mención nueva: mensaje/actividad y `has_new_reply=true`; no cerrar ni cambiar estado automáticamente. |

IDs de evento estables `evt-request-video-001`, `evt-thanks-001`, `evt-reply-001`;
workspace/canal `demo-workspace`/`demo-channel`, actor `ana`, fechas conscientes
`2026-01-15T15:00:00Z`, `15:01:00Z`, `15:02:00Z`; fuentes null. Un fixture repetido
no debe regenerar IDs/fechas. Intents demo: `task_request`, `acknowledgement`,
`thread_reply`, `ignored` (otros textos no crean tareas). Ejecutar primero la petición
y luego reply; si el worker aún no proyectó la raíz, diferir el reply. No generalizar
esta heurística a lenguaje natural, no crear `done`, no hacer merge semántico.

## Incremento independiente: trabajo sintético

Las rutas `/api/work` y el worker opt-in `efren_bot.work_worker` implementan un
expediente/job/historia/artefacto/aprobación **separado**, únicamente para receta
`request_video` v1. Contrato cerrado, ejemplos íntegros, recuperación y límites:
[Trabajo sintético persistente](synthetic-work.md). No sustituye este contrato ni
amplía clasificación/fixtures; `work.delivered` no es cierre de Task o de fuente.
