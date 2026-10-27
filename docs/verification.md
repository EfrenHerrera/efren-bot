# Evidencia de verificación local

Registro incremental, no declaración de entrega completa. Git permanece intacto por decisión de Efrén: sin staging, commits, ramas ni push. La comparación formal de riesgo queda pendiente; no se sustituye con estas pruebas.

## Preparación de contratos

- **Obligatorias** (entorno y lock): `uv lock` resolvió 35 paquetes; `uv sync --frozen --no-install-project` instaló 32; `docker compose --project-name efren-bot config --quiet` terminó con código 0.
- **Opcional** (compatibilidad básica): imports de dependencias correctos con Python 3.14.6. No prueba la aplicación.
- **Opcionales** (disponibilidad de imágenes): las consultas `docker buildx imagetools inspect` de Python, uv, pgvector y Node agotaron 120 segundos cada una. Se conservaron las versiones; no se declaró runtime verificado por esos intentos.

## Preparación de la base de la demo

Comprobaciones clasificadas como **obligatorias** antes de ejecutarse, por el criterio de arranque local. Se usa el proyecto Compose `efren-bot`, no contenedores de otros proyectos.

1. `docker compose --project-name efren-bot up --detach --pull never db`
   - Resultado: código 0; volumen `efren-bot_postgres-data` y contenedor `efren-bot-db-1` creados, contenedor iniciado.
   - No se descargó una imagen en este comando: la imagen ya estaba disponible al ejecutarlo.
2. `docker compose --project-name efren-bot exec -T db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" && psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "SELECT current_database() AS database, name, default_version, installed_version FROM pg_available_extensions WHERE name = '\''vector'\'';"'`
   - Resultado: código 0; PostgreSQL acepta conexiones, base `efren_bot`; extensión disponible `vector`, versión `0.8.1`, todavía no instalada en esta base.
   - Esto demuestra disponibilidad del servidor y de la extensión, **no** aplicación de migraciones ni recuperación vectorial.

Sin reintentos ni cambios correctivos entre estas dos comprobaciones. API, worker y frontend no se iniciaron en estos pasos.

## Evidencia recibida antes de la integración

Fuente: `.odd/base-local.md`, espejo Engram #3815; backend tareas 2/3, frontend sesión
`ses_e98c4fd45ffelJJA1T6Z94Njvc` / Engram #3819. Checks obligatorios por criterios
backend/frontend, salvo Context7/inventario opcionales. Historial, no nuevas ejecuciones:

1. Tarea 2: `uv sync --frozen` instaló paquete; `uv run --frozen pytest -m 'not integration' tests`: 28 OK.
   `uv run --frozen ruff check src tests migrations`: falló 5 estilos;
   `uv run --frozen ruff format --check src tests migrations`: falló 9 archivos.
2. `docker compose --project-name efren-bot --profile test config --quiet`: exit0.
   `docker compose --project-name efren-bot --profile test up -d --wait --wait-timeout 60 test-db`:
   exit0, healthy, primer intento (timeout externo90s), volumen propio separado.
3. `DATABASE_URL=<test-loopback> uv run --frozen pytest -m integration tests`: 6 OK/1 fallo
   por test de carrera sin aislamiento. Corregido parametrizando casos con DB limpia;
   repetición 9 OK; unitarias28 OK; Ruff check/format12 archivos exit0.
4. Tarea 3: mismo pytest unitario39 OK; integración18 OK, incluido SIGKILL real de hijo
   de test propio. Ruff check falló4 líneas largas y format4 archivos. Patch, más tests
   de frontera aware/NUL, SQL real, no-fetch/sleep: unitarias43/integración20/Ruff19 OK.
5. Regresión dirigida `test_reply_before_root_and_thread_scope`: fallo confirmado
   `deferred` frente a `idle`, potencial starvation de raíz. Corregida elegibilidad
   de reply `awaiting_root` hasta existir tarea en su hilo. Dirigida1 OK; regresión
   final43 unitarias/20 integraciones/Ruff19 exit0, sin writes posteriores de fuentes.
6. Frontend: `npm ci`107 paquetes, Node26.0.0/npm11.12.1. Primer
   `npm run typecheck` falló TS2339/TS7006 por unión inferida en `useRemote`;
   corregido `Snapshot<T>` explícita, sin casts ni relajar strict. Repetición25 tests;
   cierre `npm run test -- --run`27/27, typecheck/build exit0.
7. Cierre backend: primer resumen Engram falló `unknown_session`, registro de sesión
   y reintento OK. Sin métricas ODD ni mutaciones Git. `.env.example` denegado;
   no se reintentó su lectura ni se eludió el permiso.

`<test-loopback>` corresponde exclusivamente a
`postgresql+psycopg://efren_bot:local_demo_only@127.0.0.1:55433/efren_bot_test`.
El guard ya existente rechaza DB demo, hosts remotos y query overrides antes de
conectar/migrar/truncar; no se necesitó modificar código backend.

## Tarea 5 — integración real (2026-10-23)

Clasificación anunciada **antes** de ejecutar: obligatorias por criterios ODD de
arranque, PostgreSQL/vector, HTTP/dedupe, worker persistente y regresión; inventario,
versiones y logs opcionales por diagnóstico. Sin navegador en esta delegación.
Lecturas/ediciones de documentación no son pruebas de runtime.

Orden de ejecuciones (las del mismo bloque paralelo no tienen dependencia):

| # | Clasificación / fuente | Comando o peticiones | Resultado y corrección |
| --- | --- | --- | --- |
| 1 | Obligatoria / Compose | `docker compose --project-name efren-bot --profile test config --quiet` | exit0. |
| 2 | Obligatoria / arranque | `docker compose --project-name efren-bot up --build -d --wait --wait-timeout 90` (timeout externo300s) | exit0 primer intento; imágenes Python/uv/Node descargadas, builds reales, migrate exit0, DB/API healthy, web/worker running. Sin fallback ni bloqueo registry. Warning no fatal `useradd: uid 10001 is greater than SYS_UID_MAX 999`; no cambio de permisos/daemon. npm contenedor106 añadidos/107 auditados,0 vulnerabilidades. |
| 3a | Obligatoria / demo DB-vector | `docker compose --project-name efren-bot exec -T db psql -U efren_bot -d efren_bot -v ON_ERROR_STOP=1 -c "SELECT current_database(), version_num FROM alembic_version; SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'; SELECT '[1,0,0]'::vector <-> '[0,0,0]'::vector AS synthetic_distance; SELECT (SELECT count(*) FROM events) AS events, (SELECT count(*) FROM messages) AS messages, (SELECT count(*) FROM outbox) AS outbox, (SELECT count(*) FROM tasks) AS tasks, (SELECT count(*) FROM activities) AS activities;"` | exit0: efren_bot/0001_local, vector0.8.1 **instalada**, distancia1, todas las tablas vacías antes del HTTP. |
| 3b | Opcional / inventario | `docker compose --project-name efren-bot --profile test ps --all` | Solo proyecto propio: DB demo55432 y test55433 healthy, API8000 healthy, web5173 y worker running, migrate exited0. Publicaciones127.0.0.1. |
| 4 | Obligatoria / HTTP real | `uv run --frozen python - <<'PY'` con `httpx.Client(base_url='http://127.0.0.1:5173', timeout=5)`; GET `/`, `/healthz`, `/readyz`, `/api/overview`, `/api/demo/fixtures`; POST root, reentrega, root con texto distinto, thanks; poll overview (máx50×0.2s); GET fuente UUID | exit0: todos GET200, raíz202→200 mismo UUID, conflicto409, thanks202; una tarea needs_context, dos actividades, sin reply ni pendientes. Fuente conserva payload completo y proveedor/dueño. No TestClient. |
| 5 | Obligatoria / reinicio real | `docker compose --project-name efren-bot stop worker` | exit0, solo worker propio detenido limpiamente. |
| 6 | Obligatoria / cola offline | `uv run --frozen python - <<'PY'` con mismo cliente: GET fixtures; POST reply literal; GET overview | exit0: reply202, pending1, tarea1/updates0 y actividades2; aceptación persistida sin proyección parcial mientras worker detenido. |
| 7 | Obligatoria / reinicio real | `docker compose --project-name efren-bot start worker` | exit0; reejecutó migrate de forma idempotente, arrancó proceso worker. |
| 8 | Obligatoria / recuperación y detalle | `uv run --frozen python - <<'PY'` mismo cliente; poll overview; GET `/api/tasks/{uuid}`, ambas `/api/events/{uuid}`; POST los tres fixtures otra vez; GET overview y GET directo `http://127.0.0.1:8000/readyz` | exit0: pending0, task1 needs_context/has_new_reply=true, actividades3, hilo con solo raíz+reply en orden. UUID nativos serializados válidos, payloads exactos, source_url null. Tres replays200 y overview idéntico, ninguna transición done. Readiness directo200. |
| 9a | Obligatoria / CLI compartida | `make demo` → `docker compose --project-name efren-bot exec -T api python -m efren_bot.demo` | exit0: tres duplicate con UUID estables, ingesta directa compartida, no HTTP ni procesamiento implícito. |
| 9b | Obligatoria / unicidad SQL | `docker compose --project-name efren-bot exec -T db psql -U efren_bot -d efren_bot -v ON_ERROR_STOP=1 -c "SELECT (SELECT count(*) FROM events) AS events, (SELECT count(*) FROM messages) AS messages, (SELECT count(*) FROM threads) AS threads, (SELECT count(*) FROM outbox) AS outbox, (SELECT count(*) FROM tasks) AS tasks, (SELECT count(*) FROM activities) AS activities; SELECT status, count(*) FROM outbox GROUP BY status;"` | exit0: events3/messages3/threads2/outbox3/tasks1/activities3, los3 outbox processed. |
| 9c | Opcional / logs | `docker compose --project-name efren-bot logs --no-color --tail=30 migrate worker web` | exit0: Vite8.3.5 ready, worker3 processed con attempts0. |
| 10 | Obligatoria / reproducibilidad test DB | `make test-db` | exit0, DB ya existente healthy; no toca demo. Target nuevo evita instrucciones incompletas. |
| 11 | Obligatoria / regresión tras companions | `make check` | exit0: Compose, Ruff check/format src tests migrations19, npm ci107 añadidos/108 auditados0 vulnerabilidades, typecheck y build (113 módulos). |
| 12 | Obligatoria / regresión conjunta | `make test` | exit0:43 unitarias,20 integraciones PostgreSQL separadas,27 frontend. Incluye migración test, SQL vector, guard y recuperación SIGKILL de hijo de test. Warning upstream Starlette/TestClient-httpx conservado; no se cambian dependencias. |
| 13 | Obligatoria / comando final documentado | `make up` (timeout externo300s) | exit0; no retry por fallo: validación del target editado y nueva imagen tras README/comentario Docker. Web cached, backend reconstruido; migrate exit0, API healthy, worker/web running. Volumen demo conservado con datos. Mismo warning useradd no fatal. |
| 14a | Obligatoria / smoke final | `uv run --frozen python - <<'PY'` con httpx: GET directo8000 `/healthz` y `/readyz`; GET5173 `/` y `/api/overview` | exit0, todos200; cuenta final1 tarea/1 actualización/3 actividades/0 pendientes/0 failed preservada tras rebuild. |
| 14b | Opcional / inventario final | `docker compose --project-name efren-bot --profile test ps --all` | exit0, API/DB healthy, worker/web running, migrate exit0; ambas DB separadas siguen arriba. |
| 14c | Obligatoria / migración test explícita | `docker compose --project-name efren-bot --profile test exec -T test-db psql -U efren_bot -d efren_bot_test -v ON_ERROR_STOP=1 -c "SELECT current_database(), version_num FROM alembic_version; SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"` | exit0: efren_bot_test/0001_local/vector0.8.1. |
| 14d | Opcional / versiones | `docker compose --project-name efren-bot exec -T web sh -c 'node --version && npm --version'`; `node --version`; `npm --version` | exit0: contenedor Node26.12.1/npm11.20.0; host26.0.0/11.12.1. El tag Node26 fija major, no patch. |
| 15 | Obligatoria / consistencia documental AGENTS y criterio reproducible | Lectura final README/arquitectura/verificación/ODD; búsqueda de estados obsoletos en docs y readback completo Engram3815 | No quedan afirmaciones de API inexistente; tracking y espejo íntegro concordantes, tarea4[x]/tarea5[ ] parcial, Git/riesgo pendientes. Corregidos alineación del esquema textual y comandos nativos para copia sin saltos, solo documentación. |

No hubo fallos de comandos runtime en tarea 5 ni reintentos de descargas. Una lectura
exploratoria de `tests/test_config.py` devolvió file not found: se localizaron los tests
reales en `tests/test_validation.py`, sin crear stubs ni convertirlo en fallo de runtime.
No se consultó `.env.example`; se usaron defaults de configuración/documentación.
No se generaron índices CodeGraph/Graphify ni se consultó un índice ajeno.

### Secuencia HTTP ejecutada y límites

Los scripts anteriores usan exactamente fixtures servidos por GET, no regeneran IDs
ni fechas. En el primer script se comparó el overview inicialmente vacío, recepción
UUID y payload de fuente igual a la raíz. Tras restart, se comprobaron dos mensajes
(`request_video`, `reply`) con sus fuentes UUID/payload completas y tres actividades
(`task_request`, `acknowledgement`, `thread_reply`). Counts finales:

```json
{"tasks":1,"needs_context":1,"ready":0,"updates":1,"pending_events":0,"failed_events":0}
```

El reinicio de tarea 5 prueba cola persistida con worker detenido y recuperación al
arrancar, **no** un nuevo crash profundo a mitad de commit. Ese caso está acotado por
el SIGKILL real en DB test documentado en `tests/README.md`. Readiness ejecuta SELECT1,
no afirma salud del worker; el worker se verificó por sus efectos reales y SQL.
Se sirvió HTML y se recorrió el proxy real, pero esto **no** es prueba visual/navegador.
No se visitó source_url ni hubo efectos externos. Vector sintético no implica RAG.

### Cambios causales de integración

- `Makefile`: `up` espera readiness90s como comando verificado; `test-db` arranca
  explícitamente la DB separada; `lint` incluye migraciones; ayuda sin estado futuro.
- `README.md`, `docs/local-development.md`: arranque y pruebas reales, versiones,
  operación sin borrar volúmenes, defaults explícitos, CLI no-HTTP y límites.
- `docs/contract.md`, `docs/architecture.md`: contrato implementado de base no-V1,
  CLI directa, constraints por mensaje fuente y recuperación por savepoint real.
- `AGENTS.md`, `Dockerfile`: retiradas afirmaciones temporales de código inexistente.
- `docs/verification.md`, `.odd/base-local.md`: evidencia y seguimiento incremental.
- Sin defectos confirmados que requirieran tocar `src/`, `tests/` ni `apps/web/`.

## Tarea 5 — corrección posterior de presentación horaria (2026-10-23)

Evidencia recibida de `ses_e98a37e42ffek4wrmDJBobhNTK`, Engram #3825; no nuevas
ejecuciones en este cierre documental. El coordinador detectó UI UTC frente a la
zona funcional Mérida; traza: etiqueta -> API UTC -> formatter UTC -> fixture15Z.
Corrección acotada a `apps/web/src/App.tsx`, `apps/web/src/test/App.test.tsx`,
`apps/web/vite.config.ts`, `compose.yaml` (solo entorno web), `apps/web/README.md`
y `docs/local-development.md`. APP_TIMEZONE existente se pasa a Vite como zona
pública VITE_APP_TIMEZONE; default America/Merida, validación IANA con Intl,
sin publicar otras variables ni credenciales. DEFAULT_APP_TIMEZONE no es un secreto.
API/DB/JSON conservan UTC; no se leyó `.env` ni se eludió permiso alguno.

Todos los siguientes checks se clasificaron **obligatorios antes de ejecutarse**,
por criterios UI/configuración/arranque de la corrección. Orden recibido exacto:

| # | Comando / comprobación | Resultado |
| --- | --- | --- |
| 1 | `npm --prefix apps/web run typecheck` | exit0. |
| 2 | `npm --prefix apps/web run test -- --run` | exit0,31/31; antes27. |
| 3 | `npm --prefix apps/web run build` | exit0. |
| 4 | Script Node con `resolveConfig` de Vite | exit0: default America/Merida, APP_TIMEZONE=America/Bogota prevalece sobre VITE_APP_TIMEZONE=UTC; solo se publica la zona; rechazos esperados Invalid/Timezone, +06:00 y vacío. Son casos negativos correctos, no fallos de comando. |
| 5 | `docker compose --project-name efren-bot config --quiet` | exit0. |
| 6 | `npm --prefix apps/web run build` tras endurecer validación IANA | exit0, incluye typecheck. Segundo build deliberado, no retry por fallo. |
| 7 | `docker compose --project-name efren-bot up --build -d --no-deps --pull never web` | exit0, solo web recreada. Capas base/npm ci en caché; metadata Docker0.8s, sin descarga de capas. Backend/worker/DB intactos. |
| 8 | Script Node HTTP real a `http://127.0.0.1:5173` | exit0: panel/healthz/readyz200, configuración Mérida servida, evento real mantiene2026-01-15T15:00:00Z (=09:00 Mérida);1needs_context/1update/0pending/0failed. |

Los scripts Node inline se identifican por operación y resultados en la evidencia
recibida, no por un nombre de archivo o línea de comando reconstruidos.
Sin fallos correctivos. No se repitieron pruebas backend porque sus fuentes no
cambiaron: siguen vigentes43 unitarias/20 integraciones DB separada; no se altera
el registro inicial de27web. Las31 pruebas posteriores cubren lista/hilo/actividad
a09:00, updated_at05Z ->14ene23:00, override Bogotá10:00, zona inválida y payload15Z.

## Tarea 5 — navegador del coordinador (2026-10-23)

**Obligatorio**, criterio panel real escritorio/móvil. Herramienta OpenChamber,
servicios propios ya activos; evidencia recibida, no repetida en este cierre:

1. Abrir escritorio1440x900: datos reales1tarea y detalle con2mensajes; etiqueta
   Mérida09:00 y actualización22oct23:54.
2. Click «Petición video»: «Evento ya recibido. No se añadió trabajo nuevo»;
   mantiene1tarea, no trabajo adicional.
3. «Ver evento» accepted: payload con occurred_at15Z intacto.
4. Móvil390x844: layout apilado; acceso a fuente y enlace `a.back-link`
   «Volver a pendientes» funcionales.
5. Capturas: `.openchamber/screenshots/efren-bot-desktop-final-2026-10-23T06-17-32-053.jpg`
   y `.openchamber/screenshots/efren-bot-mobile-2026-10-23T06-11-39-990.jpg`.

Snapshots sin errores reportados **no equivalen** a una comprobación completa de
consola. El padre terminó su navegador; esta delegación no abre ni toca sus tabs.
`.gitignore` incorpora `.openchamber/` únicamente para no versionar capturas propias;
es un companion mecánico autorizado, no staging ni otra mutación Git.

## Tarea 5 — smoke real de teclado, foco y overflow (2026-10-23)

Fuente: `ses_e989c094cfferubuO83h0xKqYN`, Chrome headless156.0.8078.48, perfil
temporal nuevo sin login. Instrumentación temporal @playwright/test fuera del repo;
no se incorpora como dependencia ni prueba del producto. Scratch aprobado:

`/private/var/folders/kh/h4blnjhx4cz49v5cd9lw8yv80000gp/T/opencode/efren-bot-browser-smoke/`

Artefactos: `inspect.mjs`, `smoke.mjs`, `results.json`, `results-retry.json`.
Clasificados antes: criterio UI/teclado **obligatorio**; preparación de instrumentación
**opcional auxiliar**, no evidencia funcional por sí sola. Orden recibido:

| # | Clasificación / fuente | Comando / comprobación | Resultado |
| --- | --- | --- | --- |
| 1 | Opcional auxiliar / localizar instrumentación | Sondeo `command -v` de node/npm y listado de alternativas de navegador | exit1 por alternativas ausentes; Chrome sí encontrado. No fallo del producto. La evidencia no aporta la línea completa del sondeo; no se reconstruye. |
| 2 | Opcional auxiliar / dependencias disponibles | Node `require.resolve` de3paquetes | exit0:3no disponibles (errores capturados por el sondeo); sin inventar sus nombres ni línea no recibida. |
| 3 | Opcional auxiliar / instalar en scratch | `npm install --save-dev --ignore-scripts --no-audit --no-fund @playwright/test` | exit0, solo scratch. |
| 4 | Obligatoria / inspección UI real | `node inspect.mjs` | exit0;1resource404, URL no identificada. Se conserva; no afirmar una sesión íntegra sin errores. |
| 5 | Obligatoria / teclado/foco/layout | `node smoke.mjs` | exit1:8PASS y4fallos del SCRIPT: contraste calculado contra relleno incorrecto y selector de fecha ambiguo. Corrección únicamente de scratch, no del producto. |
| 6 | Obligatoria / reintento tras corregir script | `RESULTS_FILE=results-retry.json node smoke.mjs` | exit0,12/12 asserts. Solo en este reintento: consola0, pageerror0, respuestas HTTP>=400=0. No borra el404 inicial ni el intento fallido. |

Resultados finales en **ambos viewports1440x900 y390x844**:

- Tab al skiplink: foco visible, bbox15,7.5,116.41,38.25.
- Tab por3fixtures: outline3px, offset4px, contraste5.70; Enter en duplicado mantiene1tarea.
- Tab a tarea y Space selecciona; Tab a fuente y Enter abre JSON; contraste del foco fuente5.26.
- `document.documentElement.scrollWidth == innerWidth` en1440/390; `pre` con
  overflowauto, sin scroll horizontal de página.
- Hora visible09:00 Mérida y JSON crudo15Z conservados.

Perfil temporal cerrado, sin tocar el tab del padre. Estos son12 asserts de smoke,
no una auditoría exhaustiva de accesibilidad ni una sustitución de la revisión formal.
Los fallos de instrumentación/404 son posteriores al bloque inicial de integración:
su frase «sin fallos runtime» se refiere a ese bloque, no a toda esta sesión ampliada.

## Cierre documental parcial y pendientes

Conciliación/readback de reglas, documentación, ODD y espejo Engram **obligatorios
por encargo/AGENTS**, no pruebas runtime. En esta delegación no se reejecutaron
suites ni se añadieron comprobaciones opcionales o workflows. Historial anterior
preservado, incluidos fallos, reintentos y warnings. README/desarrollo solo corrigen
estado obsoleto; READMEweb ya vigente, sin cambios. Espejo completo bajo
`odd/base-local/tasks`, proyecto `efren-bot`; se relee junto con disco para concordancia.

- **Tarea 5 [x]**, criterios funcionales PASS: entrega funcional local observada,
  incluidos navegador escritorio/móvil y teclado real, con la corrección de zona.
  Regresión inicial63backend+27web preservada; posterior31web/12asserts UI final,
  sin reclamar backend reejecutado ni ausencia global de errores.
- **Tarea 6 [ ]**, feature formalmente **pending**, no verified/done: riesgo exacto,
  revisión requerida y entrega formal diferidos explícitamente por el usuario.
  No hay tier determinista disponible ni scraft-judge ejecutado; las pruebas no los
  sustituyen. Git sigue intacto; no reabrir esta decisión ni pedir una estrategia ahora.
- Servicios propios arriba: panel `http://127.0.0.1:5173`, API
  `http://127.0.0.1:8000` (healthz/readyz200), worker independiente; DB demo55432
  y DB test55433 healthy, volúmenes separados conservados. migrate one-shot exit0.
- Detener solo este proyecto sin borrar datos: `docker compose --project-name efren-bot --profile test stop`;
  retirar contenedores con `make down`, nunca `down -v`. No se ejecutó down en esta tarea.
- V1 completa, conectores, LLM, embeddings y RAG: fuera del alcance de esta base local.
- Próximo paso: mostrar el panel al usuario. Git/riesgo quedan diferidos hasta que
  él los reabra; sin otra capacidad en marcha, nueva tarea automática o métricas ODD.
