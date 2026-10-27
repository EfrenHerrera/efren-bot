# Desarrollo local

## Retiro web · 2026-10-24

La fuente web actual deja una página blanca: no bandeja, simulaciones, panel manual,
clientes, polling ni proxy. El backend, sus workers, migraciones y datos no se retiran.
Typecheck/tests/build validan fuente; el despliegue exclusivo de web y su aceptación
real en navegador son pasos separados. No inferir runtime actualizado de estos checks.

## Herramientas y configuración

- Python `>=3.12,<3.15`; `.python-version` fija 3.14.6, también en Docker.
- uv 0.11.28; `uv.lock` universal generado con resolver, `uv sync --frozen` en
  imagen y entorno. La capa Docker de dependencias usa `--no-install-project`;
  la capa final instala el paquete no editable.
- PostgreSQL 17 soportado, imagen explícita `pgvector/pgvector:0.8.1-pg17`.
  Habilitar `vector` en migración, no confiar en que la imagen cree la extensión.
  Sin paquete Python pgvector: la comprobación sintética se puede ejecutar con SQL.
- Backend en `Dockerfile`, uv fijado `ghcr.io/astral-sh/uv:0.11.28`; sin bind mounts
  ni instalación editable. Web: `node:26-bookworm-slim`, lock npm y `npm ci`.
  Los builds y el arranque Docker se probaron; tags de release no son digest fijados.
  Versiones efectivamente observadas e intentos en [verification.md](verification.md).

No hace falta `.env` para la demo. Compose recibe variables por interpolación con
defaults exclusivamente locales. Para personalizar en el host, exportar variables
explícitamente: Python no carga `.env` automáticamente. No guardar secretos reales.

| Variable | Valor / validación del backend |
| --- | --- |
| `APP_ENV` | Solo `local`; cualquier otro valor aborta API/worker/demo. |
| `DATABASE_URL` | Única URL de aplicación, dialecto `postgresql+psycopg`; default `postgresql+psycopg://efren_bot:local_demo_only@127.0.0.1:55432/efren_bot`, Compose `db:5432`; solo hosts locales y sin query options. |
| `APP_TIMEZONE` | `America/Merida`, validar con `zoneinfo`; presentación, no almacenamiento. |
| `DEMO_OWNER_ID` | Dueño único `efren`, no aceptar override desde HTTP. |
| `WORKER_POLL_INTERVAL_SECONDS` | Float finito en `[0.1, 60]`, default `1.0`; sleep fuera de transacción. |
| `POSTGRES_DB/USER/PASSWORD` | Solo bootstrap/interpolación Compose; defaults demo. Mantenerlos consistentes con URL host. |
| `TEST_DATABASE_URL` | Variable de Make/pruebas, no otra URL leída por la app. Target `test-integration` la pasa como `DATABASE_URL`. |

Compose conserva las variables históricas `VITE_PROXY_TARGET` y `APP_TIMEZONE` en
web, pero el Vite actual ya no las consume ni publica zona horaria al cliente.
No hay listas, hilos ni fechas web. `APP_TIMEZONE` sigue siendo configuración del
backend; API, DB y JSON de origen conservan UTC. No se cambió Compose por este retiro.

La imagen no incluye `.env`; las aplicaciones validan entorno. No cambiar estos
defaults para conectar a bases/servicios reales. Credenciales demo no son una medida
de seguridad; mantener publicaciones loopback. Identificadores/contraseñas PostgreSQL
personalizados con caracteres reservados requieren URL-encoding coherente.

## Aislamiento y arranque

Proyecto `efren-bot`, volumen Compose `efren-bot_postgres-data`, red propia y ningún
`container_name` global. Puertos publicados: `127.0.0.1:55432`, `:8000`, `:5173`.
Si un puerto está ocupado, detenerse y acordar un cambio; no detener al dueño del puerto.
DB separada `efren_bot_test` en `127.0.0.1:55433`, perfil `test`, volumen
`efren-bot_postgres-test-data`; nunca reutilizar el volumen demo.

1. `make sync`: instalar proyecto y grupo dev.
2. `make up`: construir imágenes y esperar hasta 90 s de arranque; DB healthy -> migrate finaliza 0 -> API/worker;
   API ready -> web. Vite escucha `0.0.0.0:5173` dentro del contenedor.
3. Abrir `http://127.0.0.1:5173` tras integrar el retiro: página completamente blanca,
   sin controles ni consultas de producto. No hay proxy web; la API permanece en
   su puerto directo. El recorrido de tres mensajes por UI es evidencia histórica.
4. `make demo`: CLI dentro del contenedor API usa la ingesta backend compartida
   directamente, sin HTTP. Solo persiste los tres fixtures; **no** ejecuta el worker
   ni espera proyección. El worker separado la realiza; repetir devuelve `duplicate`.
5. `make down`: detener solo este proyecto, conservar volúmenes. Nunca borrar datos
   automáticamente ni añadir `-v`; no usar comandos globales prune/stop.

Para pausar conservando contenedores: `docker compose --project-name efren-bot --profile test stop`.
Para solo test DB: añadir `test-db` al final. Los servicios de la verificación quedan
arriba para revisión local, sin credenciales ni conexiones reales.

### Pruebas separadas

```sh
make sync
make test-db
make check
make test
```

`make test-integration` pasa `TEST_DATABASE_URL` como `DATABASE_URL`; default
`postgresql+psycopg://efren_bot:local_demo_only@127.0.0.1:55433/efren_bot_test`.
El guard en `tests/conftest.py` valida dialecto, host loopback, nombre exacto y ausencia
de query overrides **antes** de conectar/migrar/truncar; comprueba `current_database()`.
Aplica Alembic en la DB test y limpia solo sus tablas conocidas por caso. No ejecutar
dos suites simultáneamente en esa misma base. No pasar la DB demo a los tests.

Web en el host: `npm --prefix apps/web ci`, `npm --prefix apps/web run typecheck`,
`npm --prefix apps/web run build`, `npm --prefix apps/web run test -- --run`.
Para desarrollo nativo contra la DB demo ya migrada:
`uv run --frozen uvicorn efren_bot.api:app --host 127.0.0.1 --port 8000`,
`uv run --frozen python -m efren_bot.worker` y `npm --prefix apps/web run dev`. No usarlos mientras Docker
ocupe esos puertos. Esta alternativa nativa no se necesitó ni se verificó en tarea 5.

Comprobación sintética reproducible en demo:

```sh
docker compose --project-name efren-bot exec -T db psql -U efren_bot -d efren_bot -v ON_ERROR_STOP=1 -c "SELECT extversion FROM pg_extension WHERE extname='vector'; SELECT '[1,0,0]'::vector <-> '[0,0,0]'::vector;"
```

Resultado observado: vector `0.8.1`, distancia `1`. No implica búsqueda semántica ni RAG.
Solo los tres fixtures exactos tienen semántica determinista; el resto queda `ignored`
sin tarea para revisión manual. No hay LLM, conectores ni transición automática a `done`.

## Comprobaciones y evidencia

Clasificar antes de cada ejecución e informar intentos, salida y correcciones, incluidos fallos.

| Clasificación / fuente | Comprobación | Momento |
| --- | --- | --- |
| Obligatoria, tarea 1 | `uv lock`; `uv sync --frozen --no-install-project` | Preparación; resolver e instalar dependencias reales. |
| Obligatoria, tarea 1 / criterio Compose | `docker compose --project-name efren-bot config --quiet` | Valida configuración, no construye ni verifica runtime. |
| Obligatoria, criterios backend | `make lint`, `make test-unit` | Tras código/tests. |
| Obligatoria, criterios DB/recuperación | `make test-integration` | Tras DB test separada: migraciones, vector sintético, dedupe concurrente, rollback y recuperación. |
| Obligatoria, criterios frontend | `make web-check`, `make test-web` | Tras interfaz: scripts `typecheck`, `build`, `test -- --run`. |
| Obligatoria, criterios recorrido histórico | HTTP real por proxy, worker proceso/reinicio, `make demo` y navegador | Observados antes del retiro en tarea 5, incluido escritorio/móvil/teclado; la UI/proxy ya no existen en fuente. |
| Obligatoria, retiro web del 2026-10-24 | `npm ci`, typecheck, tests del App vacío, build e inventario fuente/dist | Sin clientes/hooks/proxy ni chunks legacy; despliegue solo web y aceptación de vacío/preservación separados. |
| Obligatoria, entrega global | Revisión de alcance exacto y estrategia de comparación sin HEAD | Diferida por decisión de dejar Git intacto; no inventar base ni reabrir la decisión. |
| Opcional, inventario | Versiones instaladas, listeners, dry-run Make | Diagnóstico; no acredita producto funcional. |

Pruebas de integración: 202/200/409, validación aware/URL, unicidad evento/mensaje,
rollback evento/outbox, proyección atómica, reintento/crash y consumo concurrente;
sin cierre automático y reply sin mención. La UI anterior cubría carga/error/vacío,
teclado y ancho móvil; sus pruebas se retiran junto con las features, no se cuentan
como regresiones vigentes. La suite actual exige vacío y ausencia de efectos tras
StrictMode, rerender, espera, visibilidad, ciclo de página y remount.
No declarar base verificada solo por resolver, imports o validación Compose.
El cierre funcional de tarea 5 conserva 43 unitarias/20 integraciones y 27 pruebas
web iniciales; tras corregir solo presentación horaria, 31/31 web y smoke de navegador
12/12 final. Fallos/reintentos completos en [verification.md](verification.md).
Tarea 6 y feature formal siguen pending: Git/riesgo exacto/revisión/entrega diferidos
hasta que el usuario los reabra, sin métricas ODD ni nueva capacidad automática.

## Referencias consultadas

Documentación actual consultada vía Context7 para estas decisiones (no sustituye lock):

- [uv: sync parcial y Docker](https://docs.astral.sh/uv/guides/integration/docker/)
  y [backend de build](https://docs.astral.sh/uv/concepts/build-backend/): capas
  `--no-install-project`, `--frozen`, instalación no editable.
- [Compose: orden de inicio](https://docs.docker.com/compose/how-tos/startup-order/):
  `service_healthy` y migración `service_completed_successfully`; puertos loopback.
- [SQLAlchemy 2: psycopg](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg)
  y [select/locks](https://docs.sqlalchemy.org/en/20/core/selectable.html#sqlalchemy.sql.expression.GenerativeSelect.with_for_update):
  dialecto `postgresql+psycopg` y `skip_locked`.
