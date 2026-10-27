# Claude Slack bridge — evidencia de verificación parcial

Lectura cronológica: cada tramo conserva el estado observado entonces. El estado
actual y la siguiente acción están en la **adenda final de cierre parcial**; #3878
es un bloqueo OAuth histórico, ya superado por renovación manual. Las
menciones anteriores a writers activos o autorizaciones pendientes son históricas.

## Alcance y procedencia

Consolidación documental observada a **2026-10-23T15:50:06Z** (`date -u`); no es la hora exacta final de los checks delegados. Inicio del tramo runtime del padre reportado: **2026-10-23T15:37:56Z**. Identidad `claude-slack-bridge`, proyecto Engram `efren-bot`.

Fuentes: #3842 (frontend ses_e985b97fcffefJCUT39MNxwvD6), #3848 (deploy), #3851 (corrección HTTP ses_e968ff6ccffeTovx6M0SrFsVW2), y resultados Docker/browser suministrados por el padre. Evidencia previa de tareas 1/2 permanece en `docs/claude-bridge.md`, `.odd/claude-slack-bridge.md` y espejo #3836; este documento no reescribe historia `base-local`. No se leyeron fuentes, pruebas ni procesos del writer activo de tarea 3.

**Estado actual:** todos los writers terminaron; hitos 1–4 conservados, tarea 5 **PARCIAL**, tarea 6 **PENDIENTE**. API/web propios arriba con el código último desplegado; demo 1 tarea/3 actividades preservada. Auth CLI renovada/Slack connected y metadatos oficiales acreditados; no se ha leído ningún hilo Slack. Puente deshabilitado por política/opt-in sin perfil aprobado, no por fallo de conexión. Enforcement nativo real, perfil/revisión y primer hilo siguen pendientes; riesgo formal/Git/cierre global diferidos. El usuario eligió «Lo compartiré después»: esperar sin volver a pedir hilo/workspace.

## Clasificación previa de las comprobaciones

- **Obligatorias — frontend:** orden TAREA4, criterios UI/regresión del ODD y `docs/claude-bridge.md` §8; clasificación y secuencia conservadas de #3842.
- **Opcional — revisión independiente:** ses_e9848d466ffeWyE2tSjaldmNkI, revisión frontend estática readonly: 19 checks, 0 hallazgos, sin tests extra. No reemplaza riesgo formal ni pruebas runtime.
- **Obligatorias — despliegue:** orden DEPLOY LOCAL, `AGENTS.md` (clasificación/aislamiento), contrato §4/6/8; #3848 no ejecutó opcionales. SQL de conservación exclusivamente readonly; no tests sobre DB demo ni repetición de tests en fuentes mutables.
- **Obligatorias — corrección HTTP:** reproducción del bug real de integración y contrato de status público; pruebas HTTP aisladas y Ruff según #3851. No PostgreSQL ni truncates con writer activo.
- **Obligatorias — runtime posterior:** orden expresa del padre: reconstruir solo API y comprobar el mismo browser real sin introducir secretos, tras el fix. No diagnóstico independiente de auth/MCP/Slack.
- **Obligatorias — esta consolidación:** instrucción de reconciliar disco/memoria, patch dirigido, relectura de ambos documentos, espejo completo desde disco actual y readback/comparación. Sin ejecutar tests, servicios ni métricas en esta sesión documental.

## Tarea 4 — frontend completado

Cambios solo en `apps/web/`; sin dependencias nuevas ni cambios de package/lock. Panel bajo demo, propuestas escapadas y no validadas, fuente exacta del permalink, presentación America/Merida. Secreto propio solo en memoria; no cookies/storage/query. Limpieza y abort en clear/pagehide/unmount, 401 limpia secreto, replay usa misma UUID/payload y nueva lectura requiere acción manual. Cancelación y polling secuencial controlan carreras/stale/visibilidad. Guard proxy conserva Host/Origin, rechaza duplicados/contextos inválidos, elimina forwarded y bloquea runner/aliases.

Secuencia **obligatoria**, cwd `apps/web/`, resultados y remediaciones de #3842:

| Orden | Comprobación | Resultado / remediación |
| --- | --- | --- |
| 1 | `npm run typecheck` | exit0 |
| 2 | `npm test -- --run` | exit1: 129 PASS / 1 FAIL en 6 archivos. Mock cancel devolvía cancel_requested false tras cancelar; fixture corregido y tests de carreras añadidos. |
| 3 | Typecheck | exit0 |
| 4 | Vitest | exit0: 136 tests / 7 archivos |
| 5 | `npm run build` | exit0 con warning configLoader native/import sin extensión; corregidos import `.ts` y allowImportingTsExtensions. |
| 6 | Typecheck | exit0 |
| 7 | Vitest | exit1: 138 PASS / 2 FAIL. Response consumida reutilizada y toHaveProperty sobre headers undefined; corregidos Response nueva por llamada y Headers.has. |
| 8 | Typecheck | exit0 |
| 9 | Vitest | exit0: **140 tests / 7 archivos** |
| 10 | Build | exit0 **sin warning**, 116 módulos, CSS 7.58 kB / JS 331.86 kB |
| 11 | `node --version` | exit0: v26.0.0 |
| 12 | `npm --version` | exit0: 11.12.1 |

README posterior solo documental. Sin npm ci/instalaciones/global, Docker, Git ni métricas. Mocks y tests unitarios del guard no verifican backend/DB/proxy HTTP real/Claude/Slack. Revisión opcional independiente: 19 checks estáticos/0 hallazgos, sin tests adicionales.

## Tarea 5 — despliegue local parcial (#3848)

Orden de fases **obligatorias**, con comandos/scripts completos y SQL preservados en #3848; no se inventan aquí invocaciones no suministradas:

1. En paralelo, `docker compose --project-name efren-bot config --quiet`, `docker compose --project-name efren-bot ps --all` y SQL readonly de migración/tablas: todos exit0. Baseline HEAD `0001_local`, siete tablas demo, sin bridge; API/worker/web viejos.
2. En paralelo, SQL readonly de conteos y HTTP script urllib: ambos exit0. Demo events3/messages3/threads2/tasks1/activities3/outbox3, provider fixture3. Overview 200; bridge/status **404 baseline**, task UUID `5f6f87cb-d19a-4e1c-85ff-75c4ce8acec8`.
3. `docker compose --project-name efren-bot up --build --detach --wait --wait-timeout 90` (timeout externo 300000 ms): **exit0 al primer intento**. Warning useradd UID10001 > SYS_UID_MAX999 no fatal; sin remediación necesaria. DB demo/test existentes preservadas, sin override ni nuevos montajes host.
4. En paralelo, SQL readonly postmigración, `docker compose --project-name efren-bot exec -T api alembic heads`, logs migrate y smoke HTTP: exit0. HEAD **0002_bridge**, tablas `bridge_runs`/`bridge_presence` creadas y ambas vacías; conteos demo idénticos. Log migrate vacío no se tomó como prueba: SQL y alembic certificaron migración.
5. En paralelo, estado Compose e inspección limitada de contenedores/HTTP: exit0. API/DB demo55432/DB test55433 healthy; web/worker running, **sin healthcheck propio**, HTTP web200; migrate exited0. Todos restart0/exit0; API/web/worker/migrate sin montajes; DB solo datos PostgreSQL.
6. SQL readonly final: exit0, bridge_runs0/bridge_presence0/events3/tasks1 tras negativos.

Smoke HTTP de #3848, en orden: web `/` 200; status vía web con **Origin explícito** + Sec-Fetch-Site same-origin 200/no-store (`enabled:false`, `configuration:disabled`, `reason:disabled`); health/ready web y API 200; Origin evil 403; runner/claim vía web 403; create sin auth 401 usando permalink sintético (sin visita ni persistencia); overview 200 con demo original. Después: Host malicioso API403, Sec-Fetch-Site cross-site web403, status API con Origin explícito200. Esto no cubría el GET real del browser sin Origin.

No fallos de checks/reintentos de deploy. El 404 inicial era baseline esperada, resuelta por reconstrucción autorizada. API http://127.0.0.1:8000, web http://127.0.0.1:5173; servicios dejados arriba. No CLI/runner/modelo/hook real/Slack, lectura de secretos/perfiles, auth/MCP/update ni habilitación.

## Defecto real browser y corrección contractual (#3851)

El padre abrió http://127.0.0.1:5173 en OpenChamber: GET same-origin del browser **sin Origin y sin Bearer** devolvía 401 y mostraba secreto inválido antes de introducir token. No era un fallo de Slack ni falta de login.

Fix delegado acotado a `src/efren_bot/bridge/http.py` (condición de auth), `tests/test_bridge_http.py` y aclaración §4 de `docs/claude-bridge.md`. El status público sin PII admite fallback **Host web válido + metadata same-origin** sin Bearer; no elimina controles Host/Origin. Status conserva solo cuatro campos; runs/create/cancel/unknown siguen auth401, runner desde web403, Origin malicioso/null, host API sin Origin, cross-site y contexto duplicado siguen403. Sin relajación de permisos Slack ni cambio de perfil/DTO/readiness.

Secuencia **obligatoria** de #3851:

1. Comparación readonly tracking/espejo PASS (11162 bytes/FNV1a139253680 en ese momento).
2. `uv run --frozen pytest -q tests/test_bridge_http.py -k 'browser_public_status_without_origin_or_bearer or public_status_does_not_require_available_token'`: exit1, **7 FAIL / 3 PASS / 43 deselected**, reprodujo 401.
3. Patch acotado.
4. `uv run --frozen pytest -q tests/test_bridge_http.py`: exit0, **53 PASS**.
5. `uv run --frozen ruff check src/efren_bot/bridge/http.py tests/test_bridge_http.py`: exit0.
6. `uv run --frozen ruff format --check src/efren_bot/bridge/http.py tests/test_bridge_http.py`: exit0, 2 archivos ya formateados.

Advertencia heredada Starlette/httpx, no bloqueante. Pruebas SQLite prohíben SQL; sin PostgreSQL/default DB/truncates. Regresión backend completa diferida para no interferir writer activo de tarea 3; no reutilizar los 154 PASS históricos como certificación de esta integración final.

## Runtime obligatorio del padre después del fix

1. `docker compose --project-name efren-bot up --build --detach --no-deps --wait --wait-timeout 60 api`: **exit0 primer intento**, solo API recreada y healthy. Warning UID10001 heredado no fatal.
2. Misma pestaña de verificación OpenChamber, recarga tras fix: snapshot correcto **«Deshabilitado»**, **«El puente está deshabilitado. La demo sigue disponible.»**, botón **Consultar deshabilitado**. Demo conserva 1 tarea y el hilo de 2 mensajes, presentación Mérida. Antes del fix mostraba 401/secret invalid. No se introdujeron tokens ni URLs Slack reales.

Pestaña `browser:agent:1792770254788-3` dejada abierta por instrucción; la cerrará el padre. Comprobaciones reportadas por el padre, no repetidas por esta sesión documental. No se dispone de hora exacta final del runtime; no inferirla del reloj de consolidación.

## Pendientes y frontera de seguridad

- Tarea 3: writer activo `ses_e985d0d90ffeVSBeFMqUkDmQxT` es dueño de su estado y cierre. Esta consolidación no inspecciona ni certifica su implementación/procesos/pruebas.
- Después: integrar protocolo host/runner y smoke con **CLI falso**, más regresión final coordinada. El CLI falso no prueba enforcement del cliente real ni Slack.
- Perfil real no secreto revisado/aprobado, barrera fail-closed y enforcement nativo efectivo siguen pendientes. No habilitar basándose en logs, versión o healthy de API.
- Primera lectura real requiere hilo expresamente elegido por el usuario. No repetir diagnóstico login/MCP ni pedir otro login para continuar el ejecutor/API autorizado.
- No consultas Slack reales, hooks/modelo reales ni habilitación en la evidencia aquí consolidada. Sin fallback API/modelo/proveedor, credenciales/HOME en Docker, efectos automáticos en tareas ni cambios de fixture.
- Riesgo formal y entrega global siguen abiertos. Git intacto, sin métricas; solo este archivo y tracking de esta feature modificados por esta sesión. Historia/evidencia `base-local` intacta.

## TAREA5 — ejecutor host y aprobación basada en evidencia (tramo posterior)

Adenda posterior a la consolidación anterior: tarea 3 ya cerró su alcance local
con 254 PASS, según `claude-bridge-task3-verification.md`. No se borra su límite
histórico: entonces `assess()` devolvía siempre false. Este tramo implementa el
mecanismo que faltaba, **sin declarar verificado el cliente nativo ni Slack**.
Tareas 1/2/3/4 conservan sus hitos; tarea 5 sigue parcial y tarea 6 abierta.

### Resultado implementado, no una habilitación ficticia

- `make bridge-verify-policy` ejecuta una implementación nativa real, no un echo:
  tres invocaciones máximas, dos turnos/30 s cada una, MCP stdio fixture único,
  baseline positivo y casos deny/default, presupuesto, crash/missing/timeout/JSON.
  Requiere intentos y ejecución/ausencia observados, hook events e init nativo
  compatible. Una negativa del modelo o un ensayo incompleto no aprueban.
- Antes: perfil real y revisión host de entorno personal/unmanaged. El corte es
  conservador: macOS, sin fuentes managed/MDM/cache remoto ni política desconocida.
  No se deduce el tipo de suscripción mediante auth. Una revisión humana explícita
  forma parte de la frontera de confianza; no es una certificación automática.
- Firma Apple estricta del binario Anthropic y hash/versión, Python, settings,
  fuentes y revisión vinculados a receipt local HMAC, TTL24h y confirmación del
  digest completo por terminal. No importación de proofs, flag de riesgo, bool
  editable, API/web de aprobación ni sustitución de ejecutable por env. El HMAC
  protege contra edición/mezcla accidental, no contra el operador dueño del secreto.
- El MCP fixture y `--strict-mcp-config` se usan **solo en el ensayo**. No prueban
  aislamiento del conector de producción. Este depende además de revisión humana,
  rechazo de managed/customizaciones y settings/flags cerrados del supervisor.
  No se copiarán OAuth ni config global a un servidor alternativo.
- `assess()` puede devolver true solo con receipt vigente y compatible; el runner
  revalida antes de claim/ejecución/heartbeat/complete. Detecta llegada/cambio del
  receipt sin reiniciar por un booleano cacheado. Ausencia deja pending sin CLI/API.
  `bridge-up` también valida proof y devuelve códigos concretos antes de Compose.
- Settings cierran plugins y desactivan sync de plugins/skills Claude.ai, conservan
  hooks y conector. API/DTO/guard público no se tocaron; frontend y DB demo intactos.

### Checks obligatorios en orden, con fallos y remediación

Fuente de todos: orden TAREA5, `AGENTS.md`, criterios ODD y contrato §§7–8/adenda.
No hubo checks opcionales. Paralelos enumerados por despacho; solo DB separada
`efren_bot_test:55433`, sin otros writers ni servicios iniciados/reconstruidos.

1. Readback previo tracking/#3836: primera extracción de memoria omitió LF
   (16975 bytes), corregida antes de writes; disco/memoria **16976 bytes,
   FNV1a3345943716**. Lecturas de contrato completo, evidencia T3, perfil/config,
   política/capacidad/preflight/supervisor/runner/tests. No índices ni HOME scan.
2. Context7 y páginas oficiales CLI/hooks/managed-MCP/managed-settings/server-managed
   consultadas. Confirman merge de allowlists, excepciones MCP y locks de hooks:
   un ensayo strict toy no certifica producción. No auth/MCP diagnostics.
3. `codesign -dv --verbose=2` sobre binario resuelto, stderr filtrado únicamente a
   Identifier/Format/Authority/TeamIdentifier: exit0, identifier
   `com.anthropic.claude-code`, Anthropic PBC `Q6L2SF6YDW`. Metadata, no hooks.
4. `uv run --frozen pytest tests/test_bridge_proof.py tests/test_bridge_policy.py tests/test_bridge_supervisor.py tests/test_bridge_runner.py tests/test_bridge_stream.py`
   -> exit0, **93 PASS**. En paralelo Ruff check -> exit1, 21 estilo/imports;
   format --diff -> exit1, seis archivos. Remediación con patch, sin auto-rewrite.
5. Tras correcciones: `uv run --frozen ruff check src tests migrations` -> exit0;
   `uv run --frozen ruff format --diff src tests migrations` -> exit0, 46 archivos.
6. Añadidos smoke API–runner–supervisor con **proceso CLI falso**. Comando DB de
   abajo -> exit0, **277 PASS**. Ruff -> exit1, cuatro estilo/imports del smoke;
   format --diff storage -> exit1, un archivo. Corregidos con patch.
7. Añadidos 16 rechazos de fuentes managed/config nativa desconocida; mismo comando
   DB -> exit0, **293 PASS**. Ruff -> exit1, dos longitudes; format --diff -> exit1,
   un archivo. Corregidos con patch.
8. `make bridge-verify-policy` -> make exit2 / módulo exit1, **negativo esperado**:
   `bridge-verify-policy blocked: profile_missing`. No Claude/modelo/proof creados.
9. Check operativo firma+idle inicial -> exit1 AssertionError **antes de arrancar
   runner**. Diagnóstico limitado de codesign -> exit1: `invalid requirement
   specification`; interpretaba el requisito inline como nombre de archivo. No
   era evidencia de binario modificado ni fallo OAuth. Corrección: prefijo `=`
   en requisito inline, manteniendo `--verify --strict`, anchor Apple, identifier
   y Team ID; test de regresión de argv añadido.
10. Repetición del script operativo -> exit0: requisito Apple estricto PASS;
    proceso Python host real anuncia `bridge-runner pending: profile_missing`,
    permanece vivo idle, TERM/grupo/reap limpios exit0, stdout adicional/stderr
    vacíos. Sin active journal, proof o perfil inventado. Runner no queda vivo.
11. Repetición final del comando DB -> exit0, **293 PASS** (incluye 53 HTTP del
    fix público y 63 originales). `uv run --frozen ruff check src tests migrations`
    -> exit0; `uv run --frozen ruff format --check src tests migrations` -> exit0,
    **46 archivos**. Warning Starlette/httpx heredado no bloqueante, sin instalar
    paquetes para ocultarlo.
12. Inventario final mediante `ps` filtrado a procesos propios bridge/fake/policy/
    verify_fixture -> exit0: ninguno, cero señales. Solo lstat del token: regular,
    own, 0600, 65 bytes; directorio0700. Perfil/review/proof/journal ausentes.
    No se leyó ni imprimió el contenido del token en este inventario.
13. Relectura documental/tracking y espejo completo #3836, comparación final al
    coordinador. Algunos patches iniciales fallaron por contexto antes de aplicar
    cambios; se releyó y aplicó el patch correcto, sin escrituras parciales.

Comando exacto de regresión (tres ejecuciones, 277/293/293 PASS):

```sh
DATABASE_URL='postgresql+psycopg://efren_bot:local_demo_only@127.0.0.1:55433/efren_bot_test' uv run --frozen pytest tests
```

Los dos smokes son protocolo ASGI/TestClient + transporte httpx de pruebas + DB
PostgreSQL real separada + procesos Python CLI falsos. Verifican idle/claim,
heartbeat, complete, éxito y wrong-URL denegado, replay sin relanzar, reap y no
mutación fixture. **No son tráfico HTTP loopback real ni cliente Claude/Slack**.
Las pruebas de recibos usan identidades sintéticas en temporales del test, no
certifican el binario instalado ni generan aprobación en `.local/bridge/`.

### Hold operativo y siguiente acción concreta

Resultado actual: **`profile_missing`**, comprobado por el comando real. No existen
`profile.json`, `policy-review.json` ni `policy-proof.json` reales; cero ensayos de
modelo nativo y cero lecturas Slack en este tramo. Se conserva el secreto propio
existente sin sobrescribir. No se ha cambiado configuración global ni desplegado
servicios; el padre integra una última vez. API/web siguen con enable default false.

Procedimiento disponible en la adenda de `docs/claude-bridge.md`: aportar perfil
real revisado, completar revisión no secreta fuera del browser, ejecutar
`make bridge-verify-policy` en terminal; solo después `make bridge-up` y
`make bridge-runner`. No hay pasos de login/reconexión ni credenciales nuevas.
Si el entorno es Team/managed/desconocido, este corte bloquea en vez de declararlo
personal o vacío; no modificarlo para forzar un PASS.

La única decisión que puede requerir autorización adicional es **obtener únicamente
los metadatos no secretos (URL de servidor, nombre exacto y schema de herramienta
read-only del conector existente), sin buscar/leer Slack ni diagnosticar auth**,
si el operador no dispone ya del perfil revisado. No inventar esa interfaz. Una
herramienta que no reciba el permalink exacto en una llamada sigue unsupported.
Después queda pendiente el primer hilo expresamente elegido por el usuario.

## Adenda de metadatos y reset documental del requisito de schema

Esta adenda es posterior a los tramos históricos anteriores: **todos los writers
han terminado**. Hitos 1–4 conservados; tarea 5 **PARCIAL**, tarea 6 **PENDIENTE**.
No se vuelve a ejecutar producto, CLI, modelos, Slack, auth, servicios, Git ni
métricas. No hay perfil/review/proof aprobado, metadatos acreditados ni primer
permalink del usuario. El puente no se habilita por este cambio documental.

### Contrato local, no exportación remota obligatoria

Revisión de referencia `ses_e965ff1cfffeqVVZBkFzT9Md1l`, evidencia de
`profile.py:259–263` y `policy.py:122–139` aportada para esta unidad, sin releer
fuentes: `input_schema` es el **contrato local cerrado de admisión construido a
partir de la interfaz oficial revisada, no exportación completa del schema remoto**.
El código valida ese contrato local, no obtiene/compara schema upstream. La
barrera es igualdad total del tool name y argumentos JSON canónicos, URL del
usuario inmutable y consumo atómico de un intento. Exigir exportación completa
no añade scope control y puede hacer incompatibles schemas remotos legítimos
con propiedades opcionales. Se resetea solo esa exigencia autogenerada; no se
cambia schema ni restricción funcional, ni se reescribe evidencia histórica.

Siguen obligatorios `tool_name`, `server_url` exacta (nunca fallback `serverName`),
fingerprint, `approved`, revisión read-only, revisión host y prueba nativa,
deny-all/una llamada y HTTP/Host/Origin/JSON/auth. No inferir nombres de herramientas
ni usar texto de modelo como autoridad. Perfil aprobado y tests falsos no prueban
enforcement real; no se elimina ninguna restricción Git ni de suscripción/secretos.

### Intentos de metadatos preservados, en orden

1. **Autorización #3860:** el usuario eligió «Sí, obtener metadatos», solo URL del
   servidor y nombre/schema de herramienta de lectura existente. No autorizó
   mensajes Slack, nuevo auth, configuración global ni una primera lectura real.
2. **ses_e9664673affeOhnj5E5RNf6VwQ / #3862:** checks obligatorios por alcance:
   `claude --help` exit0; `claude mcp --help` exit0 (paralelo con consulta Context7);
   dos consultas oficiales Context7 sobre metadata/MCP; `claude mcp get --help`
   exit0. Ayuda documenta health-check automático de get/list y no ofrece
   `toolSchema` ni opción para omitirlo en get. **Get/list no se ejecutaron entonces**.
   `system.init.tools` contiene nombres, no schema. Sin modelos, Slack ni metadata
   exportada. No fallos/reintentos de comandos; documentos/espejo fueron contexto
   opcional en esa sesión. Su anterior petición de exportación completa no pasa a
   ser requisito: aplica la precisión local de esta adenda.
3. **Seguimiento ses_e965c62d4ffeqtCce3a1aG2z2Q / #3864:** autorización acotada
   posterior permitió get con handshake automático incidental, no diagnóstico
   standalone de auth. Hubo **exactamente dos operaciones oficiales**:
   - Primera, obligatoria por autorización: `claude mcp get "claude.ai Slack"`,
     subprocess con streams en memoria, timeout30 s, grupo propio: **exit1**,
     `selected_metadata={}`. El nombre era ejemplo documentado, no conector local
     observado. Streams descartados; **no se preservó diagnóstico**. No permite
     afirmar NotFound, inexistencia de Slack ni fallo de autenticación.
   - Segunda y última, obligatoria por autorización: CLI interactivo con settings
     propios deny-all, PreToolUse wildcard exit2/onFailure:block, sin built-ins,
     permisos dontAsk y sin prompts, sin persistencia ni Chrome. **Exit1 antes del
     menú**, `stages=[]`, `selected_metadata={}`; **`/mcp` no llegó a enviarse**.
     Streams descartados; causa no preservada. No demuestra que el CLI o la vía
     manual sean imposibles. No reintento ni aceptación de trust/auth/permisos.
   - Contexto documental opcional: Context7 oficial; búsqueda web de documentación
     Slack cancelada (`Web search cancelled`), sin resultado ni remediación. No se
     tomó un servidor tercero como autoridad. Orden: lecturas, docs, get, docs/web,
     CLI interactivo. Ambos procesos reaped; harness temporal propio eliminado.

No hubo mensajes/hilos, modelos, credenciales, cambios globales ni Git en estos
intentos. No se creó archivo de metadatos (`discovered-metadata.json`) ni perfil
aprobado/review/proof. No se construyó siquiera un schema local candidato. Los
exit1 se conservan como fallos sin diagnóstico, no como evidencia sobre auth.

### Siguiente paso del usuario, no ejecutado aquí

Desde su sesión **habitual** de Claude Code: `/mcp` → Slack → lista/detalle de
herramientas (`View tools` si aparece). El menú está respaldado por documentación
oficial, **no observado en esta instalación**; no se garantiza el texto/layout.
Compartir solo nombre canónico de herramienta de lectura, descripción y parámetros
oficiales, y URL del servidor sin credenciales si es visible. No se exige exportar
JSON completo, ni compartir capturas crudas/tokens/headers/emails/credenciales.
Detenerse si aparece login o petición de nuevos permisos. Si no se ven los datos,
dejar pendiente: no improvisar nombres/URL ni abrir un workflow Slack directo.

Falta acreditar interfaz **permalink exacto → hilo en una llamada** y endpoint,
no diagnosticar conexión. Después: perfil real y revisión humana read-only/host,
prueba nativa de la barrera y primer permalink elegido por el usuario (aún no
aportado), fuera del alcance de esta unidad. Última integración y riesgo formal
siguen pendientes; Git/cierre global/métricas no autorizados.

### Comprobaciones de esta unidad documental

Todas **obligatorias** por encargo doc-only y `AGENTS.md`; ninguna opcional ni
check de producto. Orden de ejecución:

1. `read AGENTS.md`, documentos del puente y ODD completos; Engram context y
   `mem_get_observation(3836/3862/3864)`. Después `read docs/contract.md` y
   `read docs/architecture.md`, `mem_get_observation(3860)`. PASS: excepción
   separada de fixture; constraints y evidencia histórica identificados.
2. Python stdlib readonly sobre ODD y readback #3836: baseline igual, **18962 bytes,
   FNV1a4152736568**, SHA256 disco
   `f8813944c77dbf7cbbd4d8d939a5714d4f8f4821566b701eca04fbcee2a86759`.
   Sin LF perdido, fallos ni writes previos a igualdad.
3. Patch dirigido de los tres documentos permitidos, relectura y cotejo del
   contrato actual/futuro: no exigir exportación completa upstream, sí interfaz
   oficial y todas las barreras anteriores; referencias y 1–4/5parcial/6pending.
4. Check documental readonly con Python stdlib y búsqueda dirigida; guardar ODD
   completo en `odd/claude-slack-bridge/tasks` y readback de disco/#3836. Resultado
   final e igualdad se reportan al coordinador, sin introducir un hash autorreferente
   en el propio tracking. Ningún runtime se certifica por estas comprobaciones.

La búsqueda dirigida `grep` de `schema|Schema|export|serverName|View tools|ses_e965|386[024]`
en `docs/claude-bridge*.md` permitió revisar las menciones en contexto: ninguna
exige exportación upstream completa como condición actual/futura. Las peticiones
históricas se delimitan expresamente con el reset. Resultado PASS sin remediación.

Comando documental del paso 4 (obligatorio, fuente encargo/AGENTS; **exit0 PASS**,
sin fallo ni reintento; no importa fuentes ni ejecuta checks de producto):

```sh
python3 -c 'from pathlib import Path; import hashlib, re; c=Path("docs/claude-bridge.md").read_text(); v=Path("docs/claude-bridge-verification.md").read_text(); p=Path(".odd/claude-slack-bridge.md"); o=p.read_text(); n=lambda s:" ".join(s.split()); assert "contrato local cerrado de admisión construido a partir de la interfaz oficial revisada, no exportación completa del schema remoto" in n(c).replace("**", ""); assert all(x in c for x in ("tool_name", "server_url", "profile_fingerprint", "approved=true", "read-only", "prueba nativa", "deny-all", "max_tool_calls=1", "Host/Origin", "application/json", "Authorization: Bearer", "onFailure:block", "lock atómico **antes** de allow")); assert all(x in v for x in ("ses_e965ff1cfffeqVVZBkFzT9Md1l", "ses_e9664673affeOhnj5E5RNf6VwQ", "ses_e965c62d4ffeqtCce3a1aG2z2Q", "no se preservó diagnóstico", "`/mcp` no llegó a enviarse", "no observado en esta instalación", "View tools", "Web search cancelled")); tasks=o.split("## Tasks\n",1)[1].split("## Findings",1)[0]; assert tasks.count("- [x]")==4 and tasks.count("- [ ]")==2 and "PARCIAL" in tasks and "pending" in tasks; assert all(Path(x).is_file() for x in ("AGENTS.md", "docs/contract.md", "docs/architecture.md", "docs/claude-bridge.md", "docs/claude-bridge-verification.md", "docs/claude-bridge-task3-verification.md", ".odd/claude-slack-bridge.md")); assert "no exigir exportación JSON completa" in o; assert all(sum(line.startswith(chr(96)*3) for line in s.splitlines())%2==0 for s in (c,v,o)); b=p.read_bytes(); h=2166136261
for x in b: h=((h^x)*16777619)&0xffffffff
print("PASS: concordancia documental local, controles, referencias, fences y milestones; sin runtime"); print({"bytes":len(b),"fnv1a":h,"sha256":hashlib.sha256(b).hexdigest()})'
```

El primer check pasó antes de incorporar su literal. La repetición final usa
conteo de fences al inicio de línea (no backticks dentro del propio comando);
ambos checks documentales exit0, sin fallos. Hash final del mirror solo en informe
al coordinador. Descubrimiento separado guardado en #3866, sin conflictos pendientes.

## Adenda — fix mínimo del gate de help oculto (2026-10-23)

Alcance delegado: únicamente `capability.py` y `tests/test_bridge_supervisor.py`
como fuentes; documentación y tracking compañeros. Sin cambios de supervisor,
JSON/server/perfil, estados/aprobaciones, UI, DB demo, servicios ni Git.
El diagnóstico #3872 acreditó help2.1.309 sin `--max-turns`: defecto **latente**
tras perfil/proof, no causa demostrada de disabled/profile_missing ni de exit1 MCP.

El fix conserva FLAGS y separa una excepción fija `DOCUMENTED_HIDDEN_FLAGS` con
solo `--max-turns`; no acepta flags arbitrarios. Regresión independiente de help
sin ese flag pasa; cada uno de los otros 15 flags ausente sigue rechazando.
Comprueba también argv con `-p`/`--max-turns`/valor validado y `assess()` sin proof
todavía false/`policy_proof_missing`, sin nuevas invocaciones. Hash/versión mínima
y exacta, firma, revisión, aprobación nativa y hooks siguen intactos.

### Clasificación previa y secuencia exacta

Todas **obligatorias**, clasificadas antes de ejecutar por encargo del fix y
`AGENTS.md`; fuente adicional regresión: ODD/contrato y guard canónico
`tests/conftest.py:require_test_database` (antes de conexión/migración/TRUNCATE y
comprobación SQL de `efren_bot_test`). No checks frontend repetidos: fuentes
intactas, evidencia140 histórica conservada. Cwd: raíz del proyecto.

1. Lecturas AGENTS/ODD/#3836/#3872, fuentes y pruebas equivalentes. Baseline
   disco **21914 bytes/FNV1a2248232259**, SHA256
   `1e0e095e5fdf2cd608c079686caf66247e740613eacfc6b04a414a840b560b6b`.
   Primera extracción del envelope sin LF dio21913bytes/FNV1864602523; se restauró
   LF antes de writes y readback dio igualdad exacta21914/FNV2248232259.
2. Context7 resolve Claude Code y tres query-docs oficiales `/websites/code_claude`
   sobre help/flags/turnos; referencia oficial confirma help no exhaustivo.
   Corroboración documental posterior al paso8 mediante fetch público
   `https://code.claude.com/docs/en/cli-reference.md` HTTP200: `--max-turns`
   print-only, error al alcanzar límite; `--permission-prompts none` >=2.1.259.
   Versión instalada2.1.309 procede de #3872, **no nueva ejecución CLI**.
3. `docker compose --project-name efren-bot --profile test ps test-db` -> exit0,
   test-db healthy en127.0.0.1:55433; no arranque/recreación. Padre sin DB writers.
4. Añadida regresión, antes del fix:
   `uv run --frozen pytest -q tests/test_bridge_supervisor.py -k hidden_max_turns`
   -> **exit1: 1 FAIL/15 PASS/32 deselected**. Fallo positivo esperado:
   `client incompatible` por exigir `--max-turns` en help. Patch mínimo del gate.
5. Despachados en paralelo tras fix:
   - `uv run --frozen pytest -q tests/test_bridge_supervisor.py tests/test_bridge_proof.py tests/test_bridge_policy.py tests/test_bridge_runner.py tests/test_bridge_stream.py`
     -> **exit0,125 PASS**,12.43s.
   - `uv run --frozen ruff check src/efren_bot/bridge/capability.py tests/test_bridge_supervisor.py`
     -> exit0, sin hallazgos.
   - `uv run --frozen ruff format --check src/efren_bot/bridge/capability.py tests/test_bridge_supervisor.py`
     -> exit0,2archivos ya formateados. Sin remediación de estilo.
6. Backend completo, comando de abajo -> **exit1:308 PASS/1 FAIL**,16.89s.
   Caso preexistente `test_hostile_cli_never_succeeds[hookbadjson]` falló durante
   cleanup macOS: `RecoveryRequired: process identity uncertain`, PID60236.
   No se ocultó ni corrigió fuera de alcance; no atribuirlo al gate nuevo.
7. Antes de reintentar se clasificó obligatoria la comprobación de ese fallo:
   `ps -p 60236 -o pid=,ppid=,pgid=,stat=` -> exit1/salida vacía, PID ausente,
   **cero señales**. Luego
   `uv run --frozen pytest -q 'tests/test_bridge_supervisor.py::test_hostile_cli_never_succeeds[hookbadjson]'`
   -> exit0,**1 PASS**,0.17s. Sin cambios de código entre fallos/reintentos.
8. Repetición única de backend completo -> **exit0,309 PASS**,16.71s:
   293 heredados+16 parametrizaciones nuevas. Warning Starlette/httpx heredado
   en ambas suites, sin instalar paquetes. La incertidumbre transitoria de cleanup
   queda registrada; repetir con éxito no es una corrección de procesos.
9. Relectura de delta/documentos y espejo completo ODD/#3836 con readback y cotejo
   UTF-8/FNV, manteniendo hitos1–4,5PARCIAL,6PENDIENTE: **23332 bytes,
   FNV1a2586195785**, igualdad disco/readback; SHA256 disco
   `45e8ae1cc9bbb7be8454447a1aea569493b0d291881e46e6902fb6f5ee05d6e5`.
   Check documental stdlib exit0: conjunto fijo, argv/proof, fallos/reintentos,
   contrato local, fences y milestones preservados. Guardado #3836 sin conflictos
   pendientes; bugfix #3874. `git status --short` final igual al inicial: todos los
   archivos siguen untracked, sin staging/commits/ramas/push.

Comando exacto de los pasos6/8 (dos ejecuciones, fuentes estables, DB separada):

```sh
APP_ENV=local DATABASE_URL='postgresql+psycopg://efren_bot:local_demo_only@127.0.0.1:55433/efren_bot_test' uv run --frozen pytest tests
```

**Sin habilitación ni runtime nuevo:** cero Claude/update/modelos/auth/Slack,
metadata queries de cliente o cambios globales/secretos. No perfil/review/proof
creados. API/containers no reconstruidos: el fix host-only de capacidad queda para
última integración del padre. Pendientes perfil real y revisión, prueba nativa,
primer permalink elegido por usuario, riesgo formal/Git/cierre/métricas intactos.

## Adenda — bloqueo OAuth observado en el probe nativo del padre (#3878)

Fuente única nueva: hallazgo del padre #3878 y su reporte acotado para esta
consolidación documental. No se ejecutó aquí cliente, modelo, auth, Slack,
servicios, Git ni métricas; no se releyeron fuentes ni se creó otro helper.
Esta adenda no reescribe contrato ni las causas desconocidas de intentos antiguos.

### Secuencia y evidencia seleccionada, no streams de autenticación

1. Get normal del padre anterior al probe: **exit1**, stderr público exacto
   `No MCP server named "claude.ai Slack"`. Significa que ese target de
   configuración no fue encontrado; no demuestra que el CLI general carezca de
   Slack ni que la cuenta no tenga conector. Es una observación posterior distinta
   de #3864, cuyos streams se perdieron; no completar retrospectivamente sus logs.
2. Los harness anteriores perdieron el resultado durante cleanup; se conserva
   esa limitación. El probe de grupo `killpg(pgid,0)` había dado **EPERM**; no es
   prueba de extinción. La repetición actual no lo usó para declarar reap.
3. Operación nativa metadata-only autorizada del padre: CLI oficial en modo `-p`,
   `--tools ''`, permisos dontAsk, hook wildcard deny-all con `onFailure:block`
   verificado, `--setting-sources ''`, máximo **1 turno / 30 s**. Son propiedades
   reportadas del ensayo, no argv completo reconstruido ni aprobación productiva.
   Comando conocido literal:

   ```sh
   python3 '/private/var/folders/kh/h4blnjhx4cz49v5cd9lw8yv80000gp/T/opencode/efren-bot-native-metadata-probe.py'
   ```

4. Resultado: **native exit1**, `system.init` observado; servidores Slack
   seleccionados `[]`, tools `[]`. Error público exacto:
   **«Failed to authenticate: OAuth session expired and could not be refreshed»**.
   stdout **3922 bytes**, stderr **0 bytes**. Se conservaron solo estos resultados
   seleccionados: no streams raw de auth ni credenciales.
5. El padre observó **wait/reaped verified=true** para el proceso nativo padre.
   No se certifica todo el child group. Scratch propio
   `efren-bot-native-metadata-probe.py` sigue existiendo en el temporal aprobado;
   settings deny-all temporal eliminado. No se modifica ni ejecuta ese archivo
   durante esta consolidación.
6. Chequeo runtime solo de **presencia**, no valores: `CLAUDE_CODE_OAUTH_TOKEN`,
   `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_API_KEY`, `CLAUDECODE`, `HTTP_PROXY`,
   `HTTPS_PROXY`, `ALL_PROXY`: **todos false**. No se leyeron valores.

### Conclusión limitada y siguiente paso vigente

La operación **actual** acredita sesión OAuth del cliente CLI caducada y no
renovable en ese intento. No acredita fallo del conector Slack ni caducidad de
Web/Desktop, que puede seguir activo. No atribuir esa causa a los intentos viejos
sin logs. No hubo Slack tool calls; el error del cliente es anterior a inferencia
según la referencia documental reportada por el padre, sin certificar contabilidad
ni afirmar gasto cero. La ausencia de tools seleccionadas tampoco aprueba aislamiento.

No se ejecutó reconnect/relogin automático. **Esperar renovación oficial por el
usuario en el cliente**, coordinada por el padre, sin API key alternativa ni
tokens por chat; no repetir ahora requests o diagnósticos de cuentas. Solo después
reanudar metadatos no secretos dentro de la autorización vigente. La sugerencia
anterior de abrir `/mcp` queda como paso eventual tras renovación, no acción actual.
No exigir exportación remota completa ni inferir herramientas del modelo.

Incluso tras iniciar sesión faltan perfil/interfaz real, revisión read-only/host,
prueba nativa de la barrera, primer hilo expresamente elegido e integración final.
Safe read continúa **deshabilitado/fail-closed**. Hitos **1–4 intactos, 5 PARCIAL,
6 PENDIENTE**; riesgo formal/Git/cierre global siguen pendientes. Renovación,
calendario, tests o una prueba de modelo no equivalen a habilitación.

Última evidencia de producto sin repetir: #3874, **309 backend PASS** y Ruff
check/format **2 archivos PASS**. Se conserva arriba el primer **308 PASS/1 FAIL**
de cleanup, PID ausente sin señales, caso aislado **1 PASS** y repetición exitosa
sin fix de procesos. Los 293 PASS históricos no son la última regresión.

### Checks de esta actualización documental

Todos **obligatorios**, clasificados previamente por encargo doc-only y
`AGENTS.md`; ninguno opcional ni check de producto:

1. Lecturas `AGENTS.md`, ODD y este documento completos;
   `mem_get_observation(3836/3878/3874)`. PASS: fuentes limitadas al encargo.
2. Cotejo previo UTF-8 disco/#3836: **23332 bytes, FNV1a2586195785**, SHA256 disco
   `45e8ae1cc9bbb7be8454447a1aea569493b0d291881e46e6902fb6f5ee05d6e5`.
   PASS sin pérdida de LF ni writes previos a igualdad. Baseline de este documento:
   **34376 bytes**, SHA256
   `4a0e6d58e467f37b310f30a8aa8d88ea5385522f82f171382ac6881b3c82bc3c`.
3. Patch solo de ambos documentos; relectura, cotejo del error exacto, límites,
   pendientes, fences y preservación histórica con Python stdlib readonly.
4. Espejo **completo** ODD en proyecto `efren-bot`, topic
   `odd/claude-slack-bridge/tasks`, type `decision`; readback y cotejo con disco.
   Resultado y hashes finales al coordinador, sin hash autorreferente en ODD.

Estos checks no certifican runtime ni cierre global. Fallos y reintentos de
producto permanecen íntegros en sus tramos; cualquier fallo documental se reporta
con su remediación, no se oculta mediante el espejo.

## Adenda — COMPANIONCORRECTNESS TAREA5: binding nativo v2

**Parcial, no ready.** Fuente nueva #3886 del padre tras renovación manual «listo»:
native init confirmó `claude.ai Slack connected` y nombre exacto; tipos generados
oficiales `claude-code-mcp/index.d.ts:3003–3019` requieren `channel_id`/`message_ts`
strings, no URL. Este writer leyó **solo ese extracto**. El endpoint procede de
documentación Slack, no metadata runtime. No se repiten auth/get/list ni se ejecuta
Claude/Slack aquí. Se corrige el supuesto URLargument sin reescribir los intentos previos.

Cambios mínimos: perfil2/selector `slack_thread_v1` cerrado a tool/endpoint oficiales,
mapping textual del permalink padre original (>=16 dígitos, punto antes de últimos6,
sin float/int/normalización), opciones100/concise fijas y admisión local exacta.
V1 conserva dump/fingerprint; supervisor proporciona tool/args exactos por stdin.
`ENABLE_TOOL_SEARCH=false` fijo, documentado en Context7 oficial MCP/env-vars antes
del cambio: carga definiciones, no permite ToolSearch. Warning determinista 1call/100.
El companion de ensayo convierte solo su fixture inerte a v1; receipt sigue ligado
al perfil real/código original, nunca se aprueba desde fakes. Policy/proof validators
no requirieron cambios; sus hashes existentes invalidan pruebas antiguas.
API/DTO/DB/UUID/worker/fixture/frontend/Compose/Makefile y secreto propio intactos.

### Comprobaciones obligatorias, orden conservado

Fuente: encargo COMPANIONCORRECTNESS, criterios ODD y `AGENTS.md`. Todas clasificadas
antes de ejecutarse; ninguna opcional ni nueva invocación nativa:

1. Reglas/ODD/contratos/fuentes vecinas/#3836/#3886 y baseline completo iguales:
   **25984 bytes/FNV1a2479950792**, SHA256 disco
   `f617eaa921fe7e83bc0025cfb86598428d070183793b44aeaab753cf2fcddad6`.
   `.ath/rules.md` ausente; sin crear índices. Git status readonly: mismos untracked.
2. Primera tanda dirigida:
   `uv run --frozen pytest -q tests/test_bridge_thread_binding.py tests/test_bridge_validation.py tests/test_bridge_policy.py tests/test_bridge_supervisor.py tests/test_bridge_proof.py tests/test_bridge_stream.py`
   -> **233 PASS**,13.51s. Ruff inicial sobre5fuentes+5archivos tests: check
   **7 E501**, format **6 archivos** (exit1 ambos); corrección solo por patch.
3. `docker compose --project-name efren-bot --profile test ps test-db` -> exit0,
   healthy55433; no arranque/recreación. Ruff dirigido (`src/efren_bot/bridge` +
   helpers/fake/thread_binding/supervisor/storage) -> checkPASS/format21PASS.
4. Regresión completa con comando de abajo -> **379 PASS/1 FAIL**,18.72s.
   Fallo nuevo de test: mock del digest capturaba función importada y no simulaba
   drift de código; fix **solo del test**, no del validador. Ruff global simultáneo
   checkPASS/format47PASS. Añadidos6casos de omisión/drift/plantilla no aprobada.
5. Caso proof aislado
   `uv run --frozen pytest -q tests/test_bridge_thread_binding.py::test_old_reviewed_proof_cannot_authorize_new_binding`
   -> **1 PASS**,0.10s. Ruff global checkPASS/format47PASS.
6. Segunda regresión -> **385 PASS/1 FAIL**,19.12s: heredado `hooktimeout`,
   `RecoveryRequired: process identity uncertain` en `processes.py:190`, PID88926.
   `ps -p 88926 -o pid=,ppid=,pgid=,stat=,comm=` -> exit1/vacío; cero señales.
   Caso aislado de supervisor `test_hostile_cli_never_succeeds[hooktimeout]`
   con `uv run --frozen pytest -q '<nodeid>'` -> **1 PASS**,2.28s, sin fix.
7. Tercera regresión -> **385 PASS/1 FAIL**,18.84s: heredado `duplicateresult`,
   mismo cleanup/PID89639. Mismo ps para89639 -> exit1/vacío/cero señales;
   mismo comando aislado para `duplicateresult` -> **1 PASS**,0.36s, sin fix.
8. Cuarta y última regresión -> **384 PASS/2 FAIL**,18.57s: heredados `toolerror`
   PID90372 y `duplicateresult` PID90388, mismo cleanup. `ps -p 90372,90388`
   con los mismos campos -> exit1/vacío/cero señales. No más repeticiones para
   forzar verde, no relajar identidad/PID reuse ni cambiar `processes.py` fuera
   del alcance. **Regresión global NO verde, bloqueo entregado al padre.**
9. Validación dirigida final con el comando siguiente -> **191 PASS**,2.78s;
   Ruff global checkPASS/format47PASS. Incluye binding/perfil1/adversariales,
   hook/atomicidad, proof drift, fixture nativo mocked y7smokesv2 sin red.
   Los **4** smokes ASGI/API–runner–supervisor–CLI falso–PostgreSQL (v1/v2 ×
   success/wrongselector) pasan en **cada** regresión; URL/evidence originales,
   warning100/redacción del raw fake y replay sin relanzar preservados.
10. Relectura documental/plantilla/ODD y espejo completo3836 con readback al padre.
    Frontend no modificado ni reejecutado:140PASS histórico, no evidencia nueva.

Comando exacto de las cuatro regresiones (DBguard previo a conexión/migración,
solo `efren_bot_test`, nunca demo):

```sh
DATABASE_URL='postgresql+psycopg://efren_bot:local_demo_only@127.0.0.1:55433/efren_bot_test' uv run --frozen pytest -q tests
```

Comando dirigido final:

```sh
uv run --frozen pytest -q tests/test_bridge_thread_binding.py tests/test_bridge_validation.py tests/test_bridge_policy.py tests/test_bridge_proof.py tests/test_bridge_stream.py tests/test_bridge_supervisor.py::test_native_thread_binding_fake_protocol
uv run --frozen ruff check src tests migrations
uv run --frozen ruff format --check src tests migrations
```

Warning Starlette/httpx heredado en las regresiones, sin instalar paquetes.
La recurrencia coincide con el guard de cleanup ya observado #3874, no una prueba
de su causa raíz ni una corrección. Todos los nuevos casos pasan, pero no se declara
386PASS. No perfil/review/proof real creados, tokens leídos, configglobal, deploy,
Slack, modelos, Git writes ni métricas. Falta hilo padre/workspace del usuario,
revisión personal/unmanaged válida, nativeproof fresco, resolver/aceptar por separado
el bloqueo de regresión y última integración del padre. Hitos1–4 intactos,
5PARCIAL/6PENDIENTE; riesgo formal/Git/cierre global siguen diferidos.

## Adenda — corrección causal del cleanup macOS (2026-10-23)

Encargo delegado acotado, clasificación **feature existente**, sin ODD nuevo ni
reescritura de evidencia previa. Últimos dos fallos de la adenda anterior:
`test_hostile_cli_never_succeeds[toolerror]` y
`test_hostile_cli_never_succeeds[duplicateresult]`. No se atribuyen a EPERM del
harness nativo: la reproducción de producto de este tramo observa **ESRCH**, no EPERM.

### Causa, cambio y frontera conservada

Mapeo previo de más de cuatro archivos: `processes.py`, `supervisor.py`,
`capability.py`, `runner.py`, `tests/test_bridge_supervisor.py` y
`tests/fakes/bridge_cli.py`; guard DB en `tests/conftest.py`, comandos en Makefile.
Se reutilizan identidad kernel, `Popen.wait`, journal y presupuesto monotónico
existentes. Sin CodeGraph/graphify init/index, instalación, exploración HOME,
commandlines de procesos ajenos ni ps de aplicaciones del usuario.

La reproducción con hijos propios muestra la ventana de salida macOS:
`proc_pidinfo` devuelve tamaño **0**, errno **3/ESRCH**; `kill(pid,0)` todavía tiene
éxito, y `Popen.poll()` devuelve `None`. El retry previo exigía que un segundo
`poll()` inmediato ya pudiera recogerlo, algo que no garantiza el kernel. Con 30
hijos, `terminate_owned` falló **29/30** exactamente con `process identity uncertain`;
después `wait(timeout=2)` permitió confirmar ausencia del PID y grupo en los 30.
No hay evidencia de PID/PGID reutilizado en esos hijos; no se afirma retrospectivamente
la observación kernel de los PIDs históricos, que el writer anterior encontró ausentes.

Única fuente modificada: `src/efren_bot/bridge/processes.py`. Ante identidad incierta,
espera **hasta 2 s solo por su propio Popen**, sin señalizar un PID desconocido, y
reinspecciona identidad y grupo. Timeout conserva `RecoveryRequired`; PID reutilizado,
identidad aún desconocida o EPERM siguen bloqueando resultado/recovery/otro runner.
Reap del líder no prueba extinción de descendientes. No se añadió fallback de ps,
reloj de baja precisión, inferencia de ausencia por EPERM ni framework de procesos.
No se redujeron timeouts ni se alteraron señales/grupos de procesos ajenos.

Nuevo `tests/test_bridge_processes.py`: 7 casos cubren retry tras wait con ausencia,
PID reutilizado e incertidumbre persistente; espera acotada/journal íntegro y siguiente
runner bloqueado; killpg(0) EPERM y señal EPERM no ignorados; ocho hijos reales macOS
con identidad/grupo propios, reap y extinción verificados. Se conservan los tests
previos adversariales y multiproceso/timeout/cancelación; ninguno se relaja ni elimina.

### Checks obligatorios y orden exacto

Todos clasificados **antes** de ejecutar; fuentes: encargo de fix/regresión,
`AGENTS.md` y criterios ODD/contrato §7–8. Ningún check opcional. `--no-sync` reutiliza
el entorno uv existente sin instalar dependencias. Los harness Python usan solo
hijos propios y metadata PID/PPID/PGID/UID/estado/inicio; no Claude ni red.

1. Reglas/ODD/#3836/contrato y extracción final de tests: PASS. Baseline disco y
   mirror: **28667 bytes/FNV1a3423407129**, igualdad antes de writes. Lecturas
   iniciales de verificación offset680 y `tests/fake_claude.py` fallaron por
   offset/path inexistentes; remediadas leyendo offset420 y `tests/fakes/bridge_cli.py`.
   No fallo de producto ni escritura en esos intentos.
2. `uv run --frozen --no-sync pytest -vv 'tests/test_bridge_supervisor.py::test_hostile_cli_never_succeeds[toolerror]' 'tests/test_bridge_supervisor.py::test_hostile_cli_never_succeeds[duplicateresult]'`
   → **2 PASS**,0.50s. No se considera fix ni se repite hasta obtener verde.
3. `uv run --frozen --no-sync python -` con `sys.settrace` sobre identidad y
   `pytest.main(['-q','tests/test_bridge_supervisor.py'])` → **55 PASS**,12.25s.
   Diagnóstico de excepción capturó solo el caso sintético existente `exit transition`,
   PID1000001; consulta posterior devolvió None. No mostró fallo OS real ni EPERM.
   El siguiente harness fija el código original para excluir ese mock del diagnóstico.
4. `uv run --frozen --no-sync python -`, experimento acotado de **100** hijos:
   identidad antes de cerrar stdin, inspección durante salida, poll, wait2 y prueba
   de grupo tras reap. Exit0, **18480** checks/**469** incertidumbres, todas
   `(line87,size0,errno3,returncode=None)`; **100 reaped**, todos los grupos ausentes.
   Salida inicial grande truncada automáticamente por la herramienta, no perdida;
   resumen posterior del JSON propio (punto10) confirma contadores. No señales manuales.
5. `uv run --frozen --no-sync python -`, reproducción causal de 30 hijos (programa
   exacto abajo) → exit0 del diagnóstico, **29 fallos de cleanup/30**; 60 excepciones
   de identidad `(87,0,3,None)`, incluyendo las inspecciones disparadoras. Todos los
   hijos recogidos con wait2 en finally y PID/grupo ausentes; cero pendientes.
6. Antes del fix: `uv run --frozen --no-sync pytest -q tests/test_bridge_processes.py -k 'waits_for_own_child or unknown_live_child'`
   → **4 FAIL/3 deselected**,0.09s: ausencia/reused/unknown no llegan al wait/retry,
   y timeout no llama wait. Test determinista rojo, no mock hecho para ocultar el fallo.
7. Patch causal; en paralelo:
   - `uv run --frozen --no-sync pytest -q tests/test_bridge_processes.py tests/test_bridge_supervisor.py tests/test_bridge_runner.py`
     → **77 PASS**,12.69s. Incluye señales/permisos/reuse/unknown, ocho hijos reales
     y fake CLI con timeout/child/cancelación/lease/output; todos recogidos.
   - `uv run --frozen --no-sync ruff check src/efren_bot/bridge/processes.py tests/test_bridge_processes.py`
     → **1 B904 FAIL**, raise dentro de except; remediación por patch:
     `raise exc from None`, sin cambio de condición ni pérdida del error original.
   - `uv run --frozen --no-sync ruff format --check src/efren_bot/bridge/processes.py tests/test_bridge_processes.py`
     → **2 archivos PASS**.
   - `docker compose --project-name efren-bot --profile test ps test-db`
     → exit0, healthy, **127.0.0.1:55433**, sin iniciar/recrear servicios.
8. Tras B904, primera regresión con comando canónico abajo → **393 PASS**,18.78s,
   warning Starlette/httpx heredado (1), sin instalar paquetes. En paralelo:
   `uv run --frozen --no-sync ruff check src tests migrations` → PASS;
   `uv run --frozen --no-sync ruff format --check src tests migrations` → **48 PASS**.
9. Repetición **exacta sin modificaciones** del mismo backend → **393 PASS**,
   18.78s, mismo warning. Son dos suites verdes después de fix causal, no reruns de
   código sin remediar hasta verde. Incluyen los cuatro smokes ASGI/API–runner–
   supervisor–CLI falso–PostgreSQL v1/v2 × éxito/selector inválido. Guard existente
   exige `efren_bot_test` antes de conectar/migrar/TRUNCATE, confirma current_database;
   comando fija loopback55433. **Nunca DB demo55432**.
10. `python3 -` con JSON/Counter del output propio del punto4 → exit0:
    children100/checks18480/identity_errors469/all_reapedtrue, único patrón citado.
    Sin nueva inspección de procesos ni señales. Consolidación documental y mirror
    completo3836/readback son checks obligatorios finales; hashes al coordinador.

Comando exacto de ambas regresiones:

```sh
DATABASE_URL='postgresql+psycopg://efren_bot:local_demo_only@127.0.0.1:55433/efren_bot_test' uv run --frozen --no-sync pytest -q tests
```

Reproducción causal **antes** del fix (punto5; no se reejecuta como requisito para
forzar verde; el nuevo test real conserva la condición de transición):

```sh
uv run --frozen --no-sync python - <<'PY'
import collections, ctypes, json, subprocess, sys, time
from efren_bot.bridge import processes
original_code = processes.process_identity.__code__
rows = []
active = None

def trace(frame, event, arg):
    if frame.f_code is original_code and event == 'exception' and issubclass(arg[0], processes.RecoveryRequired):
        rows.append({'pid': frame.f_locals['pid'], 'line': frame.f_lineno, 'size': frame.f_locals.get('size'), 'errno': ctypes.get_errno(), 'returncode': active.returncode})
    return trace
sys.settrace(trace)
cleanup_failures = []
for iteration in range(30):
    active = subprocess.Popen([sys.executable, '-c', 'import sys;sys.stdin.buffer.read(1)'], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True, env={'PATH':'/usr/bin:/bin'})
    try:
        identity = processes.process_identity(active.pid)
        active.stdin.write(b'x'); active.stdin.close()
        limit = time.monotonic() + 1
        while time.monotonic() < limit:
            try:
                current = processes.process_identity(active.pid)
            except processes.RecoveryRequired:
                break
            if current is None:
                break
        try:
            processes.terminate_owned(active, identity)
        except processes.RecoveryRequired as exc:
            cleanup_failures.append({'pid':active.pid,'error':str(exc),'returncode_at_failure':active.returncode})
    finally:
        active.wait(timeout=2)
        assert processes.process_identity(active.pid) is None
        assert not processes.group_alive(active.pid)
sys.settrace(None)
print(json.dumps({'children':30,'identity_errors':len(rows),'error_kinds':dict(collections.Counter(str((r['line'],r['size'],r['errno'],r['returncode'])) for r in rows)), 'cleanup_failures':cleanup_failures,'sample':rows[:2],'all_reaped_and_groups_extinct':True}))
PY
```

### Estado de entrega, no habilitación real

Solo dos archivos de fuente/tests en el alcance causal; API/DTO/perfil/selector
v2 string channel_id/message_ts/URL original/presupuesto1call/capability y proof
intactos. Código y smokes integrados preparados para una sola regeneración de API
posterior del padre; **no hubo rebuild/deploy aquí**. Los dos backends verdes no
certifican enforcement nativo ni lectura Slack. Cero CLI oficial, modelos, Slack,
auth probes, credenciales/configglobal/Git/métricas. Historial de fallos conservado.

El usuario difirió el primer hilo: **«Lo compartiré después»**; no solicitarlo de
nuevo ni inventar workspace/host/perfil. Auth CLI renovada y native init Slack
connected ya reportados por el padre, cero real reads. Faltan perfil/revisión
read-only y host personal/unmanaged válido, nativeproof fresco y primera lectura
expresamente elegida cuando el usuario la comparta. No faltó una aprobación Git
por un defecto de código: Git/riesgo formal/cierre siguen diferidos por decisión
del usuario. Hitos **1–4 intactos, 5 PARCIAL, 6 PENDIENTE**; puente no live-enabled.

## Adenda final — cierre documental parcial y runtime actual del padre

Fuente: evidencia final explícita del padre (#3886, #3891 y consolidación #3893),
sin nuevas consultas ni ejecución de producto por esta sesión documental. Los
tramos anteriores conservan sus fallos, resultados y pendientes **de entonces**;
no tratar las antiguas instrucciones `/mcp`/renovación/rebuild como acciones actuales.
No hay verified/done global: **1–4 intactos, 5 PARCIAL, 6 PENDIENTE**.

### Clasificación de la evidencia final, antes de sus comprobaciones

- **Obligatorias — metadata y controles/arranque:** autorización expresa del padre,
  criterios ODD y `AGENTS.md`; lectura solo de metadata, sin contenido Slack, y
  despliegue aislado/HTTP de integración. No certifican enforcement nativo por sí solas.
- **Opcionales — documentación pública:** búsqueda web y páginas oficiales para
  endpoint/tipos; no son pruebas runtime ni autorización para instalar otro conector.
- **Obligatorias — esta unidad documental:** encargo doc-only y `AGENTS.md`:
  lecturas, concordancia histórica/estado, referencias/fences, espejo íntegro y
  readback; sin reruns de tests, CLI, servicios, proof ni perfil aprobado.

### Metadatos resueltos: autenticación funcionó, ningún hilo leído

1. El usuario renovó personalmente el CLI y confirmó **«listo»**. El padre repitió:

   ```sh
   python3 '/private/var/folders/kh/h4blnjhx4cz49v5cd9lw8yv80000gp/T/opencode/efren-bot-native-metadata-probe.py'
   ```

   **Native exit0**, init `claude.ai Slack connected`, **18 nombres de herramientas
   Slack**, incluida `mcp__claude_ai_Slack__slack_read_thread`, `errors:[]`;
   stdout **16521 bytes**, stderr **0**. Proceso padre reaped. Solo metadata con
   deny-all, sin lectura de contenido, contraseñas ni provider keys. No se guardan
   streams raw de auth. OAuth caducado #3878 **ya no es bloqueo actual**; tampoco
   se atribuye retrospectivamente a intentos anteriores sin diagnóstico.
2. Intentos UI: siempre **0 prompts / 0 tool calls**; hubo varios deadlines
   acotados antes del menú/selección MCP. `pyte` se usó efímeramente con
   `uv --no-project`, no como dependencia del producto. El manager del CLI mostró
   cuenta/Slack conectado y 18 herramientas, pero formato/cursor del selector no
   permitió extraer definiciones. No demuestra que el CLI sea unsupported.
3. Búsqueda web pública opcional cancelada, sin fallback automático por cuota.
   Después, documentación oficial
   [slack-mcp-server.md](https://docs.slack.dev/ai/slack-mcp-server.md)
   identifica **`https://mcp.slack.com/mcp`**.
   [connect-to-claude.md](https://docs.slack.dev/ai/connect-to-claude.md)
   documenta el endpoint del plugin Claude; no se instaló un nuevo plugin Slack
   ni se abrió otro OAuth Slack. **Endpoint documental, no URL observada en runtime.**
4. Vía autoritativa: un mod oficial **temporal por sesión**, NOOP `session.start`,
   `calls:none`, generó `.claude-plugin/types/claude-code-mcp/index.d.ts` conforme a
   [tipos oficiales del build](https://code.claude.com/docs/en/plugins/mods/create#get-the-types-for-your-build).
   El agente #3884 generó archivos, pero perdió parser/resultado y borró scratch;
   no se presenta aquel intento como extracción exitosa. El padre repitió con helper
   que conserva el resultado antes del cleanup:

   ```sh
   python3 '/private/var/folders/kh/h4blnjhx4cz49v5cd9lw8yv80000gp/T/opencode/efren-bot-generated-types.py'
   ```

   **0 prompts / 0 herramientas Slack**. Archivo de **390230 bytes**, nombre canónico
   en línea3004 y extracto3003–3019 en scratch aprobado
   `efren-official-tool-types-8zkbkwa8/observer/.claude-plugin/types/claude-code-mcp/index.d.ts`.
   Descripción oficial read-only: padre y replies; requeridos `channel_id` y
   `message_ts` **strings** (timestamp decimal), opcionales `limit`1..1000/default100,
   `cursor`, `latest`, `oldest` y `response_format` detailed/concise.
   Proceso CLI padre reaped/exit0. Mod temporal NOOP, no instalación permanente,
   configuración global, permisos nuevos ni secretos; no texto de modelo como autoridad.
5. El padre persistió solo metadata seleccionada en
   `.local/bridge/discovered-metadata.json`, fuera de Git, con procedencia explícita
   no-modelo, perfil **no aprobado** y `slack_content_read:false`.
   `chmod0600` y comprobaciones own/regular/no-symlink **PASS**. Sin tokens de
   suscripción. Ese archivo no es `profile.json`, review ni nativeproof aprobado.

**Lectura de metadata ≠ lectura de mensajes Slack ≠ prueba de política nativa.**
La interfaz ya está resuelta; no solicitar más exportaciones ni metadatos por UI.
Se conserva el contrato local cerrado, no exportación completa upstream obligatoria.

### Integración de código y regresión: historia conservada

- Binding v2 deriva `channel_id`/`message_ts` del permalink padre mediante **strings**,
  sin floats/búsquedas; v1 conserva fingerprint, opciones100/concise fijas, hook con
  igualdad TOTAL y una llamada, warning de contexto parcial. Los **191 PASS dirigidos**
  no ocultaban la regresión global roja por cleanup macOS; se conserva toda su secuencia.
- Fix #3891: única fuente `processes.py` y siete tests nuevos. Repro29/30 y cuatro
  tests rojos antes del fix →77focusedPASS; RuffB904→patch; **393 PASS y segunda
  regresión idéntica 393 PASS sin nuevos edits**, Ruff check/format48PASS. Unknown,
  PID reutilizado y EPERM siguen deny; EPERM nunca significa extinto. Todos los
  hijos propios recogidos, sin pendientes. No Slack/Claude reales en ese fix.
- Frontend no cambió: **140 PASS históricos**, sin rerun; DTO/API intactos.
  El compañero mecánico del padre añadió `.local` y `.openchamber` a `.dockerignore`
  **antes del build**, para excluir secretos propios/artifacts. Dos ignores y el
  archivo de metadata no son nuevo código de aplicación ni motivo para repetir tests.

### Arranque real actual y HTTP, no solo Compose válido

Comando exacto del padre, **exit0 al primer intento**:

```sh
docker compose --project-name efren-bot config --quiet && docker compose --project-name efren-bot up --build --detach --wait --wait-timeout 90
```

Imágenes backend/web reconstruidas y migración/worker/API propios recreados;
migración **exit0**, DB/API **healthy**. Warning UID10001 heredado no fatal. Servicios
propios dejados **arriba con el código último desplegado**. Sin `down -v`, otros
proyectos ni montajes de credenciales Claude/Slack. No confundir este arranque base
con `bridge-up` opt-in, que sigue pendiente de perfil/revisión/nativeproof reales.

El script HTTP stdlib del padre comprobó las siguientes requests; no se inventa
un literal único de script cuyo cuerpo no fue suministrado:

| Request / control | Resultado |
| --- | --- |
| API `:8000/healthz` | 200 |
| API `:8000/readyz` | 200 |
| Vite `:5173/api/bridge/status`, GET con `Sec-Fetch-Site:same-origin` | 200, `enabled:false`, `configuration:disabled` |
| Status vía web con `Origin:https://example.invalid` | 403 |
| `runner/claim` vía web | 403 |
| Overview demo | 1 tarea y 3 actividades preservadas |

Sin jobs creados ni lectura Slack. «Deshabilitado» corresponde a opt-in/política
sin perfil aprobado; **no es un fallo de conexión**. HTTP saludable tampoco
certifica el ejecutor/enforcement nativo ni la primera lectura real.

### Checks documentales y siguiente acción en espera

Lecturas completas de `AGENTS.md`, ODD, evidencia, contrato puente y README;
Engram context/#3836. Baseline disco y espejo: **31055 bytes/FNV1a2220621503**,
SHA256 `24de6f3a50b5ac9df21ced790ed4d3263d190d2b5c6124da139ae0c3fdafd5ef`,
igual antes de writes. Patch limitado a esos cuatro documentos autorizados;
comprobar concordancia de estado, distinción metadata/contenido/ready, preservación
literal de historia/fallos salvo los resúmenes y Next estrechamente actualizados,
referencias y fences. Espejo completo ODD en proyecto `efren-bot`, topic
`odd/claude-slack-bridge/tasks`, readback íntegro e igualdad UTF-8/FNV desde disco
actual; resultados y hashes al coordinador. No introducir hash autorreferente.

El usuario eligió **«Lo compartiré después»**. La siguiente acción es **esperar**
su enlace del mensaje padre/workspace cuando quiera, **sin volver a solicitarlos**.
No consultas reales Slack, proof nativo ni perfil aprobado ahora. Cuando aporte el
alcance: revisar/aprobar perfil workspace read-only y host/modelo personal-unmanaged
(desconocido/Team/managed bloquea), ejecutar nativeproof fresco real y solo después
bridge opt-in/runner y lectura expresamente autorizada. El source/workflow está
preparado y API/web actuales arriba; no queda un rebuild base pendiente.

No pedir tokens, provider API, login ni más metadata UI; tipos/fakes/393PASS no
sustituyen nativeproof. Riesgo formal/Git/cierre/métricas siguen diferidos por decisión
del usuario, no por código. Sin nuevos tests, CLI/modelos/auth/Slack, servicios,
herramientas en otros repos ni cambios source desde esta unidad; historia base-local
intacta. **5 PARCIAL / 6 PENDIENTE**, no habilitación ni cierre global.
