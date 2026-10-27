# Puente local de lectura manual — contrato v1

Contrato normativo de `claude-slack-bridge`, separado de la base descrita en
`contract.md` y `architecture.md`. Es una ampliación autorizada, no una modificación
retroactiva de sus fixtures/evidencia. **Diseño acordado; aún no implementado.**

Nota de lectura histórica: ese estado y los futuros de implementación de las
secciones originales corresponden a tarea 1; se conservan, no son el estado
actual. Ver adenda TAREA5 y `claude-bridge-verification.md`: implementación local
parcial, sin perfil ni enforcement real aprobado; §3 precisa el contrato local.

## 1. Alcance y uso del cliente oficial

Un solo operador local pide manualmente un permalink Slack y recibe una propuesta
no validada. Browser -> API/DB local -> runner host -> Claude Code oficial sin
modificar -> conector existente. El worker/outbox/provider `fixture` no participan.
No hay escucha, importación general, búsqueda, paginación global, publicación,
escritura de código, delegados, generación de tareas ni transición a `done`.

El usuario reporta que Slack ya responde en terminal; se acepta sin repetir
`auth`, `login`, `status`, `mcp list`, inspecciones de tokens o pruebas de conexión.
No se ha leído ningún hilo para este contrato. No inferir herramienta/schema del
nombre Slack: un operador revisará el perfil no secreto fuera del navegador.

Documentación oficial consultada el 2026-10-23 mediante Context7:

- [Setup](https://code.claude.com/docs/en/setup): `claude update` es el actualizador
  manual oficial; sigue el canal existente. No reinstalar ni cambiarlo.
- [Hooks](https://code.claude.com/docs/en/hooks): `PreToolUse` wildcard; exec form
  con `args`; `onFailure: "block"` requiere **2.1.295+**. Sin esa opción un fallo,
  timeout o JSON inválido puede dejar continuar una llamada.
- [CLI](https://code.claude.com/docs/en/cli-reference),
  [settings](https://code.claude.com/docs/en/settings-reference),
  [permissions](https://code.claude.com/docs/en/permissions): controles por sesión,
  herramientas vacías, `dontAsk`, allowlist MCP y salida headless. `allowedTools`
  es preaprobación, **no** una frontera de alcance.
- [Legal](https://code.claude.com/docs/en/legal-and-compliance): el usuario final
  puede usar su propia suscripción en el binario oficial sin modificar. No ofrecer
  login Claude.ai propio, intermediar tokens/uso de terceros ni usar OAuth en un
  Agent SDK como sustituto de API keys. Este contrato no certifica cumplimiento
  para comercialización/multiusuario: requeriría revisión y acuerdos aplicables.

Solo proceso del usuario en su host, con autenticación administrada por el cliente
oficial. No SDK de modelos, proxy OAuth, token exportado ni fallback a API. Un error
de suscripción/cuota se presenta como fallo, no se cambia método de facturación.
No se altera el binario ni sus métodos de autenticación; el supervisor únicamente
no suministra credenciales de proveedores alternativos a esta ejecución opt-in.

## 2. Configuración opt-in y frontera Docker/host

Nombres reservados para implementación (no son comandos ya disponibles):

| Nombre | Contrato |
| --- | --- |
| `CLAUDE_BRIDGE_ENABLED` | Boolean, default `false`; solo API/runner, requiere `APP_ENV=local`. |
| `CLAUDE_BRIDGE_TOKEN_FILE` | API: `/run/efren-bot-bridge/token`; host: ruta absoluta a `.local/bridge/token`. |
| `CLAUDE_BRIDGE_PROFILE_FILE` | API: `/run/efren-bot-bridge/profile.json`; host: ruta absoluta a `.local/bridge/profile.json`. |
| `CLAUDE_BRIDGE_API_URL` | Solo runner, exacto `http://127.0.0.1:8000`, sin redirects ni proxy ambiental. |
| `make bridge-init` | Crear directorio `0700` y token aleatorio 32 bytes como 64 hex ASCII + LF, archivo `0600`, creación exclusiva, nunca sobrescribir ni imprimir. No crear/aprobar perfil automáticamente. |
| `make bridge-up` | `docker compose --project-name efren-bot -f compose.yaml -f compose.claude.yaml up --build --detach --wait --wait-timeout 90`. |
| `make bridge-runner` | `uv run --frozen python -m efren_bot.bridge.runner` en host; un solo runner. |

`compose.claude.yaml` añadirá **solo a API** enable y mounts readonly del token y
perfil propios; `create_host_path: false`, error si faltan. No propagar esos mounts
a worker/migrate/web/DB. Perfil no secreto idéntico en API/host. Compose default
sin override funciona sin esos archivos, con puente deshabilitado. Publicaciones
siguen loopback; proyecto `efren-bot`. No iniciar servicios durante este contrato.
No leer `.env` para sortear permisos ni introducir credenciales allí. Config bridge
se obtiene de variables explícitas y archivos propios, nunca del navegador.

Token y perfil: archivos regulares propiedad del operador, sin symlinks; comprobar
permisos host antes de leer. El mount Docker conserva protección readonly; la API
no exige que el UID del archivo bind sea igual a su UID de contenedor. Rotación
manual fuera de runs activos; el init no es rotación. Token nunca va a argv, URL,
DB, logs, UI persistida ni entorno/entrada del hijo Claude. Para UI el operador
introduce **solo este secreto del puente** en un campo efímero; memoria de pestaña,
sin localStorage/sessionStorage/cookie, limpiar al salir/recargar. No pedir tokens
Claude/Slack. Es un operador de confianza, no aislamiento multiusuario ni frente
a malware del mismo usuario. Datos de resultados sí quedan en DB local.

## 3. Perfil local confiable y fingerprint

`docs/examples/claude-slack-profile.example.json` es JSON válido pero **no
configurado**: `approved:false`, hosts vacíos y nulls intencionales. Copiarlo no
habilita el puente. Todos los objetos del perfil rechazan claves adicionales.

Para admitirlo se exige:

- `schema_version=1` (selector URL original) o `2` (binding nativo de la adenda final);
  `profile_id` string ASCII `[a-z0-9-]{1,64}`;
  `profile_version` entero positivo; `approved=true` tras revisión del operador.
- `cli.path` absoluto a binario oficial; `minimum_version="2.1.295"`;
  `verified_version` versión exacta >= mínimo y `verified_sha256` 64 hex minúsculas
  del binario resuelto. Revalidar versión/hash antes de cada run. Actualización
  posterior invalida aprobación hasta revisar el perfil/capacidades nuevamente.
- `model` string local no vacío <=128, sin whitespace de control; el operador
  elige el modelo disponible en su suscripción. Browser/modelo no lo cambian.
- `allowed_slack_hosts`: 1..8 hosts exactos en minúsculas con formato
  `<workspace>.slack.com`, sin comodines, puerto, esquema ni credenciales.
- `connector.kind="claude_ai"`: reutiliza un conector ya conectado en el cliente
  oficial. `server_url` HTTPS exacta, sin userinfo/query/fragmento ni comodines;
  corresponde al conector aprobado, no al permalink del hilo. No incluir headers,
  tokens, comandos de servidores, rutas a credenciales ni copiarlos de HOME.
- `tool_name`: nombre MCP completo exacto revisado, no patrón, <=256 caracteres;
  `url_argument`: nombre exacto de propiedad de primer nivel, <=128 caracteres.
  `fixed_arguments`: objeto JSON cerrado, sin esa propiedad; `input_schema`: schema
  del **contrato local cerrado de admisión construido a partir de la interfaz
  oficial revisada, no exportación completa del schema remoto**; admite exactamente
  esas propiedades más URL.
   El perfil **v1** soporta una herramienta read-only que recibe permalink exacto.
   La adenda final v2 añade únicamente derivación textual local a los dos IDs oficiales;
   búsqueda, segunda llamada, cursor o cualquier otro selector siguen sin soporte.
- `limits` solo los seis campos del ejemplo. `run_timeout_seconds` entero 10..120,
  `max_turns` 1..4, `max_tool_calls=1`, `max_stdout_bytes` 1024..1048576,
  `max_stderr_bytes` 1024..65536, `max_result_bytes` 1024..32768. Son techos,
  el supervisor puede aplicar límites menores, nunca ampliarlos por input externo.

La evidencia de revisión debe garantizar que esa llamada no publica y su alcance
es el hilo, no que su nombre parezca de lectura. Si no existe esa interfaz en el
conector actual, registrar bloqueo sin reconfigurar ni probar auth. Perfil no
generado/aprobado por el modelo. Schema JSON revisado localmente, sin `$ref` remoto,
resolución de URLs ni ejecución de código. La igualdad de args es la barrera real.

Esta precisión no cambia el schema soportado ni sus restricciones funcionales.
Según la revisión `ses_e965ff1cfffeqVVZBkFzT9Md1l` (`profile.py:259–263` y
`policy.py:122–139`), el schema se valida **localmente**; no se obtiene ni compara
con un schema upstream. El control exige igualdad total del nombre de herramienta
y de argumentos JSON canónicos, URL original del usuario inmutable y presupuesto
atómico de un intento. Exigir además una exportación completa remota no añade
control de alcance y puede rechazar interfaces legítimas con propiedades opcionales.
No inventar nombres/semántica desde texto del modelo ni sustituir `server_url`
por `serverName`. Siguen obligatorios fingerprint, `approved`, revisión read-only,
revisión host, prueba nativa, deny-all, una llamada y controles HTTP/Host/auth.
Un perfil o un ensayo con CLI falso no demuestran enforcement real.

### Histórico: interfaz oficial pendiente, sin nueva lectura Slack

La autorización de metadatos #3860 y los intentos #3862/#3864 no produjeron una
interfaz ni endpoint acreditados; detalle y fallos en
`claude-bridge-verification.md` (adenda de metadatos). No se exige una exportación
JSON completa del schema remoto. El paso propuesto **entonces**, ya superado por
la evidencia oficial #3886, era desde **su sesión habitual de Claude Code**: abrir `/mcp`, seleccionar
Slack y consultar lista/detalle de herramientas (`View tools`, **si aparece**).
La documentación oficial respalda el menú, pero no se observó en esta instalación:
no se garantiza esa UI exacta. Si no muestra los datos necesarios, mantener pending.

Se proponía compartir **solo** nombre canónico de una herramienta de lectura, descripción y
parámetros oficiales que acrediten lectura de hilo por permalink exacto en una
llamada, y URL del servidor sin credenciales si es visible. No capturas crudas,
tokens, headers, emails ni credenciales; detenerse ante login o permisos nuevos.
Esto acredita interfaz URL→hilo y endpoint, no salud de conexión. La URL exacta del
servidor sigue siendo obligatoria para aprobar el perfil, aunque no sea visible.
Ese pendiente de metadatos ya está resuelto por tipos oficiales generados y docs
públicos, no por texto de modelo ni contenido Slack; ver adenda v2 y evidencia final.
No volver a pedir exportación, metadatos por UI, login ni tokens. CLI renovada y
Slack connected ya observados no equivalen a prueba nativa de política. El usuario
eligió «Lo compartiré después»: esperar su enlace/workspace sin volver a pedirlos;
no aprobar perfil ni ejecutar prueba/lectura real ahora. Cuando lo aporte, quedan
revisión/aprobación real del perfil/host y nativeproof fresco antes del opt-in/runner.
API/web con código actual ya desplegados; deshabilitado es política, no fallo de conexión.

`profile_fingerprint = "sha256:" + SHA256(canonical_profile_utf8).hexdigest()`.
Canonicalización: JSON de perfil completo validado, `sort_keys=True`,
`separators=(",", ":")`, `ensure_ascii=False`, sin LF final. Sin floats/NaN,
solo valores JSON estándar; sin normalización semántica ni eliminar campos.
API y runner calculan independientemente. Cualquier drift bloquea claim/complete;
un run conserva snapshot inmutable de ID, versión, fingerprint y URL original.
API y runner releen/verifican el perfil antes de admisión y complete, no confían
solo en un hash enviado por el peer. No cambiar perfil durante runs activos.

## 4. Seguridad HTTP específica del puente

Controles **antes de persistir o devolver datos reales**, solo rutas
`/api/bridge/*` (no romper health/demo/proxy existente):

- Hosts externos admitidos exactos: `127.0.0.1:5173`, `localhost:5173`,
  `127.0.0.1:8000`, `localhost:8000`. Rechazar Host ajeno/duplicado, puertos u
  otros nombres/IP; no confiar en `Forwarded`/`X-Forwarded-*` del cliente.
  Vite verifica el Host original y preserva Host/Origin al proxy bridge; si necesita
  reescribir Host interno `api:8000`, implementar ruta proxy específica que conserve
  esta validación. No añadir `api` a hosts públicos confiando en headers falsificables.
- Browser exige `Origin` exacto `http://127.0.0.1:5173` o
  `http://localhost:5173` para **GET y POST**, sin `null`. Fetch GET del cliente
  debe enviarlo: si el navegador no lo incluye en same-origin GET, permitir ese GET
   solo con `Sec-Fetch-Site:same-origin`, Host de web admitido y token válido,
   salvo `GET /api/bridge/status`, público y no sensible también en ese fallback.
   Sin Origin, el Host API `:8000` o la ausencia de `Sec-Fetch-Site:same-origin`
   no admiten status público. Rechazar Origin presente incorrecto siempre.
   Sin CORS, wildcard ni preflight
  habilitado para sitios ajenos. `Sec-Fetch-Site:cross-site` se rechaza.
- Todo endpoint salvo `GET /api/bridge/status` requiere
  `Authorization: Bearer <token propio>`; status solo información no sensible y
  también valida Host/Origin. Comparación de token de longitud/formato fijo mediante
  `hmac.compare_digest`, errores genéricos; no registrar headers/cuerpos.
- Runner usa rutas `/api/bridge/runner/*`, Host `127.0.0.1:8000`, sin Origin;
  rechazar cualquier Origin en ellas. Auth obligatoria. No proxy web para esas rutas.
- POST exige `Content-Type: application/json` (charset UTF-8 opcional), JSON estricto,
  objeto, extras prohibidos, sin duplicate keys/NaN. Máximo cuerpo 64 KiB; input
  de creación 4 KiB. Nada de formularios, query token ni ambient cookie auth.
- `Cache-Control:no-store` en respuestas bridge, sin cuerpos en access/error logs.
  Rechazos: Host/Origin 403, auth 401, media type 415, tamaño 413,
  validación 422. Nunca eco de secretos, raw errores CLI o payload inválido.

## 5. Identidad, estados y ciclo de vida

Entidad separada `BridgeRun` / tabla `bridge_runs`, UUID4 nativo, JSON UUID string.
No crear eventos/mensajes/tareas fixture ni reutilizar sus IDs. Campos persistidos:

```text
id, idempotency_key, requested_slack_permalink,
profile_id, profile_version, profile_fingerprint,
status, cancel_requested, created_at, started_at, finished_at, deadline_at,
runner_id, lease_token, lease_expires_at, result, error_code
```

Timestamps aware UTC; tiempos del servidor, no reloj del runner. `deadline_at` se
fija al crear (`created_at + run_timeout_seconds`), incluye espera en cola. URL y
snapshot inmutables. Idempotency key UUID string enviada por UI, unique, no secreto.
Lease token UUID4 aleatorio nuevo por claim (fencing), **jamás** en DTO browser.

```text
queued -> running -> succeeded | failed | cancelled
queued -> cancelled | failed
running + cancel_requested -> cancelled (tras terminar grupo o expirar lease)
```

- Una clave nueva crea `queued`. Replay misma clave/URL y perfil vigente devuelve
  mismo run, incluso terminal, sin relanzarlo. Misma clave con URL o snapshot de
  perfil distinto ->409 `idempotency_conflict`. No recortar/canonicalizar URL.
- URL: string HTTPS <=2048, Host exacto del perfil, path
  `/archives/<channel>/p<digits>` (canal ASCII alfanumérico, timestamp opaco), sin
  userinfo, puerto explícito, query, fragmento, escapes o whitespace. No seguir
  redirects, buscar raíz ni extraer IDs para ampliar scope. Si no admite ese formato,
  422; nunca visitar la URL desde API. Hilo seleccionado explícitamente por usuario.
- Claim en transacción corta, row lock y serialización global bridge (advisory lock
  o equivalente): máximo **un run running** y un runner host mediante lock de archivo.
  Elegir queued más antiguo `created_at,id`. Lease 15 s, heartbeat cada 5 s;
  no conservar transacción durante CLI/red/esperas. Capacidad/fingerprint deben casar.
- Expiración lease running -> `failed/interrupted`; nunca requeue/auto-retry de
  lectura externa. Deadline -> `failed/timeout`. Reconciliar en claim/GET/cancel/
  heartbeat/complete con locks, no depender de un scheduler nuevo. Runner mata su
  grupo al perder contacto/lease o alcanzar plazo local, aunque API esté caída.
  Fencing protege DB, no detiene red: no hacer otro claim hasta confirmar proceso
  previo terminado; caída runner requiere supervisor/grupo anterior extinguido.
  El supervisor conserva journal propio mínimo de PID/PGID e identidad de arranque
  antes de liberar el lock host. Al reiniciar, confirmar reap/extinción sin riesgo
  de PID reutilizado; si no puede demostrarlo, bloquear y exigir recuperación
  manual, no iniciar automáticamente el siguiente queued tras expirar la lease.
- Cancel queued termina inmediatamente. Cancel running pone `cancel_requested=true`;
  el runner termina grupo y completa cancelled. Si no responde, lease expira y la
  API terminaliza cancelled con error null. Cancel/complete se serializan: cancel
  observado antes de completar impide succeeded. Cancel de terminal es no-op.
- Complete solo runner/lease correctos, running, lease/deadline vigentes. Payload
  inválido no cambia estado; lease anterior ->409 `lease_lost`. Terminal no se
  sobrescribe ni siquiera por complete repetido. Reintentar una lectura exige
  acción manual, nueva key y nuevo run; advertir que pudo haber lectura previa.

## 6. DTO y endpoints exactos (API v1)

Todos los objetos rechazan extras; respuestas 200 salvo donde se indica. Fechas UTC
ISO8601, nulls explícitos, DTO no expone token, lease, stdout, stderr ni pensamiento.

```text
BridgeRunView = {
  id: UUID, requested_slack_permalink: string,
  profile_id: string, profile_version: int, profile_fingerprint: string,
  status: "queued"|"running"|"succeeded"|"failed"|"cancelled",
  cancel_requested: bool,
  created_at: UTC, started_at: UTC|null, finished_at: UTC|null, deadline_at: UTC,
  result: BridgeResult|null, error_code: BridgeErrorCode|null
}
BridgeResult = {
  summary: string[1..4000],
  proposed_actions: string[1..1000][0..12],
  missing_context: string[1..1000][0..12],
  evidence_refs: string[1..2048][0..12],
  warnings: string[1..1000][0..12]
}
BridgeError = {error: {code: string, message: string}}
```

No strings blancos ni NUL/control salvo LF/tab en texto. `evidence_refs` son URLs
**idénticas** a `requested_slack_permalink`, sin refs inventadas ni subrecursos;
array deduplicado (máximo efectivo 1). Salida completa <= `max_result_bytes` UTF-8.
Para succeeded exigir una lectura admitida y finalizada sin error por la herramienta
aprobada, sin violación de política, JSON final válido y evidencia del permalink.
No lograr esto ->failed, no propuesta ficticia. JSON válido no prueba causa raíz,
verdad de la propuesta ni lectura completa (puede faltar contexto en una sola llamada).
UI muestra siempre «Propuesta no validada; revisar fuente y contexto»; no HTML/Markdown
activo ni ejecución de acciones/enlaces automática. Advertencias deterministas de
contexto parcial se añaden sin eliminar las del modelo, respetando límites.

| Método/ruta | Input y respuesta |
| --- | --- |
| `GET /api/bridge/status` | `{mode:"manual_claude_slack", enabled:bool, configuration:"disabled"\|"pending"\|"ready", reason:string\|null}`. Sin perfil/hashes/URLs/runner IDs. Ready exige enable, perfil válido y runner compatible visto <=15 s, no solo configuración presente. |
| `POST /api/bridge/runs` | `{idempotency_key:UUID, requested_slack_permalink:string}` ->202 nuevo /200 replay, `{run:BridgeRunView}`. No campos de modelo, perfil, prompt, herramientas, argv, endpoint ni owner. |
| `GET /api/bridge/runs/{run_id}` | `{run:BridgeRunView}`; no lista/historial global en este corte. |
| `POST /api/bridge/runs/{run_id}/cancel` | `{}` -> `{run:BridgeRunView}`. |
| `POST /api/bridge/runner/claim` | `{runner_id:UUID, profile_fingerprint:string, cli_version:string, cli_sha256:string, policy_verified:true}` -> `{claim:BridgeClaim\|null}`; también actualiza presencia compatible sin trabajo. |
| `POST /api/bridge/runner/runs/{run_id}/heartbeat` | `{runner_id:UUID, lease_token:UUID, profile_fingerprint:string}` -> `{cancel_requested:bool, lease_expires_at:UTC, deadline_at:UTC}`. |
| `POST /api/bridge/runner/runs/{run_id}/complete` | `{runner_id:UUID, lease_token:UUID, profile_fingerprint:string, outcome:"succeeded"\|"failed"\|"cancelled", result:BridgeResult\|null, error_code:BridgeErrorCode\|null}` -> `{run:BridgeRunView}`. |

```text
BridgeClaim = {
  run: BridgeRunView, lease_token: UUID, lease_expires_at: UTC
}
BridgeErrorCode = "interrupted"|"timeout"|"cli_failed"|"output_limit"|
  "invalid_result"|"policy_denied"|"capability_unavailable"|"profile_mismatch"
```

Succeeded: result obligatorio y error null; failed: result null y error obligatorio;
cancelled: ambos null. El runner no envía mensajes de error libres. `policy_verified`
es declaración del runner autenticado después de pruebas locales, no input browser
ni prueba criptográfica. No confundir presencia con validación de cuenta Slack.
Claim incompatible ->409 `profile_mismatch`/`capability_unavailable`, no claim.
Perfil/API deshabilitado o sin configurar ->503 `bridge_disabled`/
`bridge_not_configured`; creación sin runner listo ->503 `runner_unavailable`.
Lectura/cancel de runs previos siguen autenticadas si token disponible aunque no
haya perfil listo. DB fallida ->503 `database_unavailable`; inexistente ->404
`run_not_found`; UUID inválido ->422. Si disabled sin token, solo status funciona.
Otros errores de protocolo 409: `lease_lost`, `run_terminal`,
`idempotency_conflict`. Nunca aceptar succeeded como simple reflejo de stdout.
`status.reason` es null solo cuando ready; valores cerrados restantes:
`disabled`, `token_unavailable`, `profile_missing`, `profile_unapproved`,
`profile_invalid`, `profile_mismatch`, `capability_unavailable`,
`runner_unavailable`. Perfil ausente/no aprobado/inválido deja configuración pending
sin romper la demo; un valor de entorno mal tipado sí es error de arranque.

## 7. Supervisor host y barrera de herramientas

Runner sin servidor entrante: solo polling HTTP loopback autenticado. Un proceso,
un run, un grupo de procesos nuevo por run. URL/ID/deadline/perfil del claim se
validan otra vez; comparar fingerprint del archivo local antes de lanzar y completar.
Snapshot inmutable readonly por run y contador de presupuesto separado, ambos en
directorio temporal propio `0700` bajo `.local/bridge/runs/`, archivos `0600`.
Solo supervisor/hook escriben estado operativo; modelo sin scratch/filesystem tools.

Argv fijo sin shell, ejecutable absoluto comprobado. Base reservada:

```text
claude -p --restricted --setting-sources "" --settings <per-run-settings.json>
  --tools "" --permission-mode dontAsk --permission-prompts none
  --disable-slash-commands --no-chrome --no-session-persistence
  --output-format stream-json --verbose --include-hook-events
  --model <trusted-profile-model> --system-prompt <fixed-reviewed-system-prompt>
```

Prompt de usuario fijo con permalink como dato (stdin, no shell/argv generado por
modelo). Todo contenido Slack es no confiable, no instrucciones. No resume,
continue, plugin, IDE, cloud, remote-control, fallback-model ni dangerous flags.
**No `--bare` ni `--safe-mode`**: desactivan hooks; bare además excluye OAuth.
No `--allowedTools` en esta base: el único allow lo emite el hook tras validar;
la allowlist exacta vive en el perfil/hook, no en un permiso global preaprobado.

Settings por run: `permissions.allow=[]`, modo dontAsk, hook wildcard y
`allowedMcpServers:[{serverUrl:<exact-profile-server-url>}]`, sin comodines.
Conector existente Claude.ai: **no** `--strict-mcp-config` ni desactivar conectores
Claude.ai, porque excluirían precisamente la conexión que se reutiliza; no generar
servidor alternativo ni copiar OAuth a `--mcp-config`. El allowlist MCP oficial
incluye conectores Claude.ai, pero tiene excepciones managed/builtin. La capacidad
de aislar ese único conector y mantener el hook efectivo debe verificarse antes de
habilitar; si managed policy/plugins/mods pueden saltar la barrera o añadir MCP,
bloquear `capability_unavailable`, no modificar su configuración para forzarlo.

Forma del control obligatorio (paths sustituidos solo por supervisor):

```json
{"hooks":{"PreToolUse":[{"matcher":"*","hooks":[{
  "type":"command","command":"<absolute-verified-python>",
  "args":["-m","efren_bot.bridge.policy","<absolute-run-policy.json>"],
  "timeout":2,"onFailure":"block"
}]}]}}
```

Hook ejecutado directamente, sin shell ni argumentos derivados de entrada model.
stdin JSON limitado <=64 KiB, evento `PreToolUse`, `tool_name` igualdad exacta,
`tool_input` objeto con exactamente los argumentos de `Profile.arguments(URL)`:
v1 `fixed_arguments` + `{url_argument:URL}`, v2 los cuatro campos de la adenda,
tipos/valores idénticos (no confundir bool/int), sin extras/duplicate keys/ref remoto.
URL comparada byte por byte contra snapshot del claim, no contra prompt. Exigir
run/deadline/perfil vigentes y presupuesto disponible; consumir presupuesto con
lock atómico **antes** de allow: un solo intento read por run, sin retry del modelo,
incluso si la herramienta falla. Todos los otros nombres/args, subagentes, búsqueda,
shell, archivos y segunda llamada reciben deny. Un denial marca run como inválido;
no aceptar resultado posterior. Salida allow/deny explícita
`hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow"|"deny"}`;
errores o inputs desconocidos ->exit2, sin texto sensible. Nunca salir 0 sin decisión.
`onFailure:block` protege crash, ejecutable ausente, timeout y JSON inválido.

Entorno del hijo por allowlist explícita: HOME del propio usuario solo en host para
el cliente oficial, PATH mínimo, locale/TMPDIR propio y variables internas puente
estrictamente necesarias sin secreto HTTP. No heredar todo `os.environ`, API keys,
`ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`, endpoints base alternativos,
apiKeyHelper, switches Bedrock/Vertex/Foundry, proxies ni configuración que omita
hooks/permissions. No inspeccionar archivos de credenciales. Aislar settings de
user/project/local mediante flags; managed no se sobreescribe ni se elude. Si no
puede garantizar suscripción oficial sin proveedor/API heredada, no ejecutar.

Leer stdout/stderr concurrentemente con techos del perfil, sin acumular ilimitado,
sin mostrar/persistir streams, prompts, mensajes Slack crudos ni CoT. Stream-json
se procesa solo para contar turnos (assistant message IDs distintos), correlacionar
la única lectura/hook y extraer evento final `result` exitoso; ignorar thinking.
Máximo de turnos excedido, salida no parseable/incompleta/duplicada, CLI error o
tool-result fallido ->failed. Campo final `result` debe ser un string JSON de
`BridgeResult` estricto (no fences/HTML ni objetos adicionales), validado otra vez
por API. No usar un StructuredOutput tool desconocido como excepción al hook.

Deadline monotónico local no mayor al del servidor; renovar lease cada 5 s. Ante
cancelación, timeout, pérdida de lease/contacto, política o exceso de salida:
SIGTERM al grupo, esperar <=2 s, SIGKILL si persiste, reap siempre antes de completar
o tomar otro run. No matar PIDs ajenos. Excluir stdin secreto/archivos de política
de toda salida. Logs propios: run ID, estado, error code y tiempos solamente.
Eliminar solo temporales propios tras reap (no árboles amplios). DB guarda resumen
y propuesta validados, no fuente completa. Retención/borrado automático configurable
fuera de este corte; advertir persistencia local, sin prometer eliminación inmediata.

## 8. Capacidad, pruebas y límites de evidencia

Capacidad instalada observada: actualización oficial `2.1.169 -> 2.1.309` exit0;
`--version` confirma `2.1.309`, `--help` confirma flags anteriores. Docs actuales
soportan onFailure:block para esa versión. **No se ejecutó un modelo/hook real ni
Slack**: esto no certifica enforcement en runtime ni tool/schema/conector disponible.

Antes de habilitar `policy_verified`, tarea 3 debe comprobar versión/hash/flags,
validar settings y perfil propios estrictamente (print ignora settings inválidos),
probar hook adversarial y supervisor con CLI falso. No usar `allowedTools` como
rescate si el hook no se carga. Verificar configuración efectiva no interferida por
managed/customizaciones por mecanismos oficiales sin inspeccionar credenciales ni
volver a diagnosticar auth. Si no existe evidencia suficiente sin una invocación
adicional que necesite autorización, registrar pendiente y mantener fail-closed;
pruebas con CLI falso **no** certifican el cliente real ni lectura efectiva.

Obligatorias por criterios de `.odd/claude-slack-bridge.md` para integración futura:
idempotencia/concurrencia/fencing/cancel/timeout/rollback en PostgreSQL separado;
Host/Origin/auth/JSON/size y proxy; perfil vacío/drift; tool equivocado/URL distinta/
extras/segundo intento/crash/timeout/invalid-JSON del hook; entorno sin fallback;
output/turns/process-group; UI pending/error/propuesta; smoke con CLI falso y
regresión demo. Clasificar antes cada comprobación y conservar intentos fallidos.
Primera lectura real requiere perfil revisado y un hilo elegido expresamente, no
una prueba de conexión encargada otra vez al usuario. Sigue pendiente.

## 9. Registro ordenado de tarea 1

### Adenda operativa TAREA5: aprobación host, no un booleano de capacidad

La implementación host añade `make bridge-verify-policy`. Requiere primero el
perfil real aprobado y `.local/bridge/policy-review.json`, ambos `0600` en `0700`.
No descubre Slack ni obtiene su schema. El operador aporta esa interfaz revisada;
sin ella informa `profile_missing` y no invoca el cliente. El token existente no
se sobrescribe ni se pasa al cliente.

El companion de revisión v1 contiene exactamente `schema_version:1`,
`profile_fingerprint`, `operator` (texto no secreto),
`account_scope:"personal_subscription"`, `effective_managed_settings:{}` y
`basis` (texto no secreto que describe la revisión efectiva, no auth ni tokens).
Este corte soporta solo macOS sin managed policy. Es una declaración humana
explícita sobre su suscripción/entorno, **no una detección de cuenta**. No aceptar
Team/Enterprise ni una política managed desconocida como vacía. Presencia de
archivos managed, MDM o cache remoto, incluso vacíos/symlinks/inaccesibles, bloquea.
El programa solo hace lstat de rutas de política documentadas, no lee HOME ni
credenciales; eso por sí solo no demuestra que una cuenta sea personal.

Con esa revisión, el comando hace tres ensayos nativos como máximo, dos turnos y
30 segundos cada uno, en cwd propio: lectura toy y baseline positivo de las cuatro
herramientas toy preaprobadas; nombre/URL rechazados;
presupuesto consumido y hook ausente/crash/timeout/JSON inválido. Solo configura un
MCP stdio fixture con `--strict-mcp-config`, sin Slack, shell del modelo ni red del
fixture. Para fallos del hook, exclusivamente en el ensayo, las herramientas toy
se preaprueban: no basta que dontAsk las deniegue por otra causa. Se exigen intentos
observados, ausencia de ejecución y hook events; negativa del modelo, cuota/error,
formato desconocido o ensayo parcial no aprueban. Streams se descartan, guardando
solo contadores/observables propios. Este ensayo **no prueba aislamiento MCP de
producción**. Ese aislamiento depende además de la revisión humana acotada anterior,
flags de producción y rechazo de managed/customizaciones; no se extrapola strict.

Solo tras ensayos completos el operador confirma por terminal el digest exacto
de la evidencia. El comando crea exclusivamente `policy-proof.json` firmado HMAC
con el secreto propio, ligado a perfil, revisión, binario resuelto, versión/hash,
settings y código del control. Caduca a las 24 horas; no existe importación de
pruebas externas ni `accept-risk`/bool/env que lo apruebe. HMAC detecta edición y
mezcla accidental, **no protege frente al propio operador que posee el secreto**.
Cambios/caducidad/falta de revisión/prueba invalidan capacidad. La API no recibe
estos companions ni cambia su DTO; `policy_verified` sigue siendo declaración del
runner confiable. No representa una prueba criptográfica del proveedor.

También se valida la firma Apple estricta con identifier
`com.anthropic.claude-code` y TeamIdentifier Anthropic PBC `Q6L2SF6YDW`, observados
en el binario actualizado oficialmente; un script con JSON/versión falsos no
cumple ese requisito. El intérprete Python y fuentes/settings quedan ligados al
receipt. Settings cierran plugins y desactivan sync Claude.ai de plugins/skills;
no desactivan hooks ni conectores del perfil de producción.

Flujo del operador (no ejecutar pasos pendientes con valores inventados):

1. Aportar `profile.json` revisado según §3, `0600`; no se crea aquí. Para calcular
   su fingerprint sin ejecutar Claude:

   ```sh
   uv run --frozen python - <<'PY'
   from efren_bot.bridge.init import BRIDGE_DIR
   from efren_bot.bridge.profile import load_profile
   print(load_profile(BRIDGE_DIR / "profile.json", host=True).fingerprint)
   PY
   ```
2. Usar `docs/examples/claude-policy-review.example.json` como estructura de la
   revisión **no aprobada**. Completar fuera del browser, sin copiar credenciales;
   fingerprint exacto y base real de revisión. No declarar personal/unmanaged si se
   desconoce: ese caso queda bloqueado, no requiere login ni probar conexión.
3. Con el runner detenido (incluido si esperaba idle), ejecutar
   `make bridge-verify-policy` desde terminal: solo si ambas revisiones son válidas
   se ejecutan los tres ensayos. Rechazo, fallo o cancelación no crea prueba.
4. Solo con receipt válido, y en la integración autorizada, `make bridge-up` y
   `make bridge-runner`. Este último puede arrancar previamente para esperar idle;
   no reclama ni llama al cliente sin configuración/capacidad. No repetir init:
   el secreto existente no se sobrescribe. Renovar prueba caducada exige terminar
   el runner, conservar/retirar manualmente la prueba anterior y repetir revisión;
   el comando no reemplaza pruebas ni elude journals de procesos pendientes.

`make bridge-runner` puede esperar sin perfil/prueba, sin claims ni invocaciones
Claude. `bridge-up` opt-in sigue pendiente de perfil/prueba reales y no se ejecuta
aquí; no confundirlo con el arranque Compose base actual, ya integrado por el padre.
La evidencia histórica de tarea 1 a continuación permanece intacta.

Todas estas comprobaciones son **obligatorias** por la orden de tarea 1/AGENTS;
ninguna prueba runtime de API/DB/UI corresponde a este cambio documental.

1. Leer entero `.odd/claude-slack-bridge.md`; `mem_save(project="efren-bot",
   topic_key="odd/claude-slack-bridge/tasks", type="decision", title="Claude Slack
   bridge tareas", content=<entero>)`; readback `mem_get_observation(3836)` y
   disco mediante `python3 -c` dirigido. Resultado igual: 6333 bytes UTF-8,
   FNV-1a `3137447066`; SHA256 disco
   `cf06eb615c2a1159664fb6d1bb08bc2f5a67bb080f752ffad82f59b774f62867`.
   Extracción inicial del render de memoria excluía LF separador (6332 bytes);
   se corrigió extracción incluyendo LF, sin writes/update previos a igualdad.
2. Lecturas dirigidas `AGENTS.md`, contrato/arquitectura actuales, `.gitignore`,
   `compose.yaml`, `Makefile`; no `.env` ni credenciales. Mapeo padre sin índices;
   no crear índices ni inspeccionar HOME. Skills no autorizan indexación fuera de
   este alcance. Resultado: demo separada y override necesario, no servicios iniciados.
3. Context7 resolve `/websites/code_claude`; query-docs separados sobre updater,
   hooks, headless/settings y legal antes del update. Resultado: updater oficial
   documentado y advertencias de hooks/headless/legal incorporadas arriba.
4. `/Users/efren.herrera/.local/bin/claude update` (timeout120000 ms): exit0,
   `Successfully updated from 2.1.169 to version 2.1.309`. Sin reintento, cambio de
   canal, reinstalador o edición global por este agente.
5. `/Users/efren.herrera/.local/bin/claude --version`: exit0, `2.1.309 (Claude Code)`.
   `/Users/efren.herrera/.local/bin/claude --help`: exit0; flags observados, no modelo.
   Corroboración read-only posterior `https://code.claude.com/docs/en/hooks`
   confirma hook >=2.1.295; consultas adicionales Context7 MCP/permisos fijan
   exclusiones y allowlist. No son comprobaciones de conexión ni credenciales.
   Remediación: ninguna del updater; enforcement real/perfil siguen pendientes.
6. Validación documental/JSON y readback final del espejo: registrar resultado en
   tracking antes de entregar. No ejecutar Git mutante, métricas, test Slack,
   `make check/test`, Docker ni modelo para rellenar evidencia inexistente.

Comando exacto de comprobación documental del punto 6 (fuente: orden de tarea 1,
obligatoria; exit0, PASS inicial y repetición final tras completar documentación,
ambos sin fallos ni remediación):

```sh
python3 -c 'import json; from pathlib import Path; p=Path("docs/examples/claude-slack-profile.example.json"); d=json.loads(p.read_text()); assert d["approved"] is False and d["allowed_slack_hosts"] == [] and d["model"] is None; assert d["connector"]["tool_name"] is None and d["connector"]["input_schema"] is None; assert d["limits"]["max_tool_calls"] == 1; c=Path("docs/claude-bridge.md").read_text(); assert all(x in c for x in ("/api/bridge/status", "/api/bridge/runs", "/api/bridge/runner/claim", "BridgeRunView", "BridgeClaim", "onFailure", "2.1.309")); assert ".local/bridge/" in Path(".gitignore").read_text().splitlines(); assert "## Excepción acotada: claude-slack-bridge" in Path("AGENTS.md").read_text(); assert "docs/claude-bridge.md" in Path("AGENTS.md").read_text(); print("PASS: JSON ejemplo no habilitado, contratos/referencias y exclusión local presentes; no runtime verificado")'
```

Comando exacto de igualdad disco/espejo del punto 1 (fuente: requisito previo de
tarea 1, obligatorio; exit0, 6333 bytes/FNV-1a 3137447066; misma función UTF-8 en
Code Mode sobre readback entero, incluyendo LF anterior a metadatos `Session:`):

```sh
python3 -c 'from pathlib import Path; b=Path(".odd/claude-slack-bridge.md").read_bytes(); h=2166136261
for x in b: h=((h^x)*16777619)&0xffffffff
print({"bytes":len(b),"fnv1a":h})'
```

Readback final aplica idéntico comando al tracking actualizado y la misma función
a `mem_get_observation(3836)`, sin transformar contenido salvo separar metadatos del
render. Resultado final y nuevo hash se conservan en el informe al coordinador;
no incrustarlos dentro del archivo cuyo contenido se compara.

Resultado de readback final: 9171 bytes UTF-8, FNV-1a `1891793047`, disco y memoria
iguales. Corroboración SHA256 obligatoria del mismo espejo: primer helper Code Mode
falló `ReferenceError: Unknown identifier 'DataView'` antes de calcular digest;
sin escrituras ni efecto sobre el espejo. Remediación: helper con arrays/operaciones
enteras, self-check vector `abc` correcto; segundo intento exitoso. SHA256 disco y
readback Engram coinciden:
`463796334a05ae60afb30a7cc2d67af16af260b1785d744ddcb284eff826a069`.
Comando disco exacto (exit0, sin reintento):

```sh
python3 -c 'import hashlib; from pathlib import Path; b=Path(".odd/claude-slack-bridge.md").read_bytes(); print({"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest()})'
```

Estado final de tarea 1: actualización observada y contrato fijado; implementación,
perfil aprobado y runtime permanecen pendientes. No equivale a entrega global.

## Adenda — compatibilidad de flags ocultos (2026-10-23)

El diagnóstico #3872 observó que el help de 2.1.309 omite `--max-turns`.
La [referencia oficial CLI](https://code.claude.com/docs/en/cli-reference),
corroborada por Context7 y su versión markdown pública, aclara que help no lista
todos los flags y documenta `--max-turns` como límite válido en print mode.
No es motivo suficiente para declarar incompatible ese cliente.

El sondeo mantiene versión exacta, mínimo 2.1.295 y digest antes/después; exceptúa
**solo `--max-turns`** del requisito de aparecer en help mediante conjunto fijo en
código. Todos los demás flags requeridos siguen bloqueando si faltan. No hay
excepción inferida de input/perfil ni aceptación de flags arbitrarios. El supervisor
conserva `-p`, `--max-turns` y su valor validado, además del control host de turnos.
Firma, revisión/aprobación del perfil, receipt nativo y hooks fail-closed intactos.

Este fix no resuelve ni explica los exit1 de metadatos, no crea perfil/prueba ni
habilita el puente. Evidencia de tests y fallo/reintento conservados en
`claude-bridge-verification.md`. Perfil real revisado, prueba nativa y primer hilo
siguen pendientes; la integración base posterior ya está desplegada, no habilita
el bridge. Git/riesgo formal/cierre sin cambios.

## Adenda — binding nativo Slack thread v2 (2026-10-23)

El supuesto de que la herramienta real recibe una URL queda corregido por evidencia
autoritativa #3886: tipos generados por el cliente oficial,
`claude-code-mcp/index.d.ts:3003–3019`, describen
`mcp__claude_ai_Slack__slack_read_thread` como read-only del padre y sus replies.
Requiere `channel_id:string` y `message_ts:string` decimal del **padre**. No recibe URL.
La descripción menciona herramientas auxiliares, pero este producto **no las autoriza**.
`https://mcp.slack.com/mcp` procede de la
[documentación oficial Slack](https://docs.slack.dev/ai/slack-mcp-server#transport-protocol),
no de una URL observada en runtime. No se reinstala/configura otro conector.

`docs/examples/claude-slack-thread-profile.example.json` es una plantilla **no aprobada**,
sin workspace/modelo/hash real. Perfil v2 exige `connector.selector="slack_thread_v1"`,
esa herramienta y endpoint exactos, sin `url_argument` ni mapeos de nombres arbitrarios.
La admisión local cerrada exige exactamente `channel_id`, `message_ts`, `limit` y
`response_format`. `fixed_arguments` es exactamente `{"limit":100,"response_format":"concise"}`:
100 coincide con el default oficial (rango remoto 1..1000); concise es opción oficial.
El producto restringe más que la interfaz remota: prohíbe cursor/latest/oldest y extras.
`schema_version=1` conserva serialización y fingerprint originales; no se migra ni
aprueba automáticamente. Versión/selector incompatibles son perfil inválido.

La misma validación compartida de permalink exige host exacto permitido y path ASCII
`/archives/<channel>/p<digits>`, HTTPS minúscula y sin query/fragmento/escapes/userinfo/puerto.
V2 exige al menos 16 dígitos (al menos 10 de segundos + 6 fraccionales); admite segundos
más largos dentro del techo URL2048. El canal sigue string opaco; se inserta un punto
antes de los últimos seis dígitos **sin float/int/redondeo**, conservando ceros iniciales.
Ejemplo sintético `p1234567890123456` → `"1234567890.123456"`.
No se cambia/canonicaliza la URL original persistida ni sus evidence_refs; no se visita.
El operador debe elegir **Copiar enlace del mensaje padre**, no un reply. No se puede
acreditar raíz sin leer; si la llamada rechaza ese selector, falla sin buscar otro hilo.

Supervisor envía por stdin la URL original y `authorized_tool_name`/
`authorized_tool_arguments` completos derivados del snapshot validado, incluyendo opciones
fijas; el modelo no elige selectores. Hook conserva igualdad TOTAL de nombre/args/tipos,
presupuesto atómico de **un** intento y deny de todo lo demás, incluso ToolSearch.
Según [Claude MCP](https://code.claude.com/docs/en/mcp) y env-vars, consultados con
Context7 antes de usarlo, el entorno permitido fija `ENABLE_TOOL_SEARCH=false`: carga
definiciones directamente, sin autorizar herramientas nuevas ni cambiar permisos globales.
`--tools ''`, dontAsk, `onFailure:block`, allowlist serverUrl y todos los gates intactos.

El resultado añade advertencia determinista de una llamada/máximo100 mensajes/contexto
incompleto y enlace padre; no certifica lectura completa ni hace done. No cambia HTTP,
DTO/DB, UUID, fixture, frontend o estados. El ensayo nativo sigue solo con el MCP stdio
inerte v1, y su receipt queda ligado al **perfil original** y a todo el código de control:
estos cambios invalidan proofs anteriores y exigen revisión/prueba nativa nueva. Tests
fake no las sustituyen. Perfil real, host elegido y aprobación no se crean en este tramo.
