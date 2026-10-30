# Fábrica: embudo, perfiles, ejecución y compuertas humanas

Planta de control de una fábrica de desarrollo. Entra cualquier fuente por un embudo con
criterios de admisión; cada solicitud se resuelve a un **proyecto** con un **perfil** (frontend,
lambdas, orquestador multi-repo, los que se agreguen); la ejecución la hace una unidad externa
(`scraft-ops factory run`) y toda salida al mundo pasa por una compuerta humana.

Estado: **implementada y ensayada con datos simulados**; las conexiones reales (Slack vivo, Notion,
GitLab, WhatsApp) están implementadas detrás de interfaces y **apagadas por defecto**. Ver
[qué está verificado y qué no](#qué-está-verificado-y-qué-no).

## Tres ejes independientes

| Eje | Pregunta | Dónde vive |
| --- | --- | --- |
| **Fuente** | ¿De dónde llega el pedido? | Un adaptador por fuente (`factory/intake.py`) |
| **Rol** | ¿Qué trabajo es? (`development`, `review`, `support`, `research`) | Criterios de admisión (`factory/policy.json`) |
| **Perfil de proyecto** | ¿Cómo se trabaja *este* tipo de proyecto? | `factory/profiles/*.json` (misma forma que scraft-ops) |

Lo que cambia entre proyectos vive en el perfil, no en el código de la fábrica. Un orquestador, un
proyecto de lambdas y uno de puro frontend se distinguen por sus checks obligatorios, sus rutas que
fuerzan a una persona y su política por efecto.

## Flujo

```text
Slack (almacenado) ─┐
Notion (planificado) ┼─> IntakeItem ─> triage ─> admit ──────────────> FactoryJob (cola)
WhatsApp (webhook)  ─┘   (huella)     (criterios)  ask_context/inbox ─> persona decide ─┘
                                                   discard
FactoryJob ─> scraft-ops factory run ─> RunRecord ─> efectos propuestos
                (worktree aislado,        │            auto  ─> el worker lo ejecuta
                 checks, riesgo,          │            human ─> bandeja "Fábrica" ─> aprobar/denegar
                 revisión)                └> merge y deploy: nunca existen aquí
```

### 1. Embudo (`intake.py`)

Cada fuente normaliza a un `IntakeItem` (fuente, autor, fecha, contenido intacto). Agregar WhatsApp o
cualquier otra es escribir un adaptador: `fetch(since)` si se consulta, `parse(payload)` si empuja.

| Adaptador | Tipo | Notas |
| --- | --- | --- |
| `SlackCollectionAdapter` | pull | Lee **solo lo ya almacenado** por el recolector y **solo mensajes marcados `attention = required`** por una persona. Una mención no es un encargo. |
| `NotionAdapter` | pull | Páginas de una base de tareas. Nombres de propiedades configurables. Solo estados "listos" (`Ready`, `To do`…). `MockNotionClient` para ensayo; `NotionHttpClient` usa la API oficial con token y base del host. |
| `WhatsAppAdapter` | push | Payload de WhatsApp Cloud API (solo texto). El webhook exige firma. |
| `FixtureAdapter` | pull/push | Datos enlatados para pruebas. No se expone por HTTP. |

### 2. Criterios de admisión (`triage.py`, `policy.json`)

Deterministas, versionados y explicables: **no hay modelo**. Cada decisión guarda sus razones y la
versión de la política.

| Decisión | Cuándo |
| --- | --- |
| `admit` | Es trabajo, el proyecto y el rol están claros y nada exige a una persona antes |
| `ask_context` | Parece trabajo pero falta proyecto, hay ambigüedad entre proyectos o es demasiado corto |
| `inbox` | Una persona decide: palabras sensibles (producción, permisos, borrar, migración…), o cambió una versión ya admitida, o no está claro que sea un pedido |
| `discard` | No es un pedido, duplicado, tarea no lista, o Slack sin marca humana |

Un proyecto se resuelve por pista explícita (propiedad de Notion), por canal de Slack declarado o por
palabras clave **declaradas del proyecto**. Si dos proyectos coinciden, se pregunta; no se adivina.

### 3. Proyectos y perfiles

`projects.json` (explícito, ver `docs/examples/factory-projects.example.json`) dice qué repo, qué perfil
y qué palabras tiene cada proyecto. Los perfiles son los de scraft-ops (`scraft-ops factory profiles`);
`tests/test_factory_cross.py` falla si las copias de este repo se desalinean.

### 4. Ejecución

`ScraftOpsExecutor` llama `scraft-ops factory run --job -` con un `JobSpec` y recibe un `RunRecord`
(contratos en `factory/contracts.py`, espejo del lado Go). Un run fallido es **dato**, no excepción.
Cada intento usa su propio id (`fj-xxxx-a1`, `-a2`…) porque los worktrees son de un solo uso.

La unidad de ejecución nunca toca tu checkout: trabaja en un worktree propio, corre los checks del
perfil, calcula el riesgo del diff real y, si el riesgo es medio o alto, pide una revisión independiente.

#### Ejecutor principal y respaldo autorizado

Frontend prefiere **OpenCode**. Se puede autorizar **Claude como respaldo** en el
registro del proyecto (esto sí permite consumir esa cuenta):

```json
{"name":"landing","profile":"frontend","repo_path":"/ruta/sandbox","executor":"opencode","fallback_executors":["claude"]}
```

Sin `fallback_executors` no hay cambio de cuenta implícito. La selección de principal
sigue override del proceso → proyecto → perfil;los otros perfiles conservan su
configuración explícita. Cada JobSpec guarda la selección al admitirlo:los cambios
de configuración no reescriben jobs en cola ni reanudan los fallidos del piloto.

La unidad prueba cada ejecutor autorizado una sola vez durante el trabajo inicial,
con el mismo presupuesto de tiempo total. Releva solo ante CLI ausente o mensajes
de disponibilidad reconocidos (cuota/autenticación/429/503),sin progreso en el log y
con HEAD/worktree intactos,incluidos archivos ignorados. Errores desconocidos,pruebas
fallidas,timeout,cancelación,log truncado o cambios parciales detienen:sin fallback.
La revisión independiente no se releva automáticamente después del trabajo.

`RunRecord.executor` es el último ejecutor invocado;`execution_attempts` conserva
todos los intentos con motivo,log y timestamps,incluso si el respaldo recupera el
fallo. Se almacena íntegro en el detalle del job. Checks,riesgo,revisión y aprobación
de efectos no se debilitan. Nunca fake→real. Un modelo/effort fijado y fallback
juntos se rechazan hasta poder configurar ambos proveedores sin ambigüedad.

OpenCode V2 se invoca con servidor privado (`run --standalone`),cwd del worktree y
`--format json` para el trabajo inicial;la revisión conserva texto para no buscar
veredictos dentro de eventos JSON de herramientas. No se cambia la configuración
global ni el servidor de tu sesión.
Requiere un binario scraft-ops actualizado compatible con el campo aditivo
`policy.fallback_executors`. El campo vacío se omite para unidades antiguas estrictas.
Compilar un binario de pruebas no sustituye ni instala el binario global.

### 5. Efectos y compuerta humana (`effects.py`)

Efectos que existen: `open_pr`, `update_notion`, `post_slack`. **`merge` y `deploy` no existen.**

- La política de cada efecto sale del perfil y del riesgo: `auto`, `human` o `forbidden`. Algo que
  necesita a una persona nunca baja de `human`; un run fallido no propone nada; lo `forbidden` ni se propone.
- Una persona aprueba una **huella** (hash del contenido exacto), no una frase. Si el contenido cambia,
  la aprobación no aplica. Aprobaciones con vigencia (24 h por defecto) y se invalidan si existe una
  corrida más nueva del mismo pedido.
- **La API solo registra la decisión** (`approved`). Un worker en el host ejecuta lo aprobado y vuelve a
  comprobar la vigencia. Credenciales y acceso a git nunca están en el proceso web ni en Docker.
- Marcador durable `executing`; un resultado incierto queda `uncertain` y no se reintenta a ciegas.

Control del trabajo desde la bandeja: pausar, continuar, detener, **reorientar** (conserva ambas citas
literales: el pedido original y tu corrección).

## Superficies HTTP

| Superficie | Confianza |
| --- | --- |
| `/api/collection/factory/{list,detail,admission,control,effect}` | Frontera local endurecida existente: host, origen, token de sesión, JSON estricto, límites de tamaño. Es la que usa la web. |
| `/api/factory/webhooks/whatsapp` | Firma `X-Hub-Signature-256` sobre el cuerpo crudo; **falla cerrado (503)** sin secreto configurado. Necesita un túnel para que Meta lo alcance. |

No existe ninguna ruta sin autenticar que mute la fábrica.

## Configuración (entorno explícito; nada se carga solo)

| Variable | Para qué | Por defecto |
| --- | --- | --- |
| `FACTORY_PROJECTS_FILE` | Registro de proyectos | vacío (sin proyectos: todo pide contexto) |
| `FACTORY_PROFILES_DIR` | Perfiles que sobrescriben los incluidos | vacío |
| `FACTORY_SCRAFT_OPS_BIN` | Binario `scraft-ops` | `scraft-ops` |
| `FACTORY_STATE_DIR` | Worktrees, logs y registros de corrida | `~/.scraft-ops/factory` |
| `FACTORY_AGENT_EXECUTOR` | `fake` (ensayo), `claude` u `opencode` | vacío: lo decide el proyecto/perfil;frontend prefiere OpenCode |
| `FACTORY_AGENT_FALLBACKS` | JSON allowlist de hasta un respaldo real,por ejemplo `["claude"]`;`[]` desactiva respaldo en los jobs que admita ese proceso | sin definir:hereda `fallback_executors` del proyecto,que por defecto es vacío |
| `FACTORY_GATEWAY` | `recording` (no hace nada, anota) o `real` | `recording` |
| `FACTORY_EFFECT_TTL_HOURS` | Vigencia de una aprobación | `24` |
| `FACTORY_NOTION_TOKEN` / `FACTORY_NOTION_DATABASE_ID` | Notion real (lectura de tareas y escritura de estado, esta última solo con aprobación y `FACTORY_GATEWAY=real`) | vacío (sin Notion) |
| `FACTORY_NOTION_STATUS_PROPERTY` | Nombre de la propiedad de estado | `Status` |
| `FACTORY_WHATSAPP_APP_SECRET` / `FACTORY_WHATSAPP_VERIFY_TOKEN` | Webhook | vacío (503) |

## Ensayo sin conexiones

```sh
# 1. Compilar scraft-ops (repo scraft-ops):  go build -o /tmp/scraft-ops ./cmd/scraft-ops
make test-db
make factory-rehearsal SCRAFT_OPS_BIN=/tmp/scraft-ops
```

Ejecuta la fábrica de punta a punta con el binario real de scraft-ops, un agente **falso**, repos
git temporales y pasarelas de efectos que solo anotan. Sin modelo, sin red, sin credenciales.

## Prueba final en el entorno conectado

El guion ejecutable, con criterios de paso y evidencia a entregar, está en [factory-test-plan.md](factory-test-plan.md). Resumen:

Orden sugerido; cada paso añade **una** capacidad real y se verifica antes del siguiente.

1. `make sync`, `make up`, `make test-db`, `make factory-rehearsal` en la máquina nueva (debe pasar igual).
2. Copiar `docs/examples/factory-projects.example.json` a `.local/factory/projects.json` con rutas reales.
3. **Solo lectura, sin agente real:** `FACTORY_AGENT_EXECUTOR=fake`, un `NotionAdapter` real
   (`FACTORY_NOTION_TOKEN` + `FACTORY_NOTION_DATABASE_ID`, `make factory-worker` con `--pull slack,notion`) y Slack ya recolectado. Comprobar que la admisión decide lo esperado sobre
   pedidos reales y que nada se ejecuta. (`update_notion` y `open_pr` siguen en `recording`.)
4. **Un agente real, un proyecto frontend, una tarea pequeña:** `FACTORY_AGENT_EXECUTOR=claude` (o
   `opencode`), `FACTORY_GATEWAY=recording`. Revisar el worktree y el `RunRecord` a mano.
5. **Un efecto real:** `FACTORY_GATEWAY=real` solo para `open_pr` (GitLab) con aprobación humana.
6. Después, lambdas y orquestador multi-repo.

## Qué está verificado y qué no

Comprobaciones, clasificadas antes de ejecutarlas: **obligatorias** por criterio de este incremento
(contrato JobSpec/RunRecord, admisión, compuerta de efectos, aislamiento de la API) salvo indicación.

| Qué | Cómo | Estado |
| --- | --- | --- |
| Contrato Go ⇄ Python, perfiles idénticos | `test_factory_cross.py` con el binario real | verificado con agente falso |
| Admisión, adaptadores, efectos, ejecutor | `test_factory_unit.py` | verificado |
| Embudo → cola → fencing → efectos, en PostgreSQL separado | `test_factory_service.py` | verificado |
| Frontera HTTP y webhook firmado | `test_factory_http.py` | verificado |
| Bandeja web "Fábrica" | `FactoryWorkspace.test.tsx`, typecheck, build; navegador local | mocks PASS; vista vacía observada escritorio/móvil, acciones reales aún sin verificar; ver factory-test-report.md |
| `NotionHttpClient` contra Notion real | solo con transporte simulado | **sin verificar** |
| `GlabGateway` (git push + `glab mr create`) | solo con procesos simulados | **sin verificar** contra GitLab real |
| `SlackCollectionAdapter` sobre el recolector vivo | consulta SQL simulada en la unidad | **sin verificar** con datos reales |
| Webhook de WhatsApp con Meta | firma y payload documentados | **sin verificar** con Meta real |
| `claude -p` / `opencode run` headless | construcción de argumentos | **sin verificar**: los flags se leyeron del `--help` local, no se ejecutó un agente real |
| Efectos `post_slack` | no hay pasarela | **no implementado** (se propone, no se ejecuta) |
| Despliegue en Docker de la API con el registro de proyectos | `compose.factory.yaml` | verificado localmente con registro vacío readonly, esquema0011, health200 y datos previos intactos; evidencia `.local/factory/validation/deployed-acceptance.json` |

Límites conocidos: el perfil no tiene paso de preparación (un worktree nuevo no trae `node_modules`; ver el plan de pruebas); un job es de un solo repositorio (la iniciativa multi-repo, con orden entre repos,
es trabajo de la capa siguiente); no hay topes de costo/tiempo por corrida más allá del timeout de la
unidad de ejecución; la política de admisión es por palabras clave y se afina con uso real.
