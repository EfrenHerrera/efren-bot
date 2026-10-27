# Trabajo sintético persistente · incremento A

> **Retiro de frontend · 2026-10-24 (posterior a la aceptación de abajo).**
> Se eliminaron de la web todas las simulaciones, bandeja y paneles, incluidos los
> clientes/hooks/proxy y sus pruebas; la fuente actual deja la página en blanco.
> El backend A, la API, workers, migración principal `0003_synthetic_work` y datos
> existentes se conservan. Este documento mantiene íntegros el contrato, ledger,
> ejemplos JSON y corte de aceptación previos: sus botones, conteos y 212 pruebas
> web describen aquel momento, no controles ni suite actuales. Las 464 Python son
> también evidencia histórica, no una ejecución nueva de este retiro. No inferir
> el inventario actual de expedientes desde el caso único de aceptación.
> Cambiar fuente no acredita despliegue ni aceptación de página vacía; esa integración
> y preservación runtime se comprueban por separado. Ver [estado web](../apps/web/README.md).

Contrato implementado y activo en el runtime local tras autorización adicional del
2026-10-24, **no una V1 de agentes ni un despliegue de producción**.
Solo usa el fixture canónico `request_video`, receta versión 1 y ejecutor
`fake_db_v1`. No cambia la ingesta/outbox/Task/Activity originales ni el Bridge.
No introduce modelos, embeddings, conectores, comandos, n8n o efectos externos.

La API y el panel no inician este worker. Encolar no acredita disponibilidad del
proceso. `/readyz` conserva únicamente `SELECT 1`: no acredita tablas nuevas,
worker nuevo, backlog procesado ni aprobación humana autenticada.

## Identidad y wire congelado

- UUID nativos para expediente, job, historia, intento, artefacto y aprobación;
  strings UUID en JSON. El evento fuente `evt-request-video-001` sigue siendo un
  identificador opaco del fixture: no es UUID, tarea Notion ni clave KNF.
- `source_snapshot` es `DemoEventInput.canonical_payload()` exacto, con fecha fuente
  UTC estable. `created_at`/`updated_at`/decisión/intentos usan el reloj actual aware
  UTC. No convertir el tiempo fuente en tiempo de ejecución.
- SHA256 estándar sobre JSON canónico existente: claves ordenadas, separadores
  compactos, UTF-8 sin escapes ASCII. Es una comprobación de contenido, **no firma,
  autenticación ni protección frente a un administrador que altere toda la DB**.
- Dueño/actor `efren` es el dueño demo local, no identidad humana verificada.
  Entradas con campos adicionales (`owner`, URLs, comandos, estados, snapshots)
  se rechazan; el servidor copia el fixture, nunca visita URLs.

| Ruta | Entrada / salida |
| --- | --- |
| `POST /api/work` | `{idempotency_key: UUID, fixture_id: request_video\|thanks\|reply}`. 202 `{status:accepted,detail}`; replay exacto 200 `{status:duplicate,detail}`. |
| `GET /api/work` | `{mode:synthetic_work,executor:fake_db_v1,works:WorkSummary[]}`; últimos 50 por `created_at DESC,id ASC`. |
| `GET /api/work/{work_id}` | `WorkDetail`; snapshot coherente en transacción `REPEATABLE READ`. |
| `POST /api/work/{work_id}/approvals/{approval_id}/decision` | `{decision:approve\|reject,artifact_sha256:hex64,reason:string}` -> 200 `{status:recorded\|duplicate,detail}`. |

Un nuevo `thanks`/`reply` obtiene 422 `unsupported_recipe`. La misma clave ya
aceptada con otro fixture obtiene 409 `idempotency_conflict` **antes** de buscar
receta. Creación concurrente igual conserva un expediente/job/historia inicial.
Creación y comprobación de conflictos son transaccionales: no quedan huérfanos.

Decisión: razón exacta, no blanca, 1–500 caracteres, sin NUL; SHA256 hexadecimal
minúsculo de 64 caracteres. Recurso ajeno/desconocido 404; hash distinto o replay
con decisión/motivo distintos 409. Replay exacto conserva historia y timestamps,
incluso después de finalizar. El cliente debe conservar clave/cuerpo ante recepción
incierta; no asumir fallo/no recepción ni generar silenciosamente otra clave.
Validación/UUID inválido 422; DB/tablas indisponibles 503 sanitizado sin SQL o URL.

DTOs cerrados en `src/efren_bot/work/contracts.py`:

```text
WorkSummary = {id,fixture_id,recipe_version,owner_id,state,job_status,created_at,updated_at}
  state = active|waiting|delivered; job_status = queued|waiting_human|succeeded|failed
WorkDetail = {work,job,history,artifacts,approvals}
  work = WorkSummary + {source_snapshot:DemoEventInput,source_sha256}
job = {id,work_id,status,checkpoint,attempt_count,failure_count,available_at,last_error_code}
checkpoint = {version:1,phase,source_sha256,proposal_artifact_id,approval_id,final_artifact_id,next_action}
  phase = prepare|await_approval|finalize|complete|rejected|failed
  next_action = run_prepare|human_decision|run_finalize|none
history[] = {id,sequence,kind,actor_id,occurred_at,attempt_id,attempt_number,data}
  kind = work_created|proposal_prepared|approval_recorded|simulation_finished|attempt_failed
  data = {reason,alternatives:string[],checks,pending:string[],source_fixture_id:request_video,
          source_sha256,artifact_id,approval_id,error_code}
checks[] = {name,status:passed|failed|not_run,detail}
artifacts[] = {id,job_id,attempt_id,version,kind:proposal|result,content,sha256,created_at}
  content = {title,summary,action:ASK_CONTEXT|SIMULATION_COMPLETE,missing_context:string[],checks,
             pending:string[],source_fixture_id:request_video,source_sha256,no_external_effects:true}
approvals[] = {id,job_id,artifact_id,artifact_sha256,status:pending|approved|rejected,
               decision_reason,decided_by,created_at,decided_at}
```

IDs de checkpoint, historia `artifact_id`/`approval_id`/`attempt_id`/`attempt_number`,
error y datos de decisión son null cuando todavía no existen. Historia ordenada por
`sequence ASC`, artefactos por `version ASC`, aprobaciones por `created_at,id`.

## Persistencia y recuperación real del alcance A

Migración aditiva `0003_synthetic_work` después de `0002_bridge`: cinco tablas
`work_items`, `work_jobs`, `work_history`, `work_artifacts`, `work_approvals`.
Un job por work y clave de solicitud única. Intento UUID único en historia (sin
sexta tabla), FK desde artefacto al intento ya insertado; versión única por job.
Estados/contadores tienen constraints. No existen FKs a fixtures/proyecciones/Bridge.

1. Claim de un job elegible `queued` con `FOR UPDATE SKIP LOCKED`, luego lectura de
   work/artefactos/aprobación. Decisiones adquieren primero el mismo lock de job.
2. Preparar valida receta, snapshot/digest y checkpoint. En una transacción corta
   inserta historia de intento, propuesta inmutable por API, aprobación pendiente y
   checkpoint `await_approval`. Acción **ASK_CONTEXT**, conserva video/destino faltantes.
3. `waiting_human` no es elegible: ni busy-loop, ni conexión/lock retenido esperando
   al usuario. Aprobación simulada exacta encola `finalize`; rechazo marca job failed,
   error `approval_rejected`, checkpoint `rejected`, work waiting; nunca finaliza.
4. Finalización revalida fuente/checkpoint, contenido completo y SHA de la propuesta
   original, relación aprobación/artefacto/job y estado **actualmente approved**.
   Incluso cambiar contenido y recalcular sus hashes no lo convierte en otra receta.
   Registra resultado **SIMULATION_COMPLETE**, job succeeded/work delivered. Conserva
   contexto pendiente y checks `external_publication`/`real_tests` en **not_run**.
   No publicó un video, no ejecutó tests y no cerró ninguna fuente o Task.
5. Intento total se flushea en la transacción exterior antes de `begin_nested()`;
   todos los efectos del paso quedan dentro del savepoint. Fallo revierte TODO el
   paso; se recargan objetos expirados sin `Session.rollback()` exterior. Con el
   claim aún bloqueado se guarda intento fallido, código fijo seguro y backoff
   1/2/4/8/16 s; máximo cinco fallos. Corrupción/versión/receta/checkpoint inválidos
   fallan cerrado (`state_invalid`), sin intentar publicación ni reparar evidencia.
6. Crash anterior a commit revierte intento/artefacto/aprobación/checkpoint y libera
   lock; otro consumidor retoma. Tras commit, checkpoints evitan reproponer/finalizar.
   No se afirma lease/fencing, ejecución larga remota o exactly-once de red.

## Proceso separado y operación local

La entrega inicial fue solo fuente/pruebas. La autorización adicional del 2026-10-24
permitió migrar la principal e iniciar explícitamente `work-worker` en Compose.
Ese servicio ya está ejecutándose en el stack activado: no iniciar un duplicado en
el host para usar el panel. API y navegador no crean ni arrancan procesos worker.

Para una operación **nativa alternativa, sin ese worker Docker**, con autorización
propia y la DB local elegida **ya migrada**, los comandos siguen siendo:

```sh
uv run --frozen python -m efren_bot.work_worker --once
# Sin --once: loop local independiente, sleep sin transacción/conexión retenida.
uv run --frozen python -m efren_bot.work_worker
```

`Settings()` rechaza `APP_ENV` no local antes de crear engine. El fake no lanza
subprocesos ni red; solo el proceso worker de pruebas se lanza explícitamente desde
tests. No hay autostart en API/web; Compose define el servicio explícito `work-worker`,
que comparte imagen backend/entorno local, depende de DB/migración y no añade puertos,
mounts ni credenciales. Logs worker: estado/IDs/contadores/código
seguro, nunca DB URL, payload fuente completo o texto de excepción SQL.
**En el corte inicial de implementación** no se ejecutaron comandos contra DB
principal, migración principal ni inicio de servicios. Cambiar fuente no actualizó
automáticamente el runtime previo; la integración autorizada y observada posterior
se registra al final, separada de las pruebas históricas.

## Evidencia de comprobaciones

Este ledger conserva el corte histórico de implementación/remediación en TESTDB;
sus pendientes y límites describen ese momento, no revierten la activación posterior.
Las **464 pruebas Python** finales y **212 web**, typecheck/build, son evidencia
histórica: no se repitieron durante la activación sin cambios funcionales de código.

Todas las comprobaciones se clasificaron antes como obligatorias por criterios A,
`.odd/synthetic-work-vertical.md` y AGENTS. Entorno explícito en cada comando:
`APP_ENV=local`, `UV_OFFLINE=1`, `DATABASE_URL` y `TEST_DATABASE_URL` fijadas a la DB
local de pruebas documentada (`efren_bot_test`, loopback, puerto **55433**). Sin
heredar URL desconocida. El guard comprobó identidad antes de migrar/truncar;
limpieza explícita conjunta de tablas propias, sin CASCADE. No se inició test-db.

Intentos conservados por rondas (checks independientes paralelos; prefijo de entorno
anterior omitido, sin secretos):

| Comando después del prefijo | Resultado |
| --- | --- |
| `uv run --frozen pytest -q tests/test_work_contracts.py::test_worker_local_guard_before_engine` | RED esperado: 1 fallo ImportError, módulo aún inexistente. Implementado módulo/guard; pasa en suites posteriores. |
| `uv run --frozen ruff check src tests migrations` | 12 E501; corrección mediante PATCH. |
| `uv run --frozen ruff format --check src tests migrations` | 7 archivos sin formato; corrección mediante PATCH, sin formatter-write. |
| `uv run --frozen pytest -m 'not integration' tests` | 374 PASS, 69 descartadas. |
| `uv run --frozen pytest -m integration tests` | 68 PASS, 1 fallo helper: otro job aprobado precedía al segundo prepare. Se prepararon ambos antes de aprobar. |
| `uv run --frozen ruff check src tests migrations` | PASS. |
| `uv run --frozen ruff format --check src tests migrations` | PASS, 56 archivos. |
| `uv run --frozen pytest -m integration tests` | 75 PASS, 383 descartadas, con cobertura adversarial adicional. |
| `uv run --frozen pytest -m 'not integration' tests` | 383 PASS, 75 descartadas. |
| `uv run --frozen ruff check src tests migrations` | PASS. |
| `uv run --frozen ruff format --check src tests migrations` | PASS, 56 archivos. |
| `uv run --frozen pytest -q -s tests/test_work_storage.py::test_wire_examples` | 1 PASS; produjo ambos ejemplos sintéticos íntegros de abajo. |
| `uv run --frozen pytest -m 'not integration' tests` | Final con validación de los ejemplos documentados: **384 PASS**, 75 descartadas. |
| `uv run --frozen ruff check src tests migrations` | PASS, pero prefijo DATABASE_URL tenía typo `psycg`; Ruff no conecta DB. Repetido correctamente abajo. |
| `uv run --frozen ruff format --check src tests migrations` | Final PASS, 56 archivos. |
| `uv run --frozen pytest -m integration tests` | Final **75 PASS**, 384 descartadas. URL correcta `psycopg`; guard/identidad antes de migrar/truncar. |
| `uv run --frozen ruff check src tests migrations` | Final PASS con prefijo correcto `psycopg`. |

Warning conservado: deprecación upstream Starlette TestClient/httpx; no se cambiaron
dependencias para ocultarlo. Las suites incluyen los 393 casos históricos; no se
afirma un baseline fresco anterior a este incremento. Metadata Alembic/ORM sin diff,
head TESTDB `0003_synthetic_work`. Sin head histórico hardcodeado que editar.

Cobertura nueva: extras/hash/motivo/versión, idempotencia concurrente/conflictos,
rollback create, propuesta única y espera sin conexión, replay/carreras de decisión,
rechazo, final local, error Python y DB tras flush en prepare/finalize, fallo en cada
inserción artefacto/aprobación, backoff y límite, corrupción de fuente/checkpoint y
contenido/hash/estado aprobado, consumidores competidores, ausencia de socket y
subprocess del fake, límites/orden de lista, HTTP 422/404/409/503 y repeatable-read.

Prueba de reinicio: nuevas factories ASGI/sesiones antes/después de aprobar **sin
reset de DB**, mismo work/job/historia, procesos OS worker nuevos `--once` para
preparar/finalizar y tercer proceso idle. No se reinició un servidor HTTP real.
Prueba crash: hijo propio pausa solo en test después de flush sin commit; otro
consumidor hace SKIP LOCKED; SIGKILL solo a ese PID; rollback y recuperación única
sin artefacto/aprobación parcial. La demo anterior conserva **1 Task needs_context
y 3 actividades** tras procesar los tres fixtures y completar trabajo nuevo.

Pendientes deliberados: review/riesgo formal exact-delta y Git; integración visual
del panel a cargo del writer web/padre. No se declara verified/done global.

### Remediación acotada de los dos P2 de revisión

Sin cambios al wire, esquema, GET con REPEATABLE READ ni aislamiento global:

- Replay de creación: el lookup inicial puede dejar `WorkItem` obsoleto en el
  identity map si un worker confirma entre lookup y detalle. Ahora se toma primero
  el lock del **job**, se actualiza el job cargado y se hace `refresh(WorkItem)`
  bajo ese lock; se conserva hasta construir todo el detalle y confirmar el replay.
  El orden sigue siendo job → dependientes, como worker/decisiones.
- CLI: `Worker()` se construye dentro del try. `ValidationError` de Settings produce
  solo `Invalid local configuration`, salida 1, sin excepción/URL/payload/traceback;
  finally cierra únicamente el worker construido. APP_ENV se valida antes del engine.

Regresiones reproducidas **antes** de corregir código: intercalado determinista
de commit worker entre lookup y replay para prepare y finalize (ambos detalles
incoherentes), y worker competidor durante lecturas de detalle (antes no había lock).
Después, replay coincide con el detalle persistido completo; el competidor devuelve
idle por SKIP LOCKED durante la lectura y puede preparar tras commit del replay.
CLI se ejecuta en hijos propios con URL **ficticia** y marcador de contraseña no
real; guard explícito hace fallar si se alcanza engine/red. Casos local/production
comprueban salida no cero, mensaje fijo y ausencia de marcador, URL, traceback o
stderr. Los cinco casos pasaron tras la corrección.

Ledger de esta remediación, **secuencial**, obligatorio por los dos P2/criterios A.
Mismo prefijo explícito APP_ENV local, UV_OFFLINE=1 y ambas variables DB fijadas a
TESTDB loopback 55433; el guard conserva current_database antes de migrar/truncar.
Los procesos CLI del test sustituyen solo su propio entorno con la URL ficticia.

| Comando después del prefijo | Resultado |
| --- | --- |
| `uv run --frozen pytest -q --tb=no tests/test_work_contracts.py::test_cli_rejected_settings_sanitized_before_engine_or_network` | RED: **2 FAIL** (local/production), salida capturada no impresa. |
| `uv run --frozen pytest -q --tb=short tests/test_work_storage.py::test_create_replay_refreshes_stale_work_after_worker_commit tests/test_work_storage.py::test_create_replay_holds_job_lock_through_detail_reads` | RED: **3 FAIL**, reproduciendo ambos estados obsoletos y falta de lock. |
| `uv run --frozen pytest -q --tb=no tests/test_work_contracts.py::test_cli_rejected_settings_sanitized_before_engine_or_network` | GREEN: **2 PASS**. |
| `uv run --frozen pytest -q --tb=short tests/test_work_storage.py::test_create_replay_refreshes_stale_work_after_worker_commit tests/test_work_storage.py::test_create_replay_holds_job_lock_through_detail_reads` | GREEN: **3 PASS**. |
| `uv run --frozen ruff check src tests migrations` | 1 E501 en aserción nueva; corregida mediante PATCH. |
| `uv run --frozen ruff format --check src tests migrations` | 1 archivo por la misma aserción; corregido mediante PATCH. |
| `uv run --frozen ruff check src tests migrations` | **PASS**. |
| `uv run --frozen ruff format --check src tests migrations` | **PASS**, 56 archivos. |
| `uv run --frozen pytest -m 'not integration' tests` | **386 PASS**, 78 descartadas. |
| `uv run --frozen pytest -m integration tests` | **78 PASS**, 386 descartadas; head TESTDB 0003 y metadata sin diff, incluidos restart/crash. |

Total posterior a remediación: **464 PASS**, warning upstream TestClient/httpx
conservado. No hubo PATCH rechazados. Los registros anteriores se conservan como
historia, no se sustituyen por este resultado. Solo cambiaron service/worker, sus
tests causales y este documento; no frontend, ODD/espejo, servicios, DB principal,
Git, dependencias ni configuración. Relectura/aprobación de revisión pendiente del
padre; no cierre verified/done global. Los dos ejemplos de abajo siguen siendo
**queued** y **waiting_human**, no una finalización aprobada.

## Dos ejemplos íntegros reales de TESTDB (solo datos inventados)

Capturados por `test_wire_examples`, 2026-10-24. Son `WorkDetail`, no wrappers;
la creación responde `{status:accepted,detail:<ejemplo 1>}` y GET devuelve el detalle
directo. UUIDs/timestamps de esa ejecución, no IDs que deban reutilizarse al operar.

### 1. Creado y todavía en cola

```json
{"work":{"id":"51e8f732-b696-4a61-9995-544a3591dec7","fixture_id":"request_video","recipe_version":1,"owner_id":"efren","state":"active","job_status":"queued","created_at":"2026-10-24T17:00:31.685487Z","updated_at":"2026-10-24T17:00:31.685487Z","source_snapshot":{"event_id":"evt-request-video-001","workspace_id":"demo-workspace","channel_id":"demo-channel","message_id":"msg-video-001","thread_id":"msg-video-001","actor_id":"ana","text":"@efren sube el video","occurred_at":"2026-01-15T15:00:00Z","source_url":null},"source_sha256":"783ad11ada6d4ca82aa95f27a03ace777a5e9acb1e7599362a415b8d2d888bcc"},"job":{"id":"e13ce53e-a5d6-4144-a43c-432b9279ffc5","work_id":"51e8f732-b696-4a61-9995-544a3591dec7","status":"queued","checkpoint":{"version":1,"phase":"prepare","source_sha256":"783ad11ada6d4ca82aa95f27a03ace777a5e9acb1e7599362a415b8d2d888bcc","proposal_artifact_id":null,"approval_id":null,"final_artifact_id":null,"next_action":"run_prepare"},"attempt_count":0,"failure_count":0,"available_at":"2026-10-24T17:00:31.685487Z","last_error_code":null},"history":[{"id":"06c39463-853f-48b3-83ff-69eebcce1ae0","sequence":1,"kind":"work_created","actor_id":"efren","occurred_at":"2026-10-24T17:00:31.689334Z","attempt_id":null,"attempt_number":null,"data":{"reason":"Solicitud explícita de simulación con fixture canónico.","alternatives":["No ejecutar efectos externos","Conservar la fuente sin cerrar"],"checks":[{"name":"local_step","status":"passed","detail":"Paso DB local registrado."}],"pending":["Publicación externa no implementada","Identidad humana no autenticada"],"source_fixture_id":"request_video","source_sha256":"783ad11ada6d4ca82aa95f27a03ace777a5e9acb1e7599362a415b8d2d888bcc","artifact_id":null,"approval_id":null,"error_code":null}}],"artifacts":[],"approvals":[]}
```

### 2. Propuesta durable esperando decisión simulada

```json
{"work":{"id":"51e8f732-b696-4a61-9995-544a3591dec7","fixture_id":"request_video","recipe_version":1,"owner_id":"efren","state":"waiting","job_status":"waiting_human","created_at":"2026-10-24T17:00:31.685487Z","updated_at":"2026-10-24T17:00:31.702795Z","source_snapshot":{"event_id":"evt-request-video-001","workspace_id":"demo-workspace","channel_id":"demo-channel","message_id":"msg-video-001","thread_id":"msg-video-001","actor_id":"ana","text":"@efren sube el video","occurred_at":"2026-01-15T15:00:00Z","source_url":null},"source_sha256":"783ad11ada6d4ca82aa95f27a03ace777a5e9acb1e7599362a415b8d2d888bcc"},"job":{"id":"e13ce53e-a5d6-4144-a43c-432b9279ffc5","work_id":"51e8f732-b696-4a61-9995-544a3591dec7","status":"waiting_human","checkpoint":{"version":1,"phase":"await_approval","source_sha256":"783ad11ada6d4ca82aa95f27a03ace777a5e9acb1e7599362a415b8d2d888bcc","proposal_artifact_id":"adc9244d-9cdc-4d70-9bd7-b330bacc1bb4","approval_id":"5e5a482d-0c05-4355-a34c-e7a887f103a6","final_artifact_id":null,"next_action":"human_decision"},"attempt_count":1,"failure_count":0,"available_at":"2026-10-24T17:00:31.685487Z","last_error_code":null},"history":[{"id":"06c39463-853f-48b3-83ff-69eebcce1ae0","sequence":1,"kind":"work_created","actor_id":"efren","occurred_at":"2026-10-24T17:00:31.689334Z","attempt_id":null,"attempt_number":null,"data":{"reason":"Solicitud explícita de simulación con fixture canónico.","alternatives":["No ejecutar efectos externos","Conservar la fuente sin cerrar"],"checks":[{"name":"local_step","status":"passed","detail":"Paso DB local registrado."}],"pending":["Publicación externa no implementada","Identidad humana no autenticada"],"source_fixture_id":"request_video","source_sha256":"783ad11ada6d4ca82aa95f27a03ace777a5e9acb1e7599362a415b8d2d888bcc","artifact_id":null,"approval_id":null,"error_code":null}},{"id":"a92b0bda-cc1d-4c75-afc4-0012a8d6a87b","sequence":2,"kind":"proposal_prepared","actor_id":"efren","occurred_at":"2026-10-24T17:00:31.700119Z","attempt_id":"b4febb8a-8cd2-40f1-9916-9986ec4710ed","attempt_number":1,"data":{"reason":"Falta contexto: propuesta ASK_CONTEXT, esperar decisión simulada.","alternatives":["No ejecutar efectos externos","Conservar la fuente sin cerrar"],"checks":[{"name":"local_step","status":"passed","detail":"Paso DB local registrado."}],"pending":["Publicación externa no implementada","Identidad humana no autenticada"],"source_fixture_id":"request_video","source_sha256":"783ad11ada6d4ca82aa95f27a03ace777a5e9acb1e7599362a415b8d2d888bcc","artifact_id":"adc9244d-9cdc-4d70-9bd7-b330bacc1bb4","approval_id":"5e5a482d-0c05-4355-a34c-e7a887f103a6","error_code":null}}],"artifacts":[{"id":"adc9244d-9cdc-4d70-9bd7-b330bacc1bb4","job_id":"e13ce53e-a5d6-4144-a43c-432b9279ffc5","attempt_id":"b4febb8a-8cd2-40f1-9916-9986ec4710ed","version":1,"kind":"proposal","content":{"title":"Pedir contexto del video (sintético)","summary":"ASK_CONTEXT: pedir qué video debe subirse y a qué destino. No publicar.","action":"ASK_CONTEXT","missing_context":["Qué video","Destino de publicación"],"checks":[{"name":"canonical_fixture","status":"passed","detail":"Snapshot y digest coinciden con request_video v1."},{"name":"external_publication","status":"not_run","detail":"Sin conector ni publicación externa."},{"name":"real_tests","status":"not_run","detail":"Este ejecutor no ejecuta pruebas ni comandos."}],"pending":["Obtener contexto real fuera de esta simulación","No cerrar la fuente"],"source_fixture_id":"request_video","source_sha256":"783ad11ada6d4ca82aa95f27a03ace777a5e9acb1e7599362a415b8d2d888bcc","no_external_effects":true},"sha256":"b360c87daa96e1c03bc55be76d21b6a4354585080d8ce1fec7eb18c654fbf947","created_at":"2026-10-24T17:00:31.701124Z"}],"approvals":[{"id":"5e5a482d-0c05-4355-a34c-e7a887f103a6","job_id":"e13ce53e-a5d6-4144-a43c-432b9279ffc5","artifact_id":"adc9244d-9cdc-4d70-9bd7-b330bacc1bb4","artifact_sha256":"b360c87daa96e1c03bc55be76d21b6a4354585080d8ce1fec7eb18c654fbf947","status":"pending","decision_reason":null,"decided_by":null,"created_at":"2026-10-24T17:00:31.701946Z","decided_at":null}]}
```

## Activación local autorizada · 2026-10-24

Tras la entrega de fuente/pruebas, el usuario autorizó continuar **solo con la
activación local de A**. Las observaciones siguientes corresponden aproximadamente
a 20:28–20:39 UTC del 2026-10-24; no son pruebas repetidas por esta actualización
documental ni autorización para B–F, conectores, publicaciones o Git.

### Preparación, migración y servicios observados

Antes de activar, la principal estaba en `0002_bridge`, sin tablas de trabajo y con
`/api/work` 404 esperado. Se registraron los seis contenedores previos y hashes
completos de filas de ocho tablas originales para comprobar preservación.

Los únicos acompañantes de configuración fueron el servicio Compose `work-worker`
y el ignore `.local/backups/`. El respaldo persistente privado quedó en
`.local/backups/activation-a-20261024T202836Z/main.dump`: formato custom, 25 179 bytes,
59 entradas de inventario, directorio 0700 y archivos 0600, con propietario/sin
symlinks verificados. Manifest e inventario permanecen privados; `.dockerignore`
ya excluía `.local`. Se verificaron dump, inventario y checksum, **no una restauración**.
No hubo restore, downgrade, reset ni `down -v` automático; no abrir ni publicar el
contenido del respaldo o credenciales.

Ledger de activación, clasificado previamente como **obligatorio por la autorización,
preservación, AGENTS y ODD**. Los comandos Compose usaron
`docker compose --project-name efren-bot -f compose.yaml`; se omiten parámetros
privados de respaldo/DB. Este registro describe lo ya ejecutado por el operador.

| Comando u operación | Resultado observado |
| --- | --- |
| Compose `config --quiet`; `git check-ignore --quiet` sobre la ruta del respaldo | PASS; configuración válida y respaldo ignorado. La comprobación histórica no concede permiso Git. |
| `pg_dump` custom; `pg_restore --list`, checksum y permisos | PASS, exit 0 para dump/inventario; restauración no probada. |
| Compose `build api web` | PASS; web en caché y backend reconstruido con locks congelados. Warning no fatal conservado: `useradd` UID 10001 supera `SYS_UID_MAX` 999. |
| Compose `run --rm --no-deps --pull never migrate alembic upgrade 0003_synthetic_work` | PASS; revisión exacta `0003_synthetic_work`, cinco tablas nuevas vacías y hashes de ocho tablas originales idénticos antes de recrear aplicaciones. One-off retirado; contenedor migrate histórico conservado. |
| Compose `up --detach --no-deps --no-build --pull never --force-recreate api web` | PASS; solo API/web recreados. |
| Compose `up --detach --no-deps --no-build --pull never work-worker` | PASS; servicio nuevo con imagen igual a API, cero mounts y sin puertos. |
| GET locales `/healthz`, `/readyz`, `/api/work` y `/api/work` por proxy web | 200; lista inicialmente vacía. Readiness no acredita worker. |
| Navegador local: crear intención, observar propuesta, reiniciar solo work-worker, recargar y aprobar simulación | PASS; recorrido detallado debajo. |
| Lecturas SQL de preservación, API y metadatos finales de contenedores | PASS; datos y servicios protegidos intactos, publicaciones solo loopback. |

No hubo fallos ni reintentos correctivos de activación. La migración usó una ejecución
one-off sin recrear el migrate histórico. Se conservaron por ID, StartedAt, estado,
imagen y puertos los cuatro servicios protegidos: DB, test-db, worker fixture y
migrate histórico. El proyecto quedó con siete servicios; API/web son sus nuevos
contenedores y `work-worker` es el único que se reinició durante la aceptación.

### Aceptación persistente por UI y API

En `http://localhost:5173` se abrió **Abrir trabajos sintéticos** y se creó una única
intención explícita `request_video`, sin POST inicial automático ni reproducir de
nuevo la simulación de tres mensajes. Se observaron:

- Work `3f91e5d6-49af-464b-88d0-d092b95efe95`, job
  `659c1825-4750-4833-8944-869922f6dc6f` en `waiting_human`, propuesta y aprobación
  `pending`, `next_action=human_decision`, 1 intento, 0 fallos y 2 entradas de historia.
- Reinicio mediante `docker restart` **solo del contenedor work-worker**, previamente
  verificado por sus etiquetas de proyecto/servicio. Conservó ID de contenedor, cambió
  StartedAt y el detalle completo consultado antes/después fue idéntico.
- Recarga del navegador, reapertura del panel y selección del expediente existente:
  mismos IDs, contexto, historia y siguiente paso; no fue necesario crear otro trabajo.
- **Aprobar simulación** con el SHA exacto de la propuesta y motivo explícito:
  «Acepto únicamente la finalización sintética local de A; no autoriza efectos externos.»
- Resultado UI/API `delivered`/`succeeded`, checkpoint `complete`, `next_action=none`,
  2 intentos, 0 fallos, 4 entradas de historia (las 2 originales intactas), 2 artefactos
  propuesta/resultado y aprobación `approved`.

No se subió video ni se ejecutó código, publicación Slack/Notion/MR o acción externa.
Dueño/decisor siguen siendo identidad demo local, **no autenticación humana real**.
Los estados crudos y el aviso sintético permanecen; `delivered` no significa Task done.

### Preservación y límites de evidencia

Lecturas SQL read-only finales confirmaron revisión principal `0003_synthetic_work`
y hashes completos de filas de las ocho tablas originales idénticos: 1 Task,
3 eventos, 3 outbox, 2 hilos, 3 mensajes, 3 actividades, 0 BridgeRuns y 0 presencias
del Bridge. La Task conserva exactamente `needs_context` y `has_new_reply`.
Solo el caso de aceptación añadió 1 work, 1 job, 4 historias, 2 artefactos y
1 aprobación. Health/readiness/proxy siguieron en 200 y las integraciones vacías.
El progreso del job observado —no `/readyz`— acredita el nuevo worker.

Esta fue una aceptación sintética autorizada de la aplicación más lecturas de
preservación, **no suites DB ni TRUNCATE contra la principal**. Las suites Python/web
anteriores se conservan como evidencia histórica y no se repitieron por activación.
La evidencia privada de sesión está en el scratch `efren-activation-a-5zg131km`,
con `before.json`, `after-migration.json`, `after-start.json`, `waiting.json`,
`delivered.json` y `after.json`; no son artefactos públicos del repositorio.

El snapshot final del navegador truncó texto al final: entrega e historia relevantes
sí fueron visibles y el detalle API íntegro quedó en `delivered.json`. No se afirma
revisión visual completa, de accesibilidad o móvil. Replay exacto adicional y captura
visual eran opcionales y **no se ejecutaron**. El navegador quedó abierto en el
resultado local para el usuario. No hay promesa 24/7 ni recuperación automática del
host. Riesgo formal exact-delta/judge y entrega Git siguen diferidos, con trabajo
histórico en el checkout; no se declara verified/done global. La plataforma B–F y
los conectores/skills/roles reales, embeddings y n8n siguen fuera de este alcance.
