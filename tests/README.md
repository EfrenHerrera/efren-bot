# Comprobaciones backend locales

Obligatorias por `.odd/base-local.md`, `AGENTS.md` y criterios de tareas 2/3:

```sh
uv sync --frozen
uv run --frozen pytest -m 'not integration' tests
uv run --frozen ruff check src tests migrations
uv run --frozen ruff format --check src tests migrations
docker compose --project-name efren-bot --profile test config --quiet
docker compose --project-name efren-bot --profile test up -d --wait --wait-timeout 60 test-db
DATABASE_URL='postgresql+psycopg://efren_bot:local_demo_only@127.0.0.1:55433/efren_bot_test' uv run --frozen pytest -m integration tests
```

El último comando equivale a `make test-integration`; `make test-unit` y
`make lint` siguen disponibles (el comando Ruff anterior incluye además migraciones).
No ejecutar simultáneamente dos suites de integración sobre la misma DB: cada caso
trunca **solo** las tablas explícitas de este producto, después del guard de aislamiento.
No se usa SQLite, mocks de persistencia ni la DB de demo. `TEST_DATABASE_URL` es
solo la variable de Make; la app y las migraciones leen `DATABASE_URL`.

Antes de cualquier migración/truncate se exige dialecto `postgresql+psycopg`, nombre
exacto `efren_bot_test`, host loopback, puerto explícito **55433** y ninguna query que pueda cambiar
host/servicio. Se verifica también `current_database()`. Cambiar `DATABASE_URL` a
una DB demo/remota aborta, no migra ni limpia. No se necesitan cambios de pyproject/lock.
`Settings` solo permite `APP_ENV=local`, `DEMO_OWNER_ID=efren`, timezone IANA y poll
finito entre 0.1 y 60 s; no carga `.env` implícitamente. No usar credenciales reales.

La fixture de sesión aplica `alembic upgrade head` sobre esa DB separada. La suite
compara metadata ORM/migración y ejecuta distancia SQL entre vectores sintéticos;
esto no implementa embeddings ni RAG.

## Recuperación y alcance de la evidencia

- Fallo de ingesta inyectado al insertar outbox: rollback de evento/mensaje/hilo.
- Fallo de proyección tras flush de tarea/actividad: rollback del savepoint **antes**
  de persistir intento/backoff. Se conserva el lock del claim en la transacción
  exterior, evitando que otro worker observe o procese una proyección parcial.
- Backoff real de elegibilidad (1/2/4/8/16 s), 5 fallos -> `failed` visible en overview.
  Los tests adelantan elegibilidad en DB para no dormir; no simulan el paso del tiempo.
- Crash real: un proceso hijo propio pausa **solo en el test**, después del flush
  sin commit. El padre verifica que otro consumidor hace SKIP LOCKED, envía SIGKILL
  al hijo y verifica recuperación/ack único. No es solo una excepción simulada y
  no mata el worker/DB/servicios del usuario. Crash después de commit no se mata
  explícitamente: se comprueba repetición sin efectos tras el ack.
- Consumidores paralelos, lock de hilo, reply anterior a raíz, evidencia por scope,
  alias sin reproyección y detalle de mensajes únicos. No hay merge semántico,
  interpretación general, cierre automático ni efecto externo.
- Reply sin raíz: `pending` con motivo interno `awaiting_root`, sin gastar intentos
  de fallo. Aunque venza su backoff, no compite por el claim hasta existir tarea en
  su propio hilo. Así no bloquea una raíz aceptada después en un loop con polls
  espaciados. El contador pending incluye esa evidencia; no se descarta ni mezcla.
- CLI real en subprocess encola sin procesar; subprocess worker `--once` procesa.
  El loop devuelve la conexión antes del sleep (test explícito).

La API se prueba mediante ASGI TestClient, no se inicia servidor HTTP. El warning
de deprecación upstream TestClient/httpx no se corrige cambiando dependencias aquí.
API/worker/web en Compose, smoke de navegador e imagen backend quedan para tarea 5.

## Operación manual posterior (no ejecutada por estos tests)

```sh
# Contra la DB local elegida y ya migrada: encola, no procesa.
uv run --frozen python -m efren_bot.demo request_video thanks reply
uv run --frozen python -m efren_bot.worker --once
# Sin --once: loop independiente, sleep fuera de transacción.
uv run --frozen python -m efren_bot.worker
```

Para detener únicamente la DB de pruebas conservando su volumen:
`docker compose --project-name efren-bot --profile test stop test-db`.
Nunca usar `down -v` ni detener contenedores de otros proyectos.

## Incremento A: pruebas de trabajo sintético (sin iniciar servicios)

`test_work_contracts.py` y `test_work_storage.py` prueban el contrato `/api/work`,
cinco tablas/migración aditiva, savepoints, hashes/checkpoints, decisión simulada,
concurrencia y recuperación. La limpieza incluye las cinco tablas nuevas en el
mismo TRUNCATE explícito sin CASCADE. Casos negativos rechazan puerto principal o
ausente antes de conectar/migrar/limpiar. No endurecer Settings general: demo usa 55432.

Con TESTDB **ya disponible** y URL local conocida, fijar ambas variables DB
explícitamente (no heredar una URL desconocida) y ejecutar secuencialmente:

```sh
DATABASE_URL="$TEST_DATABASE_URL" UV_OFFLINE=1 uv run --frozen pytest -m integration tests
```

El guard verifica además `current_database()` antes de Alembic. Si no está disponible,
parar y reportar: esta autorización A no permite `make test-db`, Docker up, migrar
la DB principal, desplegar ni arrancar servicios. Las instrucciones Docker anteriores
son operación histórica, no un paso automático de este incremento.

Restart usa factories ASGI/sesiones nuevas sin reset DB y procesos worker `--once`
propios distintos para prepare/finalize/idle. Crash mata solo un hijo propio tras
flush sin commit y demuestra rollback/SKIP LOCKED/recuperación única. El fake no
lanza subprocess ni red; los tests sí pueden lanzar su propio proceso worker.
[Ledger de todos los intentos y ejemplos reales sintéticos](../docs/synthetic-work.md).
