# Plan de pruebas de la fábrica (para el agente que la prueba en el entorno conectado)

Lee primero [factory.md](factory.md) (qué es y cómo está hecha). Este documento es el **guion de
prueba**: qué ejecutar, en qué orden, qué debe pasar y qué entregar al final.

La fábrica fue construida y ensayada **solo con datos simulados**. Tu trabajo es la primera vez que
toca algo real. Por eso el plan va por etapas, cada una añade **una** capacidad real y no se pasa a la
siguiente sin evidencia de la anterior.

## Reglas para quien prueba

1. **No arregles el código para que una prueba pase.** Si algo falla, detente, guarda la evidencia y
   repórtalo tal cual. Un fallo honesto vale más que una prueba verde forzada.
2. **Ningún efecto real antes de la etapa 7.** Hasta entonces `FACTORY_GATEWAY=recording` (por defecto).
3. **`merge` y `deploy` no existen.** Si ves una forma de hacerlos, es un defecto: repórtalo.
4. **No copies credenciales al repo, a Docker ni a los logs.** Slack, Notion, GitLab y los agentes usan
   la conexión que ya existe en el host. Los secretos van solo por variables de entorno del host.
5. **Nunca `docker compose down -v`.** No toques contenedores ni volúmenes de otros proyectos.
6. **Clasifica cada comprobación antes de correrla** como obligatoria (la pide este plan) u opcional, y
   conserva los fallos y reintentos. No declares algo verificado porque "no dio error": necesitas la
   evidencia que pide la columna *Evidencia*.
7. **No uses datos de producción para nada que escriba.** Leer tus tareas de Notion y tus mensajes
   marcados de Slack (etapa 4) es lo único real que se lee. Las escrituras van a un proyecto y a una
   página de pruebas.

## Cómo debe funcionar todo (el flujo esperado)

```text
fuente ─> IntakeItem ─> triage ─┬─ admit ────────────────────────────> job en cola
                                ├─ ask_context / inbox ─> persona ──> admit | discard
                                └─ discard
job ─> worker (host) ─> scraft-ops factory run ─> RunRecord
         (worktree aislado, checks del perfil, riesgo del diff, revisión si riesgo ≥ medio)
RunRecord ─> efectos propuestos:
         policy auto  ─> el worker lo ejecuta        (solo riesgo bajo, sin pendientes, perfil lo permite)
         policy human ─> pestaña "Fábrica" ─> aprobar con la huella exacta ─> la API marca `approved`
                                                                          ─> el worker lo ejecuta
```

**Estados** (todos deben poder observarse en la base y en la pestaña Fábrica):

| Objeto | Estados | Reglas que nunca deben romperse |
| --- | --- | --- |
| Item | `received → admitted / needs_context / needs_human / discarded` | Un mismo contenido no crea dos items (huella única). Una versión cambiada de algo ya admitido va a `needs_human`. |
| Job | `queued → running → succeeded / failed / blocked`, y `paused`, `cancelled`, `superseded` | Cada intento usa su propio id (`fj-xxxx-a1`, `-a2`…). Un intento detenido o reclamado no puede sobrescribir el resultado. Máximo 3 intentos. |
| Efecto | `proposed → approved → executing → executed`, y `denied`, `failed`, `uncertain`, `expired`, `superseded` | La API **nunca** ejecuta, solo registra `approved`. La huella debe coincidir. Un `uncertain` no se reintenta solo. |

**Quién hace qué:** la API y la web no tienen git, `glab`, agentes ni credenciales. Todo eso vive en el
worker del host (`make factory-worker`).

## Etapas

Convención: `$SO` = binario de scraft-ops, `$STATE` = directorio de estado de la prueba.

### Etapa 0 · Precondiciones (obligatoria)

| Comprobar | Comando | Debe ser |
| --- | --- | --- |
| Python/uv/Docker/Node/Go/git | `uv --version`, `docker ps`, `node -v`, `go version`, `git --version` | uv 0.11.28, Node 26.x, Go 1.26+, Docker activo |
| Agentes (según el que uses) | `claude --version`, `opencode --version` | instalados y con sesión iniciada |
| GitLab (solo etapa 7) | `glab auth status` | autenticado en el host |
| scraft-ops con sus agentes | en el repo scraft-ops: `go build -o $SO ./cmd/scraft-ops && $SO install --dry-run` y luego `$SO install` | existen `scraft-odd` y `scraft-judge` en el agente que vayas a usar |
| Repos de prueba | un repo frontend **de pruebas** (o una copia) con rama `main` limpia | `git status` limpio |

**Evidencia:** salida de cada comando. **Si falla:** detente; no avances.

### Etapa 1 · Ensayo simulado en la máquina nueva (obligatoria)

```sh
# repo scraft-ops
go build -o $SO ./cmd/scraft-ops && go test ./internal/factory ./internal/cli
# repo efren-bot
make sync && make test-db
make factory-rehearsal SCRAFT_OPS_BIN=$SO
make test
```

**Esperado:** el ensayo corre 4 archivos (85 pruebas al escribir esto) **sin ninguna omitida**:
`test_factory_cross.py` se omite si falta `SCRAFT_OPS_BIN`, y eso cuenta como fallo de esta etapa.
`make test` pasa completo (646 pruebas de Python y 33 de la web al escribir esto; lo que importa es
**cero fallos, cero omitidas en los archivos `test_factory_*`**).

**Evidencia:** las últimas líneas de cada comando. **Si falla:** la fábrica no es portable; reporta antes
de tocar nada real.

### Etapa 2 · Arranque del stack (obligatoria)

1. Copia `docs/examples/factory-projects.example.json` a `.local/factory/projects.json` con **rutas
   absolutas reales** de tus repos de prueba (el archivo está ignorado por git).
2. `make up` (aplica la migración `0011_factory`) y, para que la API conozca los proyectos:
   `docker compose --project-name efren-bot -f compose.yaml -f compose.factory.yaml up --detach --wait`.
3. Comprueba: `curl -s http://127.0.0.1:8000/readyz`, y que la base está en `0011_factory`
   (`docker compose --project-name efren-bot exec db psql -U efren_bot -d efren_bot -c "select version_num from alembic_version"`).
4. Abre http://127.0.0.1:5173, pestaña **Fábrica**.

**Pasa si:** `readyz` responde `ok`, la versión es `0011_factory`, la pestaña muestra "No hay solicitudes
esperando decisión" y 0 trabajos. **Evidencia:** captura de la pestaña y la salida de `psql`.

### Etapa 3 · Webhook de WhatsApp, sin Meta (obligatoria si vas a usar WhatsApp)

Arranca la API con `FACTORY_WHATSAPP_APP_SECRET=s3cret FACTORY_WHATSAPP_VERIFY_TOKEN=verify` en el
entorno del host (el override de compose los pasa). Luego:

```sh
BODY='{"entry":[{"changes":[{"value":{"contacts":[{"wa_id":"521","profile":{"name":"Ana"}}],"messages":[{"id":"wamid.t1","from":"521","timestamp":"1790000000","type":"text","text":{"body":"por favor cambia el botón de la landing a verde"}}]}}]}]}'
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "s3cret" | sed 's/^.* //')
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8000/api/factory/webhooks/whatsapp -d "$BODY"                     # 401
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8000/api/factory/webhooks/whatsapp -H "X-Hub-Signature-256: sha256=$SIG" -d "$BODY"   # 202
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8000/api/factory/webhooks/whatsapp -H "X-Hub-Signature-256: sha256=$SIG" -d "$BODY"   # 202, duplicates=1
curl -s "http://127.0.0.1:8000/api/factory/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=verify&hub.challenge=42"                              # 42
```

**Pasa si:** sin firma 401; con firma 202 y el segundo envío cuenta `duplicates: 1`; el reto devuelve
`42`; con la API **sin** secretos el mismo POST da 503. El mensaje aparece en la base como item
(`admitted` solo si el proyecto se resuelve por palabras; si no, `needs_context`).
**Evidencia:** los códigos HTTP. Conectar el webhook real de Meta necesita un túnel y es opcional.

### Etapa 4 · Solo lectura de fuentes reales: admisión sin ejecutar nada (obligatoria)

Objetivo: ver qué **decidiría** la fábrica con tus pedidos reales, sin que corra ningún trabajo.

```sh
export FACTORY_PROJECTS_FILE=$PWD/.local/factory/projects.json
export FACTORY_NOTION_TOKEN=...        # solo en tu shell
export FACTORY_NOTION_DATABASE_ID=...
make factory-worker FACTORY_PULL=slack,notion FACTORY_ARGS="--once --admission-only"
```

Antes, marca en la bandeja de Slack de Efren Bot al menos 3 mensajes como «requiere atención» (la fábrica
**solo** mira esos) y deja en Notion al menos 5 tareas, unas en estado listo y otras no.

**Pasa si:** el comando imprime `"ran": 0, "effects": 0`; en la pestaña aparecen las solicitudes que
esperan decisión con sus **razones**; ninguna tarea no lista de Notion fue admitida; ningún mensaje de
Slack sin marca fue admitido; no existe ningún job en estado `running`. Repetir el comando no crea items
nuevos (huella).

**Evidencia obligatoria:** una tabla con **al menos 10 pedidos reales** y, por cada uno, la decisión
esperada por el dueño frente a la que tomó la fábrica:

| Fuente | Pedido (resumido) | Esperaba el dueño | Decidió la fábrica | Razón mostrada | ¿Coincide? |
| --- | --- | --- | --- | --- | --- |

Si más de 2 de cada 10 no coinciden, la política (`src/efren_bot/factory/policy.json`) necesita ajuste:
**reporta la tabla, no edites la política por tu cuenta.** Si una fuente está desconectada el comando
imprime `-1` para esa fuente: eso es un fallo de configuración, no un "0 items".

### Etapa 5 · Un agente real, un proyecto frontend, una tarea pequeña (obligatoria)

**5a. Aísla la unidad de ejecución** (sin Efren Bot, para separar problemas de agente de problemas de la planta):

```sh
cat > /tmp/smoke-job.json <<'EOF'
{"schema":"scraft.factory.job/1","job_id":"smoke-001","source":{"kind":"manual","ref":"smoke"},
 "role":"development","profile":"frontend",
 "repo":{"path":"/RUTA/ABSOLUTA/frontend-de-pruebas","base_ref":"main"},
 "brief":"Cambia el texto del botón principal a 'Empezar'",
 "policy":{"allow_worktree":true,"allow_commit":true,"run_review":true,"executor":"claude","timeout_seconds":900}}
EOF
$SO factory run --job /tmp/smoke-job.json --state-dir /tmp/factory-smoke   # usa "opencode" para el otro agente
```

El código de salida es distinto de cero si el run no tuvo éxito, pero **el JSON se imprime igual**.

**Pasa si:** `status: succeeded`; `branch` es `factory/smoke-001`; el worktree de `worktree` tiene un commit
con **solo** el cambio pedido (`git -C <worktree> diff main --stat`); `risk.tier` es `passive`; cada
`checks[]` obligatorio está en `pass`; **tu checkout del repo sigue limpio y en `main`**. Repetir con el
mismo `job_id` debe dar `blocked` (id de un solo uso).

**Limitación conocida que probablemente verás:** un worktree nuevo **no trae `node_modules`** ni nada sin
versionar, así que los checks `typecheck`/`lint`/`test`/`build` del perfil `frontend` pueden fallar por
dependencias ausentes y el run saldrá `failed`. Aún no hay un paso de preparación en el perfil. Para seguir
probando sin editar el código, crea un directorio de perfiles de prueba con el mismo `frontend.json` y un
primer check obligatorio `{"name":"install","command":["npm","ci"],"mandatory":true,"timeout_seconds":600,
"requires_files":["package-lock.json"]}` y pásalo con `--profile-dir` (en la planta,
`FACTORY_PROFILES_DIR`). `node_modules` está en `.gitignore`, por lo que no cuenta como «verificación que
modifica el worktree». **Repórtalo como defecto de diseño** (falta un paso de setup por perfil), no lo
maquilles.

**Qué observar y reportar de forma explícita** (aquí es donde más probable es que algo no cuadre):
- ¿El agente respetó "no git, no publicar" del prompt? (`git -C <worktree> log` solo debe tener el commit de la fábrica.)
- ¿Cargó el agente `scraft-odd`? ¿Se detuvo pidiendo contexto en vez de adivinar? (en `$STATE/runs/smoke-001/execute.log`)
- ¿Funcionaron los flags (`--agent`, `--permission-mode acceptEdits`, `--no-session-persistence` en claude; `--agent`, `--dir` en opencode)? Si alguno es rechazado por tu versión, **eso es el hallazgo**.
- Con un cambio de ≥ 6 archivos o riesgo medio: ¿`review.verdict` salió `APPROVED`/`ESCALATED` parseado? Si el texto no contiene `JUDGMENT: …`, el veredicto queda vacío y el run exige a una persona (correcto, pero anótalo).

**5b. Por la planta:**

```sh
export FACTORY_AGENT_EXECUTOR=claude        # o opencode
export FACTORY_STATE_DIR=/tmp/factory-run
make factory-submit PROJECT=landing TEXT="Cambia el texto del botón principal a 'Empezar'"
make factory-worker FACTORY_PULL=slack FACTORY_ARGS="--once"
```

**Pasa si:** el submit devuelve `decision: admit` y un `job_id`; el worker corre 1 trabajo; el job termina
`succeeded`; en la pestaña el trabajo muestra riesgo bajo, sus checks y su rama; **los efectos que el
perfil marca `human` aparecen en "Acciones por aprobar" con el contenido exacto** y `open_pr` (perfil
frontend, `auto`) queda `executed` **en el registro de la pasarela, sin MR real** porque
`FACTORY_GATEWAY` sigue en `recording`. **Evidencia:** el `RunRecord` en `$FACTORY_STATE_DIR/runs/<id>.json`,
captura de la pestaña, y la fila del job/efectos en la base.

### Etapa 6 · Compuertas y negativas (obligatoria; con agente falso basta)

Con `FACTORY_AGENT_EXECUTOR=fake` y un `mock` no hay modelo de por medio. Verifica **a mano en la pestaña**
lo que las pruebas automáticas ya cubren, para confirmar que la interfaz real lo respeta:

| Caso | Cómo provocarlo | Debe pasar |
| --- | --- | --- |
| Texto sensible | `make factory-submit PROJECT=landing TEXT="Borrar la tabla de pagos de producción"` | `inbox`, **sin job**; aparece en "Por admitir" con la razón |
| Proyecto ambiguo | un pedido que nombre dos proyectos | `ask_context`, pregunta cuál |
| Cambia `package.json` | job cuyo cambio toque `package.json` | riesgo **alto**, "Por qué necesita a una persona", `open_pr` pasa a `human` |
| Falla un check obligatorio | perfil de pruebas con un check que devuelve ≠ 0 | job `failed`, **sin efectos propuestos** |
| Aprobar huella ajena | llamar `factory/effect` con otra huella | 409 `fingerprint_mismatch`, el efecto sigue `proposed` |
| Aprobar dos veces | aprobar, y repetir | segundo intento 409 `effect_not_pending` |
| Detener en vuelo | `stop` mientras corre | job `cancelled`; si el agente termina después, **no** aparecen efectos |
| Reorientar | `redirect` con un texto | el original queda `superseded`; el nuevo trae **ambas citas literales** |
| Aprobación vencida | `FACTORY_EFFECT_TTL_HOURS=1`, esperar o ajustar `expires_at` en la base de pruebas | `expired`, no se ejecuta |
| Sin permiso de worktree | job con `allow_worktree:false` | `blocked`, no se crea rama |

### Etapa 7 · Un efecto real, con aprobación humana (obligatoria, **solo** con proyecto de pruebas)

Hazlo contra un **proyecto sandbox de GitLab** y una **página de prueba** de Notion, nunca producción.

```sh
export FACTORY_GATEWAY=real
# el repo del proyecto debe tener remote `origin` hacia el sandbox y `glab auth status` OK
make factory-submit PROJECT=landing TEXT="Cambia el texto del botón principal a 'Empezar'"
make factory-worker FACTORY_PULL=slack FACTORY_ARGS="--once"      # corre el trabajo
# En la pestaña: aprobar la acción «Abrir merge request» tras revisar el contenido exacto
make factory-worker FACTORY_PULL=slack FACTORY_ARGS="--once"      # el worker ejecuta lo aprobado
```

**Pasa si:** el MR existe en el sandbox con el título y la descripción del contenido aprobado; la rama se
subió; el efecto queda `executed` con `decided_by` = quien aprobó; **repetir el worker no crea un segundo
MR**; nada se fusionó. Variantes obligatorias: (1) `update_notion` sobre la página de prueba cambia su
estado a «In review» solo tras aprobar; (2) desconectar la red durante la ejecución deja el efecto en
`uncertain` (no `failed`, no reintentado) y la pestaña lo muestra.

**`GlabGateway` nunca se ejecutó contra GitLab real antes de esta etapa.** Si `git push` o `glab mr create`
falla por flags, remotos o permisos, es el hallazgo principal: repórtalo con el mensaje exacto.

### Etapa 8 · Los otros perfiles (obligatoria antes de llamar "lista" a la fábrica)

Repite 5a con agente real sobre **un repo de pruebas por perfil**:
- `lambdas`: un cambio de código normal debe poder terminar; uno que toque `**/serverless.yml`,
  `template.yaml`, `**/*.tf` o `iam` debe forzar riesgo alto y una persona; nunca debe intentar desplegar.
- `orchestrator-multirepo`: un cambio en un esquema (`*.avsc`, `*.proto`, `schemas/`, `contracts/`) debe
  forzar a una persona. Recuerda: **un job es de un solo repo**; no hay aún orden entre repos.

**Evidencia:** un `RunRecord` por perfil, el diff, y qué checks se ejecutaron o se omitieron (un check
omitido por falta de archivos queda `skipped` y exige a una persona: confirma que ocurre).

## Qué entregar al terminar

1. **Un informe** (en este repo, `docs/factory-test-report.md`) con, por etapa: pasó / falló / no se hizo,
   la evidencia pedida y las desviaciones. Incluye versiones (`claude --version`, `opencode --version`,
   `glab --version`, commit de efren-bot y de scraft-ops).
2. **La tabla de la etapa 4** completa.
3. **Actualiza la tabla «Qué está verificado y qué no» de [factory.md](factory.md)** moviendo un renglón
   de «sin verificar» a «verificado el AAAA-MM-DD con <evidencia>» **solo** si la evidencia existe. Lo que
   no se probó se queda como estaba.
4. **Lista de defectos** con el comando exacto, el resultado esperado y el obtenido. Sin arreglarlos aquí
   salvo que el dueño lo pida: cada defecto es una tarea aparte.
5. **Qué faltó** para poder llamarla lista (por ejemplo, ordenar jobs entre repos, topes de costo y
   tiempo por corrida, limpieza de worktrees).

## Si algo sale mal

| Síntoma | Causa probable | Qué hacer |
| --- | --- | --- |
| `factory run` dice `unknown profile` | `--profile-dir` apunta a otro lugar o el nombre difiere | `scraft-ops factory profiles` lista los incluidos |
| Job `blocked` al instante | `allow_worktree` falso, base_ref inexistente o id repetido | leer `errors[]` del RunRecord |
| Job `failed` con `execution_unit_error` | binario no encontrado, o JSON inválido en stdout | `FACTORY_SCRAFT_OPS_BIN`; correr el comando a mano |
| Efecto atascado en `executing` | el worker murió a mitad | pasa a `uncertain` solo tras 10 min (`reclaim_stale`); reconcilia a mano, no reintentes |
| Job atascado en `running` | worker caído | vuelve a la cola tras 2 h (máximo 3 intentos) |
| La pestaña dice "decisiones bloqueadas" | la API no responde o el token de sesión cambió | recargar; revisar `readyz` |
| `make factory-rehearsal` omite `cross` | falta `SCRAFT_OPS_BIN` | exportarlo con ruta absoluta |
| El worktree no se puede borrar | quedan en `$STATE/worktrees/<id>` para inspección | `git -C <repo> worktree remove <ruta>` (aún no hay comando de limpieza) |
