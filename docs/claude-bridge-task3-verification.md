# Claude Slack bridge — evidencia acotada de tarea 3

## Resultado y límite

Tarea 3 implementada y probada localmente el 2026-10-23. **No significa puente
real habilitado, enforcement nativo verificado ni lectura Slack realizada.**
Se conservaron tarea 1/2 y el trabajo web del otro writer. No se hicieron cambios
Git, métricas, deploy, arranque/reinicio de servicios ni cambios de configuración
global/credenciales. La integración de tarea 5 pertenece al coordinador.

- 72 pruebas específicas de tarea 3 incluidas en la regresión final de **254 PASS**.
  Los 254 incluyen los 63 backend originales y cambios HTTP del coordinador;
  no atribuir todos los tests nuevos a este writer. Tarea 2 conserva su evidencia
  histórica de 154 tests y tarea 4 sus 140 tests web (#3842), no repetidos aquí.
- Ruff check PASS y format --check PASS, 42 archivos.
- Runner host idle/pending probado como proceso Python real con perfil sintético
  no aprobado; no conecta API, no lanza cliente y termina limpiamente por SIGTERM.
- Inventario final filtrado: ningún proceso runner/policy/CLI falso, cero señales.
  Los procesos lanzados por tests se esperan/reap y se comprueba extinción del grupo.

## Implementación verificada

- `policy.py`: exec form sin shell, wildcard con `onFailure:block`, allow explícito
  solo para nombre exacto + argumentos JSON byte-canónicos del perfil y permalink
  del snapshot. Session UUID, deadline y perfil revalidado; un intento, presupuesto
  consumido bajo flock antes de allow. Bool/int, extras, otras herramientas, URL,
  segunda llamada y JSON inválido denegados y marcados como violación. Deny/error
  sale 2 con decisión explícita, sin datos sensibles. Snapshot no se modifica.
- `supervisor.py`: argv fijo, `--settings` cerrado validado antes de lanzar,
  `--setting-sources ""`, herramientas built-in vacías, dontAsk, sesión UUID y
  max-turns bounded; no allowedTools/bare/safe-mode/dangerous/fallback. URL solo stdin.
  Hijo recibe allowlist nueva de entorno: HOME oficial solo en host, PATH/locale,
  TMPDIR propio y flags Python/local; ningún secreto HTTP, API key, token exportado,
  proveedor o proxy heredado. No se inspeccionaron archivos de credenciales.
- Stdout/stderr drenados concurrentemente y limitados por separado; no se
  persisten/muestran streams ni pensamiento. Parser cuenta IDs de assistant,
  exige una sola llamada/read success correlacionada con presupuesto del hook y
  JSON final BridgeResult estricto con evidencia igual al permalink. Streams
  incompletos, duplicados, fallidos o sin hook no producen propuesta. Se añade
  advertencia determinista de contexto parcial sin quitar las del modelo.
- Deadline monotónico no se amplía por heartbeat. Watcher permanece activo mientras
  HTTP está pendiente: pruebas separadas de lease y plazo con callback bloqueado
  confirman extinción del proceso antes de 0.85 s para límites de 0.25/0.3 s.
  Cancel/contact loss/output/policy -> TERM al grupo, gracia <=2 s, KILL cuando
  haga falta y reap antes de complete/otro claim. Un heartbeat sin finalizar bloquea
  el siguiente claim; no retry de lectura externa.
- `processes.py`: flock single-instance; journal fsync antes del lanzamiento y
  PID/PGID/start identity del kernel (microsegundos en macOS; boot/ticks en Linux).
  Arranque incierto, grupo vivo o PID reutilizado requieren recuperación manual;
  no se matan procesos desconocidos. Solo se borra journal tras extinción probada.
  Limpieza limitada a archivos temporales propios; nada de borrado recursivo amplio.
- `runner.py`: HTTP outbound exacto `http://127.0.0.1:8000`, sin Origin,
  `trust_env=False`, redirects deshabilitados, límites HTTP y respuestas cerradas.
  Sin DB directa ni retries. Idle pending no publica presencia compatible. Perfil
  ausente/no aprobado/inválido o capability unavailable no hace claim ni modelo.
  Un mismo fingerprint bloqueado no repite probes de metadatos en cada tick idle.
- `capability.py`: hash/versión/flags del cliente revisados antes del run y al
  finalizar; versión mínima 2.1.295, igualdad con versión/hash aprobados. También
  el probe metadata-only tiene caps stdout/stderr de 64 KiB y plazo total de 5 s.

## Gate exacto antes de primera consulta

`capability.assess()` devuelve intencionalmente `policy_verified=False`,
`reason="capability_unavailable"` incluso después de probes locales válidos.
**No hay un flag de entorno, campo HTTP/perfil, mock o attestation inventada que
lo convierta en true.** `Runner.once()` rechaza esa capacidad antes de contactar API.

Faltan un perfil no secreto revisado/aprobado por el operador (tool exacta read-only,
schema/args, conector y modelo reales) y evidencia revisada del cliente nativo que
demuestre hook wildcard exec efectivo/fail-closed y aislamiento del conector frente
a managed/plugins/customizaciones/proveedores alternativos. Hace falta conectar esa
evidencia a un mecanismo de aprobación implementado y revisado; no basta editar
`approved:true` ni quitar el gate. También falta el primer permalink expresamente
elegido/autorizado. No se exige repetir login, auth o diagnóstico de conexión.

Las pruebas falsas de crash/timeout/hook ausente/JSON inválido prueban el supervisor,
presupuesto y protocolo local; **no** observan `onFailure:block` en el Claude real.
El formato stream nativo y las excepciones managed siguen sin certificarse.

Cliente oficial: versión 2.1.309 heredada de tarea 1; mínima del perfil 2.1.295.
En este cierre solo se leyó el binario para SHA256, sin ejecutarlo ni actualizarlo:
`5eadc0009cdcdbc0d06e58110d7b2baf88ced6088b1c33a60a21217fe410619c`.
No presentar ese hash como una nueva prueba de versión, auth o enforcement.

## Registro de checks en orden

Todos fueron **obligatorios**, clasificados antes de ejecutar: fuente AGENTS
(clasificación/conservar fallos/DB separada), contrato §§7–8 y orden del coordinador
(supervisor, permisos, límites, procesos, regresión y cierre). No se ejecutaron
checks opcionales ni se usaron credenciales/conectividad real para rellenar evidencia.
Las llamadas independientes paralelas se enumeran en orden de despacho.

1. Lectura completa AGENTS/contrato/ODD y espejo #3836 antes de fuentes. Cierre de
   tarea 2 concordante: 11162 bytes/FNV139253680; tarea 3 aún pending. Consultas
   oficiales Context7 sobre exec args/onFailure/stream/settings exitosas; no runtime.
2. `uv run --frozen pytest tests/test_bridge_policy.py tests/test_bridge_supervisor.py`
   -> exit0, 45 PASS.
3. `uv run --frozen ruff check src tests migrations` -> exit1, 10 incidencias de
   longitud/imports. Remediación: patch, sin auto-reescritura de archivos ajenos.
4. Tras interrupciones, relectura AGENTS/contrato/ODD/#3836 y #3842 para conservar
   decisiones y evidencia frontend, sin nuevos escritores ni repetir tareas 1/2/4.
5. `uv run --frozen pytest tests/test_bridge_policy.py tests/test_bridge_supervisor.py tests/test_bridge_runner.py`
   -> exit1, 62 PASS/1 FAIL (`toolerror`). Carrera real macOS exit/proc_pidinfo antes
   de reap: solo Popen propio se poll/reap; un retry de identidad después de confirmar
   salida. PID reutilizado sigue bloqueado. Regresión determinista añadida.
6. `uv run --frozen ruff check src tests migrations` -> exit1, 8 incidencias de estilo.
7. `uv run --frozen ruff format --diff src/efren_bot/bridge tests/test_bridge_policy.py tests/test_bridge_supervisor.py tests/test_bridge_runner.py tests/fakes/bridge_cli.py`
   -> exit1, 10 archivos; remediación con patch.
8. `/bin/ps -p 4233 -o pid=,ppid=,pgid=,stat=,comm=` -> exit1 sin salida: PID propio
   del fallo ya ausente; ningún kill ni comando obsoleto esperando.
9. `uv run --frozen pytest tests/test_bridge_policy.py tests/test_bridge_supervisor.py tests/test_bridge_runner.py tests/test_bridge_stream.py`
   -> exit0, 70 PASS; incluye heartbeat bloqueado, idle pending, cancelación, límites,
   política, journal y streams. Añadidos luego 2 tests de caps del probe metadata.
10. `uv run --frozen ruff check src tests migrations` -> exit1, 3 longitudes.
11. `uv run --frozen ruff format --diff src/efren_bot/bridge tests/test_bridge_policy.py tests/test_bridge_supervisor.py tests/test_bridge_runner.py tests/test_bridge_stream.py tests/fakes/bridge_cli.py`
    -> exit1, 3 archivos. Remediación con patch; no fallo funcional nuevo.
12. `DATABASE_URL='postgresql+psycopg://efren_bot:local_demo_only@127.0.0.1:55433/efren_bot_test' uv run --frozen pytest tests`
    -> exit0, **254 PASS**. DB guard existente exige exactamente efren_bot_test antes
    de conectar/migrar/truncar. Advertencia Starlette/httpx heredada no bloqueante;
    no se instaló una dependencia para ocultarla. No DB demo ni efectos externos.
13. `uv run --frozen ruff check src tests migrations` -> exit0 PASS.
14. `uv run --frozen ruff format --diff src tests migrations` -> exit1, un archivo
    metadata pendiente de formato. Patch solo de formato, sin cambio funcional.
15. Lectura hash con el comando siguiente -> exit0, digest anterior. Sin invocar CLI.
16. `uv run --frozen ruff check src tests migrations` -> exit0 PASS.
17. `uv run --frozen ruff format --check src tests migrations` -> exit0, 42 archivos.
18. Inventario filtrado con el comando siguiente -> exit0,
    `matching_bridge_processes:[]`, `signals_sent:0`.
19. Reconciliar tracking actual del padre antes de guardar tarea 3: preservar sus
    nuevas tareas 4/5 y fix HTTP (#3851), no restaurar una versión vieja. Guardar
    espejo entero #3836 y readback disco/memoria al cerrar -> ambos 16976 bytes,
    FNV-1a3345943716. SHA256 disco:
    `3eaff58fcbe84d8c27f4d8b81f0fc1ea1b8d1ef53f84c076ec2f9aa8314b85e7`.
    Antes del cierre ambos coincidían en14526bytes/FNV2356113781; SHA256 disco
    `59e06f2856c06918f20220fd6d861aad66c656e8922f77a9a58575aa277e187a`.
    Comando disco de ambas comprobaciones: `python3 -c` leyendo solo el tracking,
    SHA256 con hashlib y FNV con la misma función que el readback Engram.

Comando exacto del punto 15:

```sh
uv run --frozen python -c 'from pathlib import Path; from efren_bot.bridge.capability import binary_digest; print({"cli_sha256": binary_digest(Path("/Users/efren.herrera/.local/bin/claude")), "minimum_version": "2.1.295", "version_previous_evidence": "2.1.309; not executed in this check"})'
```

Comando exacto del inventario (no imprime argv ni procesos ajenos):

```sh
python3 - <<'PY'
import json
import os
import subprocess
rows = []
for line in subprocess.check_output(['/bin/ps', '-axo', 'pid=,ppid=,pgid=,command='], text=True).splitlines():
    parts = line.strip().split(None, 3)
    if len(parts) == 4:
        rows.append((int(parts[0]), int(parts[1]), int(parts[2]), parts[3]))
parents = {pid: parent for pid, parent, _, _ in rows}
ancestors = set()
pid = os.getpid()
while pid and pid not in ancestors:
    ancestors.add(pid)
    pid = parents.get(pid, 0)
patterns = {'fake_cli': '/tests/fakes/bridge_cli.py', 'policy': ' -m efren_bot.bridge.policy', 'runner': ' -m efren_bot.bridge.runner'}
found = [{'pid': pid, 'ppid': parent, 'pgid': group, 'kind': kind}
         for pid, parent, group, command in rows if pid not in ancestors
         for kind, pattern in patterns.items() if pattern in command]
print(json.dumps({'matching_bridge_processes': found, 'signals_sent': 0}))
PY
```

## Handoff

El coordinador conserva `docs/claude-bridge-verification.md` y el despliegue/API/web
de tarea 5. Este writer no los arrancó ni modificó frontend. Pendiente smoke
integrado API/host con CLI falso y primera consulta real solo tras los gates
anteriores. Ningún proceso de prueba/runner/policy de este encargo queda vivo.

### Adenda posterior TAREA5

El gate estático descrito en este cierre histórico fue reemplazado después por
aprobación host ligada a evidencia nativa y revisión efectiva. Véanse la adenda de
`claude-bridge.md` y el tramo posterior de `claude-bridge-verification.md`.
No cambia los 254/72 PASS históricos ni los convierte en evidencia nativa. El
tramo posterior tiene 293 backend PASS; perfil/review/proof reales ausentes,
`profile_missing`, cero ensayos de modelo nativo y cero lecturas Slack.
