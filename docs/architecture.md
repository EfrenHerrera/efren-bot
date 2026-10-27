# Arquitectura y alcance

## Incremento revisiones de MR

Mensajes nuevos de collection → `mr_review_requests` → N `mr_review_items` independientes
→ snapshots/planes/informes/propuestas → `mr_review_entries` con decisiones humanas.
Cinco tablas en `0009_mr_review`; API solo persiste/controla. Runner host con advisory
lock propio usa `glab` allowlist y generación oficial text-only deny-all; jamás ejecuta
código de MRs. Publicación individual admite versión exacta y estado durable en vuelo;
demo histórica aislada siempre read-only. [Contrato y límites](mr-review.md).

## Incremento soporte nuevo (parcial, fuentes pendientes)

`collection_messages → support_intakes → support_cases/support_entries` añade corte
independiente y dedupe lógico; API protegida solo persiste/controla. Runner host con
advisory lock propio llama generación oficial sin herramientas ni fallback. Web muestra
avances/chat/pausa y preliminar explícitamente solo Slack. No hay adaptadores CloudWatch/
GitLab/local habilitados: estado blocked, no investigación técnica completada. No toca
worker, provider ni tablas fixture/work. Contrato vigente en `docs/support.md`.

## Incremento vigente: recolección Slack local

La corrección vigente cambia la unidad de navegación a conversación, agrupada solo
por referencias explícitas de las variantes guardadas. Menciones literales en todo
el contexto no equivalen a encargos. Asuntos humanos opcionales en tablas collection
independientes, con referencias lógicas a mensajes y revisiones/idempotencia; ni
clasificador automático ni tablas de tareas fixture/work se usan para este flujo.

Incremento de bandeja autorizado: mensajes lógicos paginados con representaciones
conservadas, anotaciones humanas por identidad externa compuesta y sin mutar el
texto. Importador host offline del archivo aprobado de cinco canales, sin red ni
avance de recolección. Configuración de canales en collection_control, congelada
en collection_runs al encolar. API protegida nunca lee archivos del host. Ningún
clasificador/modelo ni creación de tareas en este incremento.

La solicitud posterior de finalizar recolección reemplaza solo la pantalla en blanco
por controles de colección. Web -> /api/collection -> tablas collection; runner host
con lock PostgreSQL -> CLI/API oficial OpenCode -> lecturas Slack aprobadas. El
runner se ejecuta fuera de Docker, sin prompts/modelos ni credenciales copiadas.
Pausa/reanudación persistentes; manual inmediato también pausado; sin overlaps.
No inicia interpretación ni tareas, no altera el worker fixture ni el trabajo
sintético. Las descripciones de pantalla vacía más abajo son evidencia histórica,
no el comportamiento vigente. [Contrato y límites](slack-collection.md).

## Base local, no V1 completa

Estado de fuente tras el retiro autorizado del 2026-10-24: web completamente en
blanco, sin clientes, hooks, paneles ni proxy API. La aceptación de despliegue/navegador
es separada. El recorrido histórico mensaje simulado -> evento persistido -> worker
-> pendiente conserva su backend, datos y evidencia, no su interfaz anterior.
No hay especificación V1 completa versionada en este repo;
estos documentos fijan únicamente el contrato necesario para construir esta base.

| Base local acordada | Futuro V1, fuera de esta entrega |
| --- | --- |
| Un dueño demo `efren`, sin autenticación multiusuario | Identidad, permisos y operación multiusuario |
| Proveedor fijo `fixture`, eventos sintéticos | Conectores y verificaciones de proveedores reales |
| Clasificador determinista rotulado como demo | Modelos, evaluación y clasificación más amplia |
| PostgreSQL + outbox, worker sin red | Efectos externos, automatizaciones, trabajos largos |
| Scaffold React/Vite vacío; trazabilidad conservada en backend | Nueva experiencia, sincronizaciones y despliegue |
| Extensión pgvector y prueba SQL sintética | Embeddings, búsqueda semántica y RAG |

No se importan datos desde URLs, no se publican respuestas ni se ejecuta código autónomo.
La ausencia de auth solo es aceptable en loopback para una demo con datos inventados.

## Componentes y fronteras

```text
Browser -> Vite/React :5173 (página en blanco; sin acceso a API)

FastAPI :8000 ------> ingesta backend compartida <------ CLI demo
                               |
                    PostgreSQL 17 + pgvector
                     eventos + mensajes + outbox
                               |
                    worker Python (poll local)
                      tareas + actividades

FastAPI /api/work -> tablas de trabajo <- work-worker DB-only
```

- `src/efren_bot`: configuración, modelos, ingesta, clasificación y proyección.
  Entradas: `efren_bot.api:app`, `python -m efren_bot.worker`, `python -m efren_bot.demo`.
  La API exporta el objeto ASGI `app` construido por una factory `create_app()`.
- Pydantic 2 valida en la frontera; SQLAlchemy 2 síncrono/psycopg 3 y Alembic
  administran DB. No mantener sesiones de DB abiertas entre peticiones o ciclos.
- PostgreSQL usa UUID nativo y `timestamptz`, constraints de unicidad externa y FKs.
  La migración inicial habilita `CREATE EXTENSION IF NOT EXISTS vector`.
- API/worker comparten imagen backend sin mounts. Compose espera DB sana, ejecuta
  migración one-shot y solo después inicia API/worker. Web espera readiness de API.
- Frontend: React/TypeScript/Vite, imagen `node:26-bookworm-slim`,
  `apps/web/Dockerfile`, `npm ci` con lock. Sin volumen que oculte `node_modules`.
  `App` retorna null; estilos blancos mínimos, sin contenido oculto. Vite conserva
  hosts locales, puerto estricto y CORS deshabilitado, sin proxy ni timezone de web.
  Las variables históricas que Compose todavía pasa a web no tienen consumidor.

## Transacciones y recuperación

1. **Ingesta**: validar -> comprobar identidades/contenido -> insertar evento, mensaje
   y outbox en una transacción -> commit -> responder 202. Los constraints resuelven
   carreras: tras conflicto único, releer y comparar; nunca responder antes del commit.
   Reintentos/alias exactos devuelven 200 sin nuevo trabajo; colisiones devuelven 409.
2. **Consumo local**: en una transacción corta seleccionar un outbox elegible con
   `FOR UPDATE SKIP LOCKED`, proyectar tarea/actividad y marcar procesado/ack **antes
   del mismo commit**. Tomar uno por ciclo simplifica recuperación y orden. No confirmar
   una marca de «procesando» antes de proyectar; no realizar red, esperas ni sleep
   dentro de la transacción. Dormir entre polls, fuera de la sesión.
3. Si el proceso cae, PostgreSQL revierte todo y libera locks al cerrar la conexión;
   otro consumidor puede retomarlo. Si cayó después del commit, el ack evita repetición.
   Constraints de proyección (actividad y tarea por mensaje fuente) protegen duplicados;
   no se fusionan mensajes por compartir hilo.
4. Serializar también la raíz `(provider, workspace, channel, thread_id)` para evitar
   carreras entre eventos distintos del mismo hilo (lock transaccional/registro de raíz).
   Una respuesta a una raíz todavía no proyectada se difiere sin perderla; no crear
   una tarea huérfana. Orden local por aceptación y UUID como desempate.
5. Error controlado: rollback completo del savepoint de proyección; la transacción
   exterior conserva el claim lock, incrementa intentos y fija próximo intento con
   backoff limitado. Máximo 5 intentos y estado
   `failed` visible; no bucle ocupado. Crash puro no deja una proyección parcial.

Este outbox es una cola transaccional **local**, no una promesa de exactly-once sobre
red. Con procesamiento lento, llamadas externas o efectos fuera de PostgreSQL habrá
que separar claim/ejecución/ack, añadir leases con expiración, reintentos e idempotencia
de destino. No introducir leases innecesarios en la transacción local actual.

## Invariantes de demo

- Sin LLM, embeddings remotos ni reconciliación semántica. Dedupe exacta no implica
  fusionar dos mensajes parecidos. Ver [identidad y HTTP](contract.md).
- Petición del fixture de video: `needs_context`, acción concreta para pedir video/destino.
  Agradecimiento: actividad sin tarea. Reply a la misma raíz, incluso sin `@efren`:
  actualizar `has_new_reply`, registrar mensaje/actividad, nunca cerrar ni inventar `done`.
- `APP_ENV` distinto de `local` impide iniciar API, worker y demo; configuración
  inválida falla temprano. Esto no sustituye autenticación ni permite exposición pública.

## Incremento A: persistencia de trabajo sintético separada

`/api/work` -> cinco tablas nuevas -> `python -m efren_bot.work_worker` opt-in.
El fake DB-only prepara ASK_CONTEXT y se detiene en aprobación simulada; aprobar
encola finalización local, rechazar nunca publica. Job lock + savepoint conservan
historia/intentos/checkpoint sin proyecciones parciales; no leases de trabajo remoto.
No se comparte cola ni se cambia Task/Activity/Bridge. [Contrato, ejemplos y pruebas](synthetic-work.md).
Código fuente y TESTDB no equivalen por sí solos a migrar/iniciar el runtime principal.
API y navegador nunca arrancan el worker. Compose sí define explícitamente el servicio
`work-worker`, dependiente de DB/migración y con la misma imagen backend y entorno
local que API, sin puertos, mounts ni credenciales nuevas. La activación adicional
autorizada del 2026-10-24 migró la principal a `0003_synthetic_work`, recreó solo API/web
y añadió este servicio; conservó DB/test-db/worker fixture/migrate históricos.

Antes del retiro web se observó `waiting_human`, reinicio exclusivo del nuevo worker y recarga con detalle
persistido idéntico, luego aprobación simulada exacta y `delivered`/`succeeded` sin
alterar las ocho tablas originales. `/readyz` sigue siendo solo SELECT 1: la evidencia
de ejecución es el progreso real del job, no readiness. Todo sigue local, sintético
y loopback; no implica agentes reales, conectores, B–F ni operación 24/7.
Git y riesgo formal siguen diferidos; esta activación no autoriza otras operaciones
ni declara verified/done global.
[Evidencia y límites de la activación](synthetic-work.md#activación-local-autorizada--2026-10-24).
