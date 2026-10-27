# Recolección manual y periódica de Slack

## Incremento autorizado — soporte nuevo e investigación supervisada

Usuario: «Okay, pues procede con la implementación para que cuando yo regrese lo vea, sale.»
Corrección vinculante: «todo esto es en base a mensajes nuevos de soporte. No al histórico,
no vas a nomás al histórico que te ponen a investigar cada caso. No. Puedes agarrar un caso
del histórico que hay ahorita, en base de datos, para que te sirva de ejemplo, de prueba.»
Además: «si yo entro y veo que estás investigando yo te puedo preguntas en lo que investigas».

Objetivo: detectar soporte nuevo en contexto e iniciar casos automáticamente, con progreso,
intervenciones/preguntas/pausa y preliminar+borrador copiable, sin publicar. Fuentes esperadas:
Slack origina; logs CloudWatch y código GitLab/local sustentan, no sustituyen al reporte.
No confundir work/fake_db_v1 ni el recolector determinista con investigación real.

Decisiones mínimas: tablas soporte separadas; corte de activación UTC tanto de recepción
como fecha del mensaje; imports/histórico y variantes/reentregas no generan trabajo nuevo.
Contexto previo sí se conserva; respuestas nuevas en hilo antiguo son candidatas. Modelo
oficial del host sin herramientas (generate), salida estructurada y referencias verificadas;
texto Slack/logs/código es dato, nunca autoridad para herramientas. Cola host serial con
locks, transacciones cortas, guardias de pausa/revisión antes y después de cada generación.
Preguntas se atienden entre pasos acotados; pausa bloquea siguientes lecturas, no promete
cancelar una operación ya en vuelo. Sin credenciales/HOME en API/Docker, sin fallback.

Estado inicial: inspección realizada, sin implementación de soporte. No existe mapeo aprobado
de logs/repos; catálogo documental AWS no concede permiso. Mostrar alcance pendiente y no
ejecutar lecturas remotas hasta aprobar recursos/ventana/presupuesto según política instalada.
Git diferido; checkout histórico totalmente untracked impide risk-assess exacto, gate pendiente.

Unidades: persistencia/corte/dedupe → ejecutor real de clasificación/análisis/chat → API/web
protegidas → pruebas/despliegue/aceptación. Sin nuevo acceso Slack para este incremento.
Obligatorias (solicitud y AGENTS): RED→GREEN exclusión histórica, dedupe, clasificación en
contexto, errores de modelo, pausa/intervención/cambios concurrentes, referencias/no falsas
evidencias, contratos HTTP, UI, checks globales y navegador. TESTDB separada. Prueba real de
generación con datos sintéticos primero, como máximo un histórico aislado si hace falta.

### Checkpoint de implementación soporte — fuentes todavía pendientes

- Implementados esquema0008/intakes/casos/historial, runner host separado y APIs bajo
  guardias collection. UI nueva con preguntas, corrección/pausa/descarte, preliminar,
  evidencia y clipboard. No se tocaron worker/fixture/work/recolector ni sus servicios.
- RED `ModuleNotFoundError support.service` observado; primeros15tests focales y13web
  pasan, todavía no sustituyen checks globales. El esquema quedó explícito/fijo en la
  migración, sin importar modelos vivos. Se añadieron más guardias después: checks pendientes.
- [runtime-observed] Generate oficial con datos sintéticos: clasificación soporte,
  análisis preliminar, respuesta de chat y agradecimiento→ignore. Evidencia
  `.local/support/synthetic-model-acceptance.json`. Cero casos históricos y cero lecturas
  AWS/GitLab/otros repos. Sesiones técnicas archivadas por HTTP confirmado.
- Fallos preservados: modelo genérico default flint devolvió native_api_failed en
  preflight sintético. Se fijó explícitamente el mismo modelo de esta sesión existente,
  openai/gpt-6.1-sol, perfil propio no secreto y sin fallback. Después session validation
  falló porque API añade variant=default; se corroboró y admitió solo ese valor exacto.
- Preservar clasificación humana, descartes y pausas; preguntas no invalidan análisis,
  cambio de rumbo sí. Epoch global y revisión por caso descartan resultados obsoletos.
  Limpieza no confirmada pausa automáticamente nuevas generaciones, no se trata como PASS.
- **Bloqueo de alcance funcional completo**: todavía no hay adaptadores de logs/código,
  ni un alcance aprobado para ellos. No basta con configurar un nombre en chat. UI,
  reportes y contrato `docs/support.md` muestran solo Slack y source_scope_pending;
  ningún preliminar es causa confirmada ni investigación técnica terminada.
- Próximo: checks globales, aceptación real sintética end-to-end en TESTDB, despliegue
  propio y corte nuevo en principal. No dejar casos ficticios en la bandeja real.

### Entrega parcial operativa soporte — 2026-10-26 UTC

La entrega no completa la investigación técnica solicitada: CloudWatch/GitLab/código
local siguen sin adaptadores ni alcance aprobado. No decir «investigación completa».
Sí está operativo el recorrido de soporte nuevo con evidencia Slack y control humano.

- [x] Esquema0008 en principal/TESTDB, API/web desplegadas solo en proyecto efren-bot.
  Pestaña «Investigaciones de soporte» abierta en http://127.0.0.1:5173/. Recolección
  anterior conserva automático cada15min y runner73600; no se reinició por extensión.
- [x] Corte propio activado `2026-10-26T03:06:24.830229+00:00` (25oct21:06 en web).
  Runner soporte32205 con heartbeat disponible. Escaneo real tras activación:0intakes,
  0casos,0barridos,0ejemploshistóricos. No se dejaron casos sintéticos en principal.
- [x] Clasificación/análisis/chat reales comprobados con datos sintéticos exclusivamente.
  Caso automático por respuesta nueva, preliminar source_scope_pending, chat persistido
  sin reiniciar y agradecimiento→ignore. No son resultados ficticios del fake worker.
  TESTDB limpiada tras aceptación, sin tocar principal. Evidencia fresca normalizada:
  `.local/support/e2e-testdb-final.json`; anterior conserva denegaciones runtime de
  patch/execute/read/slack_post_message vía evaluación oficial de permisos:
  `.local/support/e2e-testdb-acceptance.json`. No se ejecutaron esas herramientas.
- [x] Contratos validados: IDs inventados fallan; soporte exige referencia al trigger;
  reporte con hechos reportados exige evidencia. Sanitización no rompe JSON ni IDs.
  Herramientas wildcarddeny/modelo fijado comprobados; solo generate transitorio,
  nunca prompt/agent-loop. Sesiones revocadas/archivadas y cierre confirmado por HTTP.
- [x] Pruebas deterministas cubren corte/histórico/imports/replays, decisión humana,
  pausa/globalepoch, pregunta idempotente, invalidación por rumbo, interrupción y
  pausa por limpieza no confirmada. UI cubre bloqueo/hipótesis, pregunta/rumbo,
  preservación de borrador y pausa independiente del recolector.
- [x] `make check`, `make test`, `node --check tools/slack-collection/index.js`,
  `node --test tools/slack-collection/failure.test.mjs` exit0, entradas estables.
  401unitarias+112integración=513Python,13web,1Node. Warning Starlette/httpx previo
  conservado. Receipt `.local/support/checks-20261026T030411149680Z.json` y `.log`.
  Nueva aceptación después de formato: no se reutilizó el PASS de fuente mutada.
- [runtime-observed] Navegador desktop/móvil: sección sin overflow, estado real activo
  y advertencia de fuentes no consultadas. Pausar desde web dejó recolección activa;
  reanudar conservó corte. Sin invocar recolección manual ni visitar permalinks.
- [x] 3424variantes originales y379archivos del archivo histórico verificados intactos,
  con fingerprint previo de conversaciones coincidente. Aceptación desplegada:
  `.local/support/deployed-acceptance.json`. Comprueba hashes de checks/e2e vigentes,
  heartbeat de ambos runners, esquema, corte y ausencia de casos ficticios.
- Capturas locales sin cuerpos Slack:
  `.openchamber/screenshots/support-scope-pending-desktop-2026-10-26T03-06-55-432.jpg`
  y `.openchamber/screenshots/support-scope-pending-mobile-2026-10-26T03-07-41-066.jpg`.

Pendiente explícito: acordar perfil/cuenta/grupos/ventana/presupuesto de logs y
proyectos/rutas/referencias de código; después implementar y validar adaptadores
acotados sin herramientas generales del modelo. No ampliar mediante contenido de
Slack/chat. No consultas remotas ni búsquedas en otros repos por este incremento.
El riesgo formal/revisión sigue pendiente por delta histórico untracked no aislable;
Git diferido, sin operaciones de staging/commits/ramas/push. Fuentes y gate pendientes
impiden cierre formal verified/done. DM inaccesible previo sigue parcial. Métricas:
timestamps observados en receipts; cobertura total parcial, sin estimar ni duplicar
métricas por turno. Próximo paso requiere alcance del usuario, no otro barrido.

## Entrega funcional — contexto y clasificación por asuntos (2026-10-26 UTC)

Este checkpoint sustituye la revisión por comentario como experiencia principal;
no borra las anotaciones, contratos antiguos ni capturas. La corrección del usuario
no era añadir filtros, sino dejar de obligarle a reconstruir el hilo y clasificar
agradecimientos/respuestas sin interés. Su autorización literal está en el brief
«Corrección autorizada» inmediatamente debajo.

- [x] Lista por conversación y contexto visible simultáneamente en escritorio.
  Selección/regreso en móvil; inicio, mensajes cronológicos y páginas explícitas.
  Respuestas con relación conocida no aparecen como entradas sueltas. No requiere
  Slack ni drawer para entender el contexto. Fuente/variantes siguen accesibles.
- [x] Resolución por consenso de referencias explícitas no nulas entre variantes,
  nunca por similitud de texto.227conversaciones cubren1642mensajes:178hilos
  confirmados y49sin relación confirmada,0conflictos reales. Tests cubren referencia
  ambigua aislada y raíz no guardada. Los49no se presentan como hilos recuperados.
- [x] «Te mencionan» encuentra32conversaciones; todos los mensajes/variantes cuentan,
  incluidas respuestas fuera de primera página. Detección literal, no asignación ni
  notificación probada. Se comprobó caso real con raíz sin mención y respuesta con
  mención; prueba sintética incluye respuesta55y una variante posterior sin token.
  Tokens con nombre se muestran como @nombre, propia mención como Tú; ID diferente
  con mismo prefijo no se confunde. Texto fuente intacto, sin nueva consulta de perfiles.
- [x] Sin controles de revisión/clasificación por comentario en lectura normal.
  Organización voluntaria de uno o varios asuntos collection, con título/tipo/
  atención y evidencia seleccionada o contexto completo. Sin tareas fixture/work,
  inferencia, clasificación automática ni transición a done. Actividad nueva no crea
  asunto; verla hasta una instantánea no resuelve atención ni oculta futuras replies.
- [x] Migración0007 en TESTDB/principal: followups, referencias lógicas de evidencia
  y corte visto por conversación. UUID nativos internos; referencias externas opacas
  separadas. Creación idempotente, revisión para editar/quitar, validación de evidencia
  dentro del hilo. Cambios de relaciones no descartan evidencia silenciosamente.
- [x] HTTP local bajo guardias existentes, DTOs cerrados, cuerpo acotado, secretos y
  errores privados sin eco. Abrir contexto no marca visto ni organiza automáticamente.
  Borrador preservado ante409; selección fijada durante edición para evitar perderlo
  por una actualización del recolector. Requests cancelados al cambiar/desmontar.
- [runtime-observed] Desde navegador: creado un asunto con contexto completo y dos
  más con un mensaje distinto cada uno; primer asunto reclasificado a soporte.
  Recarga mostró3asuntos y edición revisión2, evidencias0/1/1. Después se quitaron
  exclusivamente esos3asuntos temporales; seguimiento final0. No clasificaciones de
  trabajo reales inferidas por el agente.3424variantes no cambiaron con esas acciones.
- [runtime-observed] Escritorio y móvil revisados; en móvil «Ir a mención2» llevó el
  foco a una respuesta, resaltada dentro del contexto. No se visitó el permalink ni
  otro enlace incluido en mensajes. Mención citada/reenvío sigue rotulada como literal.

### Verificación y límites de esta entrega

Comprobaciones obligatorias clasificadas antes de ejecución por criterio/AGENTS:
agrupación, scope, raíz ausente/conflictos, menciones tardías, actividad no igual a
tarea, asuntos/evidencia/idempotencia/conflictos, privacidad HTTP, UI y checks globales.
RED inicial módulo conversations ausente →implementación →GREEN. Un test falló por
groups anidados frente a DTO esperado; se alineó el contrato a groups en detail.
Parche atómico con contexto HTTP desactualizado no se aplicó parcialmente; se volvió
a aplicar solo al archivo correcto. Imports/formato normalizados antes de la evidencia.

- `make check`, `make test`, `node --check tools/slack-collection/index.js`,
  `node --test tools/slack-collection/failure.test.mjs` →exit0.397unitarias+
  100integración=497Python,9web,1Node. Warning Starlette/httpx previo conservado.
  Receipt final con hashes/versiones/comandos/timestamps y entradas estables:
  `.local/collection/conversations-checks-final-20261026T014055504337Z.json`
  y su `.log`. El primer PASS anterior al refinamiento de presentación se conserva
  en `conversations-checks-20261026T013357358492Z.json`, no sustituye al final.
- API/principal0007 y web desplegadas localmente; último ajuste de presentación
  reconstruyó solo web con `--no-deps`, sin reiniciar el servicio global ni el runner.
  Runner73600 y automático activo conservados. No nuevas lecturas Slack manuales,
  reimportación del archivo, modelos, credenciales, SDK corporativo ni cambios Git.
- Prueba web/asuntos/restauración:
  `.local/collection/conversations-browser-groups-20261026T013937638029Z.json`.
- Aceptación final5páginas/227IDs de conversación únicos,1642mensajes,32conmención,
  fuentes originales379verificadas intactas,3424variantes y0asuntos temporales:
  `.local/collection/conversations-acceptance-20261026T014353099005Z.json`.
  Comprobó fingerprints de todas las entradas cubiertas y heartbeat disponible.
- Capturas privadas locales, no publicar cuerpos en reportes/Engram:
  `.openchamber/screenshots/conversations-final-desktop-2026-10-26T01-41-52-608.jpg`
  y `.openchamber/screenshots/conversations-mobile-reply-mention-2026-10-26T01-43-09-478.jpg`.

Disponible http://127.0.0.1:5173/, pestaña abierta en escritorio. Cobertura funcional
observada, no cierre formal verified/done: delta Git histórico sin seguimiento no
aislable, riesgo/revisión formal siguen pendientes y Git diferido. DM inaccesible
continúa parcial. Contexto es el guardado, no garantía de totalidad Slack/continuidad.
Métricas: timestamps reales de checks/runtime, cobertura end-to-end parcial; sin
estimaciones ni duplicación de métricas de cierre. No continuar otro alcance por extensión.

## Corrección autorizada — conversaciones y asuntos por grupo

Usuario: «Ok, procede justo así, porque al final de cuentas tenemos en consideración que yo tengo que ver la lista y todo, y justo dentro de ese mensaje con el de ese hilo puede que me hayan mencionado o que me hayan solicitado algo. O sea, no directamente en el mensaje me van a decir. Puede ser que dentro de ese todo ese contexto de ese hilo alguien me haya etiquetado igual. Y eso me interesa. Me interesa todo el contexto y ver si esa es una sola tarea, o lo dividimos en dos o en tres, y así lo clasificamos también en grupo.»

- Invalida el enfoque previo de clasificar cada comentario. Unidad de navegación:
  conversación por relaciones explícitas, contexto visible al seleccionarla dentro
  de la web; sin obligar a abrir Slack/drawer para entenderla. Respuestas como
  agradecimientos quedan dentro, no entradas independientes cuando existe relación.
- Menciones literales a la cuenta fijada en cualquier respuesta/variante guardada,
  no solo raíz o primera página. Señal de contexto, no notificación/encargo probado.
  Sin resumen semántico ni tareas inferidas automáticamente.
- Usuario organiza opcionalmente uno o varios asuntos locales por conversación,
  con título, tipo, atención y evidencia seleccionada o contexto completo. Sin
  controles de marcado/clasificación por mensaje fuera de ese modo voluntario.
  No usar tablas fixture/work ni automatizar tareas. Edición/eliminación de asuntos
  propia, con idempotencia y revisión para no perder cambios entre pestañas.
- Acompañantes necesarios: tablas collection independientes, contrato protegido,
  migración y cambio de UI. Conservar anotaciones/variantes/originales anteriores;
  no convertir una anotación de mensaje en revisión de todo el hilo.
- [runtime-observed] Agregados locales read-only:1642mensajes,227conversaciones,
  1415respuestas con relación,49mensajes sin relación explícita,0conflictos. Esto
  discrimina el fallo de presentación; no inventar enlaces para los49restantes.
- Diseño: lista/contexto simultáneos en escritorio; selección y regreso claros en
  móvil. Controles/filtros compactos, actividad de recolección sigue secundaria.
- Obligatorios por solicitud/AGENTS: RED→GREEN de agrupación/raíces ausentes,
  menciones en replies y páginas tardías, aislamiento por canal/scope, asuntos1→3,
  evidencia/idempotencia/conflictos y no modificación de fuentes, tests HTTP/UI,
  checks globales, despliegue y navegador. TESTDB separada; sin nuevas lecturas Slack
  por diagnóstico. Riesgo formal/delta Git siguen pendientes, Git no autorizado.

## Incremento autorizado — bandeja revisable y fuentes configurables

Usuario: «Procede entonces.» tras solicitar primero analizar la bandeja, mover
ejecuciones a botón/dialog/drawer, ver historial y nuevos ordenados, reclasificar
y poder agregar/modificar canales privados predefinidos.

- Implementar bandeja paginada de mensajes lógicos, contexto cronológico de hilo,
  filtros por fuente/origen/revisión/atención/tipo. Anotaciones manuales persistentes
  separadas del texto; sin inferencia, tareas ni publicaciones. Tipos iniciales
  explícitos: sin clasificar, soporte, revisión de código, coordinación e información.
- Importar offline el archivo previamente autorizado de cinco canales, con capturas
  y variantes originales intactas/procedencia; histórico no se etiqueta nuevo. No
  habilitar automáticamente los otros tres canales para siguientes recolecciones.
- Configurar canales ya accesibles desde membresía conservada, modo completo,
  solo menciones o desactivado. Guardar cambios sin borrar mensajes ni alterar un
  run en curso; nuevas fuentes completas desde su activación, sin backfill implícito.
- Cambios acompañantes necesarios: contrato/excepción local, migración, endpoints
  cerrados protegidos y runner que congela configuración por run. Sin modificar Git,
  credenciales, configuración global, fuentes corporativas nuevas o fixtures.
- Diseño: bandeja azul pizarra existente, controles compactos arriba, lista como
  protagonista y detalle en drawer. Lectura/revisión no significa atención resuelta.
- Comprobaciones obligatorias por usuario/AGENTS: RED→GREEN de paginación (>50),
  dedupe/variantes, anotaciones, configuración congelada, importación idempotente,
  privacidad HTTP; make check/test y Node; despliegue/navegador y recarga. TESTDB
  separada. Riesgo formal sigue pendiente por delta Git histórico no aislable.
- Estado inicial: sin clasificación/revisión ni configuración en modelos; API
  devuelve50registros como máximo. Archivo piloto fuera del producto y sin importar.

## Entrega activa — controles web y ejecutor común

Usuario: «Ok, pues concluye porque ya necesito ver eso. Este igual hay que contemplar que en la web debería yo poder pausarlo y ejecutarlo automáticamente de manera manual. Por si no han pasado 15 minutos y me urge algo.»

- Pausa persistente del automático, reanudación y ejecución manual inmediata incluso
  pausado; una sola ejecución en vuelo. Pausar no corta la captura en curso.
- Implementar host local sin inferencia mediante CLI/API oficial OpenCode; lifecycle
  técnico por HTTP oficial, no por el helper SDK cuyo archivado no quedó acreditado.
  No resetear sondas históricas: nuevas ejecuciones con identidad y evidencia propias.
- Persistencia PostgreSQL separada de fixtures/tareas: control, runs y mensajes con
  procedencia/variantes. Web protegida por Host/Origin/capacidad efímera local.
- Acompañantes necesarios: contrato/excepción de alcance local explícitos, migración,
  proxy web solo de esta función, comando de runner host. Sin secretos corporativos,
  publicaciones, adjuntos descargados ni cambios de otros proyectos/Git.
- Criterios obligatorios antes de ejecutar: pruebas de control/paginación/política,
  integración en TESTDB separada, frontend, lint/typecheck/build, Compose config,
  prueba host real acotada y controles desde navegador. Fuente: solicitud y AGENTS.
  Riesgo formal/delta Git exacto continúa pendiente por árbol histórico sin seguimiento;
  no modificar Git para despejarlo ni confundirlo con aceptación funcional observada.

## Objetivo y solicitud vigente

Usuario: «Ok, en entonces lo que vamos a ahorita es definir, ya dejarlo funcionando para probar estos días el flujo de recolección automática de Slack. Tanto manual como automática, y eso de estar igual en la web yo debo recolectar. Y se recolectan, pero periódicamente debes tenerlo igual.»

Esta es la prioridad activa, distinta de interpretar un hilo histórico o importar
manualmente una propuesta JSON. No construir esa otra funcionalidad por extensión.
Colección histórica existente: [slack-history-pilot.md](slack-history-pilot.md).
Los resultados de aquel archivo no acreditan un recolector activo del producto.

## Alcance acordado — 2026-10-25

- Disparador manual «Recolectar ahora» en web y disparador automático cada 15 minutos.
- Canales completos: `crd-wc-devs` y `crd-wc-tech`.
- Conversaciones directas propias individuales y grupales. Respuesta explícita:
  «También DMs grupales».
- Menciones explícitas al propio usuario en canales a los que pertenece, incluidos
  otros distintos de los dos anteriores. Respuesta: «En mis canales», definida en
  la pregunta como recoger mensaje con mención y su hilo, no todo el canal.
- Primera recolección desde la activación; siguientes desde el último avance
  confirmado. La activación aún no ocurrió y no hay un watermark real fijado.
- Ejecución periódica condicionada a host encendido y ejecutor disponible; no se
  prometió ejecución durante apagado/suspensión ni recuperación ya implementada.

## Recorrido propuesto, todavía sin implementación

Un mismo recolector atiende ambos disparadores y conserva procedencia, mensajes y
contexto disponible de hilos, cobertura/faltantes, avance y resultado de ejecución.
Evitar duplicados y carreras manual/periódico; no avanzar sobre páginas pendientes.
La web debe permitir solicitar una recolección y distinguir espera, ejecución,
resultado parcial, fallo y última actualización real, sin simular conexión.
Recolectar no interpreta, crea tareas ni ejecuta acciones sobre mensajes.

## Límites y dependencia real

Sin publicaciones Slack, adjuntos descargados, visitas a enlaces, fuentes ajenas,
SDK corporativos, tokens copiados ni HOME montado en producto/Docker. Mantener
fixtures, worker e historia existentes separados. CloudWatch y Git siguen diferidos;
no ramas, commits, worktrees ni despliegues de otros servicios por extensión.

Antes de escribir el recolector o admitir datos reales hay que acreditar una vía
oficial del host para que web y ejecución periódica soliciten lecturas acotadas.
El catálogo de herramientas de esta sesión no demuestra esa interfaz de producto.
La excepción actual de AGENTS.md es solo el puente manual Claude; no ampliarla por
analogía. Cualquier acompañante necesario de reglas/contratos debe hacer explícito
el nuevo alcance sin abrir acceso corporativo general.

No construir primero una pantalla ni un ejecutor vacío para aparentar el flujo.
La ruta de acceso del ejecutor es la dependencia pendiente, no la selección de
canales/frecuencia ni otro acuerdo sobre interpretar mensajes.

## Evidencia de preparación y límites

Comprobaciones de capacidad clasificadas obligatorias antes de ejecutar, fuente:
solicitud de flujo real y AGENTS.md (no afirmar runtime por configuración).

- Catálogo host consultado sin ejecutar herramientas de contenido: interfaces de
  lectura de canal/hilo, listado de conversaciones IM/MPIM y búsqueda con filtros.
  No se hizo una lectura Slack ni se comprobó autenticación nueva.
- CLI oficial integrada encontrada en
  `/Applications/OpenChamber.app/Contents/Resources/opencode-cli/opencode`;
  `--version` devuelve `opencode v2.1.3`; `api --help` presenta rutas HTTP y servidor.
  No usar la CLI global ni cambiar versiones/configuración.
- `service status` devuelve `stopped` para el servicio compartido. No describe ni
  detiene la instancia privada activa de OpenChamber. No se inició otro servidor.
- Revisión estática acotada de configuración Slack: entrada presente, remota,
  endpoint oficial, `disabled:false`, cliente OAuth configurado. Solo se imprimieron
  booleanos, sin valores OAuth ni otras configuraciones. Esto supera el estado
  estático deshabilitado del registro histórico, no demuestra conexión ni aprobación
  efectiva de app por el workspace. No se leyeron credenciales ni cambió el archivo.
- Referencia histórica relevante: [openchamber-slack-proxy.md](openchamber-slack-proxy.md),
  cuya última continuación dejó una app propia preparada para PKCE; no asumir que
  haga falta crear otra ni revivir el proxy antiguo o el puente Claude.
- Documentación oficial V2 de API/cliente/plugins/MCP revisada: no se ha acreditado
  todavía una llamada desatendida a Slack desde el producto. Sin pruebas de
  backend/web/DB, activación, schedule, admisión real ni cierre formal de riesgo.
- Prueba nativa posterior, sin modelo ni tools/call: CLI oficial `api --standalone
  get /api/mcp`, con salida capturada en memoria y solo estado/estructura sanitizados.
  Primer intento devolvió JSON, pero el reconocedor no encontró Slack: no se tomó
  como PASS. Se corroboró el contrato oficial y se repitió la lectura de metadatos;
  respuesta `{location,data}` con `data` array y cero entradas de nombre `slack`.
  Tercer intento con `location[directory]` explícito confirmó el proyecto correcto
  y otra vez cero entradas Slack. No acredita auth fallida: ni siquiera expone ese
  servidor en ese runtime temporal; causa de carga/configuración aún no demostrada.
- Contraste acotado de configuración efectiva por `api --standalone get /api/config`
  en el proyecto: Slack presente y habilitado, imprimiendo solo dos booleanos. El
  comando documentado `debug paths config` confirma el directorio global esperado.
  Configuración presente no equivale a servidor registrado/conectado. Bloqueo real
  para continuar integración: demostrar el acceso del ejecutor fuera de este chat.
- Recuperación documental: extracción OpenAPI mediante urllib terminó HTTP403;
  lectura del mismo documento público con webfetch funcionó. No es un fallo Slack
  ni se intentó sortear autorización. `serve --help` consultado, no se ejecutó serve.
  Las invocaciones privadas de API terminaron; no se creó modelo/sesión de análisis,
  schedule, lector de mensajes ni listener del producto.

## Siguiente paso

Resolver y comprobar la interfaz oficial del ejecutor host antes de implementar
la integración web/periódica. No pedir otra vez canales/frecuencia/punto de inicio,
ya acordados. No convertir acceso de conversación en autenticación de aplicación
ni dar por operativo un recolector por haber preparado configuración.

## Findings & adjustments — continuación tras «procede»

- Usuario autoriza continuar resolviendo acceso. La prueba privada adicional mostró
  cero plugins en general; la ausencia de Slack no demostraba un fallo de OAuth.
- Tras comprobar `service status=stopped`, se ejecutó una sola vez el `service start`
  oficial, exit0, sin cambio de configuración ni login. El usuario comunicó reinicio
  del servidor y pidió continuar sin repetir trabajo. No se repitió el arranque.
- Servicio persistente oficial observado: versión2.1.3, PID92469,93plugins,
  nueve servidores MCP y Slack `connected`. Hubo dos lecturas equivalentes de
  metadatos al retomar; se conservan como repetición de inspección, no pruebas
  distintas de lectura de contenido. No se llamó ninguna herramienta Slack.
- El bloqueo de registro desaparece en el runtime persistente; no extrapolar el
  comportamiento de `api --standalone` a ese runtime. Causa interna de la diferencia
  de carga no demostrada, no requiere tocar configuración global.
- Próxima comprobación acotada: adaptador RPC propio en un workspace temporal del
  host, cargado solo en esa ubicación, con el SDK oficial de plugins2.1.3. El API
  público `ctx.tool.list()` expone ejecutores Promise y sus contextos; se comprobará
  su invocación determinista con una sola lectura de metadatos de un canal permitido,
  sin generación de modelo ni cuerpos de mensajes. No modificar plugins del proyecto
  actual, reiniciar el servidor ni usar el puente Claude o el proxy antiguo.
- El servicio persistente ya está disponible tras el reinicio de la sesión; no
  detenerlo automáticamente al terminar una prueba. Web, almacenamiento de mensajes,
  admisión real y horario periódico siguen sin implementar/activar.
- Prueba de adaptador aislado en temporal aprobado `efren-slack-native-access/`:
  código y config solo de esa ubicación; no plugins globales/del proyecto. Primera
  suite sintética RED por módulo ausente → cinco PASS. El import directo de
  `@opencode/schema` no resolvió: se retiró, sin instalar dependencias ni cambiar
  versiones. Se pasó a plugin JS con SDK público principal ya disponible.
- Fallo propio de inicialización RPC: faltaba `events:{}`, obligatorio en tipos
  oficiales2.1.3; diagnóstico `Object.entries` sobre undefined → corrección →
  plugin `active`. Fallo propio siguiente: asumir array en `ctx.mcp.list`; el SDK
  devuelve `{location,data}` → tests RED de frontera por módulo ausente → módulo
  de validación → siete tests PASS y catálogo RPC válido. Los fallos previos se
  conservan; no son fallos demostrados de OAuth/Slack.
- Activación de plugins precede a conexión/catálogo MCP en la nueva ubicación.
  Hubo un ensayo fallido por consultar antes de disponibilidad; no reiniciar el
  servidor ni recargar repetidamente por ello. Después se observó Slack conectado
  y ocho herramientas registradas, con binding exacto `slack_slack_list_channel_members`.
- Rechazo nativo de argumento extra `channel_id`: `rpc.invalid_input`, contador
  de lecturas cero antes/después. Único intento positivo reservado: canal devs,
  limit1, formato IDs; devolvió `read_failed`, contador1. Ese contador reserva un
  intento antes de construir argumentos/contexto; NO demuestra una llamada Slack
  ni una lectura exitosa. La causa se perdió en el catch genérico; no atribuirla
  a auth, permisos ni sesión sin evidencia. No se repitió la lectura real.
- Evidencia privada no secreta: `evidence/native-access.json` conserva el ensayo
  de disponibilidad fallido; `evidence/native-access-attempt-2.json` conserva el
  rechazo y el intento fallido. Solo receipts/estados, sin IDs de miembros/cuerpos.
- Lectura del probe deshabilitada por defecto mediante `allowMetadataRead !== true`.
  Diagnóstico sin Slack confirmó que el signal del RPC existe y se puede construir
  el signal combinado. `reader_callable:false` se observó durante arranque; no
  extrapolarlo a ausencia permanente (el catálogo anterior sí estaba disponible).
- Siguiente discriminador **sin relecturas corporativas**: fixture MCP local
  sintético, solo en otra ubicación propia `fixture-runtime/`, y helper que separa
  contexto/ejecución/validación sin exponer errores privados. Pruebas de ambos
  componentes quedaron RED por archivos aún ausentes antes de implementarlos.
  La sonda de miembros no es requisito del recolector; su fallo no prueba que
  `read_channel` o el resto de lecturas estén bloqueadas. Los IDs de contexto del
  probe son transitorios, no mensajes/sesiones nativos persistidos; NO adoptar esa
  suposición para producción sin validar el contrato de ejecución.
- Adaptador experimental únicamente bajo temporal aprobado:
  `/private/var/folders/kh/h4blnjhx4cz49v5cd9lw8yv80000gp/T/opencode/efren-slack-native-access/`.
  Configuración de plugins solo en su subdirectorio `runtime`, sin plugin del repo
  ni configuración global editados. No npm install ni dependencia añadida: se retiraron
  imports transitorios no resueltos y se usa el SDK público principal ya disponible.
- Intentos conservados: tests iniciales RED por módulo ausente →5PASS; registro
  falló por import de `@opencode/schema`; corregido a plugin JS. Luego falló setup
  por `events` ausente (obligatorio en Rpc.Definition2.1.3) →events:{} →plugin active.
  Catálogo RPC dio rpc.internal por tratar McpListOutput como array en lugar de
  `{location,data}`; frontera corregida y probada. Nuevos tests RED por frontera
  ausente →7PASS. `node --check index.js` PASS. Hubo parches fallidos por contexto
  esperado distinto; no se asumió su aplicación y se releyeron los archivos propios.
- Carga activa de plugins no implica MCP conectado: la primera comprobación del
  runtime propio devolvió Slack no listo; después MCP9/Slack connected y catálogo
  con los ocho IDs exactos. No volver a refrescar la ubicación ante una mera espera
  de conexión. Solo se usó DELETE `/api/debug/location` con la ruta propia, nunca
  `location.reload` global ni un reinicio adicional.
- Prueba nativa posterior: override de canal en RPC →`rpc.invalid_input`, contador
  aún0. Un único intento permitido de `slack_list_channel_members` (canal devs,
  limit1, ids_only) →`read_failed`, contador1. No lectura confirmada ni causa atribuida;
  el contador se reserva como intento potencial porque incrementaba antes de construir
  los argumentos/contexto. No confundirlo con llamada Slack efectiva demostrada.
  No se consultaron mensajes, DMs ni menciones. El catch inicial ocultó el diagnóstico:
  corregir observabilidad antes de otra prueba real, sin repetir lecturas a ciegas.
- Evidencia sin cuerpos: `evidence/native-access.json` (primera espera fallida) y
  `evidence/native-access-attempt-2.json` (rechazo correcto e intento fallido), dentro
  de ese temporal. Se preservaron ambos. No se sobrescribió un fallo por PASS.
- Lectura del probe ahora deshabilitada por defecto, requiere opción local explícita
  `allowMetadataRead:true`; no habilitarla al retomar por extensión. Diagnóstico seco
  sin llamar Slack confirmó señal RPC presente, API abort y construcción de señal
  correctas. El adaptador usa IDs de correlación transitorios, no sesiones/mensajes
  nativos persistidos: no adoptar ese supuesto para producto sin acreditar la interfaz.
  No se ha demostrado que ese contexto sea la causa del fallo.
- Próxima discriminación, sin más lecturas corporativas: fixture MCP local sintético
  en ubicación propia para probar la misma ruta `ToolInfo.execute` y capturar clase
  de fallo por etapas. Fixture RED observado (servidor aún ausente); implementación
  y native proof pendientes. No es conector ni evidencia de recolección real.

## Findings & adjustments — contexto nativo, 2026-10-25

- [runtime-observed] Los ensayos del fixture local reprodujeron `read_failed` en
  `invoke_reader`; tests de invocación8PASS y del servidor local1PASS no acreditaban
  la ejecución nativa. Evidencias `native-fixture-nested-cause.json` y anteriores
  quedan conservadas, sin relecturas corporativas. El último parche histórico que
  proponía `fixture_native` no estaba en el archivo al retomar; se inspeccionó el
  contenido real antes de implementar, sin asumir aplicación por el historial.
- [deterministic] Fuente pública exacta `@opencode/core@2.1.3`,
  `dist/chunks/instruction-discovery-9hbqwfdp.js` (src/tool/mcp.ts): el ejecutor hace
  `permission.assert` antes de `mcp.callTool`; su mapError descarta la causa de
  errores ajenos a ToolFailure y devuelve solo `Unable to execute ...`. La forma
  real del error no contenía `error/cause`; seguir recorriendo causas no lo resolvía.
- [runtime-observed] Ejecutar la misma comprobación pública de permiso, separada
  del mapError MCP y solo con el fixture sintético, devolvió `Session.NotFoundError`.
  Evidencia `evidence/fixture-20261025T230215559167Z.json`. Esto identifica el fallo
  del contexto transitorio del prototipo; no demuestra un fallo de OAuth/Slack.
- [runtime-observed] Corrección experimental `native-fixture.mjs`: crea una sesión
  nativa mediante SDK, usa sus IDs de sesión/agente devueltos, sin prompt, generación
  ni modelo cambiado. Permisos deny-all + allow exclusivo `efrenbot_fixture_probe`;
  finally archiva esa sesión y deja deny-all. El mensaje/call de correlación sigue
  transitorio, sin mensaje nativo insertado. Su validez para este fixture sí quedó
  acreditada; no convertirla en garantía de otros flujos.
- Pruebas de ciclo de vida: RED módulo ausente y luego desacuerdo de export/import;
  interfaz alineada con archivo real →3PASS (identidad/scope, fallo del lector y
  archivo incluso cuando falla lectura de métricas). `node --check index.js` PASS.
  Hubo repetición de RED y parches por contexto desactualizado; se conservan como
  intentos, no comprobaciones distintas de éxito. No se instaló dependencia.
- [runtime-observed] `python3 -B run-fixture.py fixture_native` →read_confirmed,
  member_count1 sintético, archived=true, zero_inference_usage=true; guardia de
  lecturas corporativas bloqueada. Evidencia con fingerprints y tiempos observados:
  `evidence/fixture-20261025T230320393398Z.json` en el temporal aprobado. No convierte
  los fallos anteriores en PASS ni prueba acceso Slack. Se usó runner propio reusable;
  recargas exclusivamente de fixture-runtime, sin reiniciar servicio/global.
- Próximo discriminador autorizado: una sola sonda de metadatos del mismo canal
  devs con contexto nativo y presupuesto persistido, tras esta corrección probada.
  No repetir a ciegas ni iniciar mensajes/DMs/menciones. Recolector común, web,
  persistencia del producto, admisión real y período15min siguen pendientes.

## Estado vigente — sonda corregida y cierre de diagnóstico (2026-10-25)

- Ensayo nativo de metadatos reservado una sola vez en `metadata-runtime`:
  `native_probe` →`rpc.internal`, sin recibo. Presupuesto local y de storage consumido;
  no se reseteó ni se repitió la lectura. Evidencia
  `evidence/metadata-20261025T230450174137Z.json`. No hay lectura real confirmada.
- [deterministic/runtime-observed] El helper extraído omitía `agent`, mientras el
  handler inline anterior sí creaba la sesión con `agent:build`. La API creó una
  sesión técnica sin agente; el helper rechazó su identidad antes de `reader.execute`.
  La fuente pública Session.create no asigna agente por defecto. No atribuir este
  fallo a permisos Slack. Una definición duplicada `fixture_native` ocultaba al
  helper nuevo; se retiró junto con el schema duplicado. El PASS anterior prueba el
  handler inline, no el helper que aún no se había ejecutado en runtime.
- Corrección: creación explícita con agente técnico `build` ya existente, sin prompt,
  inferencia ni cambio de modelos/configuración global. `prepare_context` ahora
  devuelve fallo controlado si la API no devuelve identidad válida, sin llamar al
  lector y archivando la sesión. Tests cubren agente explícito y ausencia de identidad.
- Obligatorios por criterio de diagnóstico real/AGENTS.md, ejecutados sobre el
  temporal: `node --check index.js` PASS;
  `node --test native-fixture.test.mjs policy.test.mjs invocation.test.mjs fixture.test.mjs`
  →21PASS. Hubo repeticiones equivalentes registradas, no pruebas independientes.
- `python3 -B run-fixture.py fixture_native` con helper normalizado
  `explicit-agent-v2` →lectura sintética confirmada, inferencia cero, pero su lectura
  inmediata de estado devolvió `archived:false`. No declarar PASS de limpieza por
  el exit0 del runner. Evidencias `fixture-20261025T230858647215Z.json` y
  `fixture-20261025T230905825495Z.json`. No se llamó Slack en estas pruebas.
- [runtime-observed] Limpieza por `ctx.session.update` no acreditó el archivado;
  separar revocación/archivo en helper tampoco bastó en esos receipts. No se conoce
  aún la causa en la interfaz Promise; no inferirla ni modificar el SDK/servidor.
  Se usó API HTTP oficial para archivar exclusivamente las sesiones técnicas propias
  por ruta+título exactos y comprobar su estado fresco. Hubo una comprobación fallida
  conservada antes de esa reparación; nunca se contó como éxito.
- Limpieza final comprobada con API oficial: cuatro sesiones técnicas propias
  archivadas, deny-all y coste cero; sin más lecturas fuente. Evidencia privada
  `evidence/final-direct-cleanup-20261025T231000220517Z.json`. El primer reconocedor
  CLI omitía el envelope `{data:...}` y produjo falsos negativos de archivo; se corrigió
  antes de confirmar. SDK y CLI no se confunden como la misma frontera.
- `metadata-runtime/opencode.json`: ambas opciones de lectura ahora false. Recarga
  solo de esa ubicación propia y RPC `native_probe` →`capability_unavailable` confirmado.
  El presupuesto persistido continúa reservado. No otro login, credenciales copiadas,
  instalación, reinicio global, mensajes/DMs/menciones, modelo ni prompt nuevo.
- Próximo paso pendiente: normalizar el ciclo de vida de sesión contra la API oficial
  con la misma ruta sintética antes de otra sonda real autorizada, sin resetear ni
  ocultar los intentos consumidos. Luego acreditar acceso real e integrar recolector,
  persistencia privada, web y horario. No hay activación/watermark ni schedule.
- Cambios del repo en esta continuación: documentación únicamente; prototipo fuera
  del repo. Pruebas backend/web/DB no ejecutadas (sin delta de producto que verificar);
  aceptación completa y riesgo formal pendientes. Checkout sigue enteramente sin
  seguimiento: no hay delta exacto para cerrar riesgo, Git permanece diferido.

## Findings & adjustments — contexto nativo contrastado (2026-10-25)

- [runtime-observed] Fixture implementado y ejecutado; los intentos previos con IDs
  transitorios fallaron en `invoke_reader`, diagnóstico inicialmente `unclassified`.
  Suites previas: política/frontera7PASS, fixture1PASS, invocación8PASS. No equivalen
  a acceso real. Sus receipts permanecen en el temporal aprobado, sin sobrescribir.
- [deterministic] Código publicado `@opencode/core@2.1.3`, chunk
  `instruction-discovery-9hbqwfdp.js` (src/tool/mcp.ts): primero ejecuta
  `permission.assert` con sesión/agente; su `mapError` sustituye errores ajenos a
  ToolFailure por otro error con mensaje genérico, sin conservar causa. La inspección
  runtime de propiedades confirmó que el error exterior no tenía `error`/`cause`.
  Recorrer más causas no podía recuperar información descartada.
- [runtime-observed] Separar `ctx.permission.assert` antes del ejecutor del fixture
  produjo `Session.NotFoundError` con los IDs transitorios. Evidencia privada:
  `evidence/fixture-20261025T230215559167Z.json`. Es causa observada de esa reproducción,
  no diagnóstico de OAuth/Slack ni evidencia retrospectiva de la llamada real.
- [runtime-observed] Contraste con sesión técnica nativa creada por el SDK, sin
  prompt/generación: mismo fixture →`read_confirmed`,1miembro sintético, archivada,
  uso de inferencia cero. Permisos exclusivamente fixture y deny-all tras archivado.
  `native-fixture.mjs` y RPC `fixture_native` están solo en temporal. Tests de ciclo
  de vida RED por helper/import ausente →3PASS; `node --check index.js` PASS.
  Evidencias `fixture-20261025T230320393398Z.json` y
  `fixture-20261025T230321058162Z.json` registran dos ejecuciones equivalentes; la
  segunda es repetición, no una aceptación distinta. Lecturas corporativas adicionales0.
- La propuesta de añadir `fixture_native` del checkpoint anterior no estaba en el
  archivo real al retomar; se inspeccionó disco antes de implementarla. Hubo fallos de
  parches/import por estados esperados distintos; se corrigieron contra el contenido
  real, sin atribuirlos al proveedor. El runner reutilizable conserva receipts con
  permisos0600 y huellas de entradas; sus exit0 solo indican diagnóstico ejecutado,
  la aceptación depende explícitamente del receipt.
- Estado: resuelta la reproducción sintética del bloqueo; falta acreditar la lectura
  real con contexto nativo y después implementar recolector/persistencia/web/horario.
  El probe antiguo sigue deshabilitado; no se activó ninguna recolección ni watermark.
  Riesgo/cierre global pendientes: el checkout está enteramente sin seguimiento y no
  hay delta Git exacto de esta función. Git sigue diferido, sin cambios de topología.

## Estado vigente tras el ensayo de metadatos — 2026-10-25

Este apartado prevalece sobre los «próximos» anteriores; no borra intentos fallidos.

- Se intentó una sola sonda corregida de metadatos en `metadata-runtime`, con
  `native_probe`, canal/limit fijos y presupuesto persistente. Resultado:
  `rpc.internal`, sin receipt de fuente (`evidence/metadata-20261025T230450174137Z.json`).
  No se repitió. Presupuesto reservado en storage y fichero privado; no resetearlo.
- Diagnóstico local sin fuente: storage legible y presupuesto reservado. La sesión
  técnica existía sin agente, coste/input/output0. El helper nuevo había omitido
  `agent`, y su guardia fallaba antes de ejecutar el lector. No adjudicar ese fallo a
  Slack. La prueba sintética previa pasaba por un handler inline duplicado, que sí
  fijaba `agent:build` y sombreaba al helper. Inspección completa reveló el desacuerdo;
  se retiraron las dos definiciones duplicadas y se fijó el agente técnico en create.
- Native helper ahora devuelve diagnóstico controlado si falta identidad, antes
  del lector. Tests comprueban agente explícito, argumentos/permisos fijos, ausencia
  de llamada con identidad incompleta, manejo de fallo y limpieza. Suite final
  `node --test native-fixture.test.mjs policy.test.mjs invocation.test.mjs fixture.test.mjs`
  →21PASS; `node --check index.js` PASS. Son obligatorias para esta corrección por
  criterio/AGENTS, no tests del recolector ni sustituto de los globales del producto.
- [runtime-observed] El RPC sin duplicados ejecuta ahora el helper compartido v2:
  `native_context_version:explicit-agent-v2`, `read_confirmed`,1miembro sintético,
  uso0. Evidencias `fixture-20261025T230858647215Z.json` y
  `fixture-20261025T230905825495Z.json`; la segunda repite comando, no es aceptación
  distinta. Ese receipt devuelve `archived:false`: NO afirmar limpieza verificada
  dentro del helper por recibir exit0. Actualización de permisos/archivo se separó;
  persiste diferencia entre el SDK y el estado esperado. Ese ciclo de vida aún no
  está listo para adoptar como implementación del producto.
- Limpieza acotada realizada mediante API oficial HTTP/CLI solo sobre las sesiones
  técnicas propias (título exacto y ubicación propia), con permisos deny-all y archivo
  como peticiones separadas. Las comprobaciones que confundían el envelope `{data}`
  se conservaron como fallidas y se corrigieron. La lectura final de inventario,
  sin ejecutar fuente, confirmó cuatro sesiones archivadas, deny-all y coste0:
  `evidence/cleanup-list-state-20261025T231006466901Z.json`. No extrapolarlo al
  funcionamiento del helper. No nuevos prompts, inferencias ni datos de mensajes.
- `metadata-runtime/opencode.json` quedó con `allowMetadataRead:false` y
  `allowNativeMetadataRead:false`; recarga exclusivamente de esa ubicación y RPC
  de la sonda →capability_unavailable. Original/runtime/fixture no se habilitaron.
- Estado del producto sin cambios: acceso real todavía sin confirmar, no recolector
  común/persistencia/web/horario15min ni watermark activos. No se tocaron API, DB,
  worker, web, credenciales ni configuración global; sin commits/ramas/push.
- Próximo paso: terminar el ciclo de vida técnico y contrastar la vía real con una
  nueva ventana de prueba acotada, sin reciclar el presupuesto consumido ni repetir
  pruebas que ya tienen evidencia. Después corresponde la integración del producto,
  explicitar su excepción de alcance y mantener separados fixtures/semántica/tareas.
   Riesgo/delta Git y verificación global siguen pendientes, no declarar «done».

## Findings & adjustments — entrega funcional local (2026-10-26 UTC)

Este checkpoint reemplaza los estados de prototipo/no implementación anteriores,
sin borrar los ensayos ni ampliar su presupuesto. La activación real ocurrió desde
la web el 25 de octubre aproximadamente a las18:06 de Mérida; no se importó historia.

- [x] Implementados API `/api/collection`, persistencia independiente, runner host y
  web con Pausar/Reanudar automático, Recolectar ahora, progreso real e historial.
  Host/Origin/capacidad efímera propia protegen la frontera. Sin cambios de tareas,
  fixtures, interpretación, publicaciones, adjuntos ni credenciales corporativas.
- [x] Runner determinista por CLI/API oficial OpenCode2.1.3 y plugin propio
  `tools/slack-collection`, identidad exacta del lector fijada. Sesiones técnicas
  creadas con agente explícito; revocación/archivo comprobados por API HTTP oficial,
  no mediante el helper SDK experimental. Sondas históricas intactas/deshabilitadas.
- [runtime-observed] Membresías:48canales y99conversaciones directas. La llamada
  combinada solo devolvía DMs: se separaron ambas consultas, sin atribuir causa interna.
  Dos capturas reales solicitadas desde web:107páginas cada una,0registros nuevos
  en sus ventanas y resultado parcial conservado. Cero no se rellenó con ejemplos.
- Primera captura: fallos transitorios y formato vacío desconocido. Se añadió
  reconocimiento cerrado de `# Search results for:` / `No results found.`, códigos
  de error y diferimiento ante rate limit. Los reintentos diagnósticos devolvieron
  vacío válido, sin demostrar que los fallos iniciales fueran por rate limit/OAuth.
- Segunda captura: solo DM `D0B6BKJSYF9` pendiente con `channel_unavailable`.
  Referencia explícita del mismo usuario también falló. No más fallbacks/credenciales.
- [x] Principal y TESTDB migradas a `0005_collection_progress`.104scopes agotados
  recuperados conservadoramente desde runs sin mensajes/hilos; el DM pendiente no
  se adelantó. Avance por fuente con solape, dependencias de hilo y watermark global
  únicamente ante éxito completo. Los dos runs originales siguen parciales.
- [x] Navegador: activar, pausar, manual antes de15min también pausado, recargar
  conservando pausa/ejecución y reanudar. Snapshot final: automático habilitado,
  heartbeat disponible y controles reales. Pestaña del producto abierta para usuario.
- [runtime-observed] Primer disparo automático real al vencer el intervalo:
  2026-10-26T00:32:53Z; observado running en API y navegador (45páginas en snapshot
  posterior). Esto acredita el disparo, NO el resultado terminal aún no observado.
  Runner PID55700 propio, `.local/collection/runner.pid`. No LaunchAgent instalado;
  requiere host despierto y ejecutor vivo. No schedule de modelos/OpenChamber.

### Evidencia y recuperación

- Obligatorios por solicitud/AGENTS: controles, concurrencia, parsers, scope,
  persistencia, HTTP, frontend, lint/format/typecheck/build y Compose. RED previo a
  implementación registrado; prueba de head falló al conservar0003, alineada con
  incremento. Migración0005 falló en TESTDB por bind accidental `:thread`; corregido
  a `right(child->>'scope', 7) = ':' || 'thread'`, luego18tests focales PASS.
- Reejecución final sobre entradas estables: `make check`, `make test`,
  `node --check tools/slack-collection/index.js`,
  `node --test tools/slack-collection/failure.test.mjs` →todos exit0.
  396unitarias+85integración=481Python,4web,1Node. DB de pruebas separada55433.
  Receipt con hashes antes/después, versiones, timestamps y comandos:
  `.local/collection/checks-final-20261026T003325645309Z.json`; salida completa
  `.local/collection/checks-final-20261026T003325645309Z.log`.
- API/web desplegadas mediante Compose solo proyecto `efren-bot`; aceptación runtime
  posterior a0005: `.local/collection/acceptance-final-20261026T003313607557Z.json`.
  No cuerpos ni capacidades en esos reportes. La evidencia anterior
  `acceptance-20261026T001819453762Z.json` queda intacta, no acredita el delta0005.
- Captura visual:
  `.openchamber/screenshots/slack-collection-automatic-running-2026-10-26T00-34-15-933.jpg`.
  Contrato operativo: `docs/slack-collection.md`. Enlace: http://127.0.0.1:5173/.
- Cobertura de métricas parcial: timestamps reales de checks/runtime, no cronometraje
  end-to-end del trabajo previo; no estimaciones ni métricas de cierre duplicadas.

### Límites pendientes

Entrega funcional disponible para probar; no cierre formal verified/done. Árbol
histórico entero sin seguimiento impide aislar delta exacto/risk-assess y revisión
formal aplicable. Git sigue diferido: sin staging/commit/push/ramas/worktrees.
Pendientes concretos: resultado terminal de la primera automática, cobertura del DM
inaccesible si el conector la restablece y cierre de riesgo cuando usuario retome Git.
No repetir capturas completas ni diagnosticar credenciales por extensión.

## Findings & adjustments — bandeja entregada localmente (2026-10-26 UTC)

Solicitud original de este incremento, seguida por «Procede entonces.»:
«Ok, vamos por partes entonces. Si tu ya tienes el editorial guardado aquí es donde debemos hacer un ajuste en la web. En la web, primero que nada, no quiero ver últimas ejecuciones y me ocupan toda la pantalla. Puedes agregarlo a un ladito como un botón que abra un diálogo o un draw, lo que quieras, pero no me debería ocupar la pantalla. Ahora, en mensajes recogidos, aquí hay que tener en cuenta algo. Me debería mostrar todos los mensajes. Pero de cierta forma hay que antes de modificarlo hay que analizarlo, porque principalmente debemos poder ver los mensajes que hubo y los mensajes nuevos, obviamente ordenados, viendo. pues que hay en cada mensaje y todo lo que tu decías, más que nada porque como usuario yo debo poder ver, ah, mira, estos son mensajes nuevos que tengo que atender, y estos están clasificados de cierta forma. Ah, los voy a reclasificar porque están mal clasificados, tal vez. O sea, como usuario debemos poder hacer varias cosas acá, y justo igual debería yo poder modificar de igual forma los canales predefinidos, este, los canales privados que se pueden configurar. Por ejemplo, ahorita solo está Crdw C Deps y Crd W C Tch. Como privados, y esos igual deberían ser modificables por mí. Yo podría agregar canales allá.»

### Aceptación observada

- [x] «Últimas ejecuciones» retiradas del área principal; botón Actividad de
  recolección abre diálogo lateral nativo. Abrir/cerrar observado en navegador;
  cancelación Escape cubierta por seam/test. Contención y retorno de foco usan el
  diálogo nativo y cleanup explícito; no se afirma recorrido de teclado real.
- [x] Bandeja de identidades lógicas, con variantes conservadas aparte. Filtros por
  canal, contenido, histórico/reciente, nuevos/sin revisar/revisados, atención y tipo.
  Más recientes primero; hilo en orden cronológico. Sin asociaciones semánticas.
- [x] Migración0006 principal y TESTDB; annotations por scope/canal/mensaje,
  revisión/atención/tipo independientes y persistentes. Corrección manual no modifica
  mensajes, Slack ni tareas. Tipo inicial sin clasificar, atención por decidir.
- [x] Importación offline del archivo aprobado:1642mensajes lógicos/3424variantes,
  316capturas con mensajes,379archivos originales byte-idénticos antes/después.
  Índices auditados y hashes de registros comprobados; importación atómica e
  idempotencia real repetida sin añadir registros. Histórico no se etiqueta nuevo.
  Importación no cambia control, watermark ni configuración: devs/tech completos;
  los otros46canales del catálogo mantienen solo menciones según política previa.
  No se habilitan completos los tres canales adicionales por importar su archivo.
- [x] Configuración en panel aparte:48canales accesibles del catálogo conservado,
  modos completo/menciones/desactivado. Cambios congelados al encolar cada run;
  nueva captura completa desde guardado, sin backfill implícito; desactivar no borra.
  Guardado/snapshot/aislamiento de membresía probados en TESTDB; catálogo y controles
  comprobados en navegador sin dejar fuentes cambiadas por la prueba.
- [x] Paginación real recorrida por API:33páginas,1642IDs únicos, sin duplicados ni
  recorte final. Navegador Siguiente mostró51–100de1642. Instantánea por stored_at
  (ingreso a DB), no observed_at de Slack: importar algo antiguo entre páginas no
  altera la instantánea. Prueba específica reproduce ese caso.
- [x] Prueba desde web: primer mensaje clasificado como soporte y marcado revisado;
  recarga conservó ambos, atención siguió por decidir. Después se restituyeron tipo
  sin clasificar y no revisado; comprobación final confirmó cero clasificaciones,
  revisiones o atención provisional dejadas por el agente.
- [x] Vista Nuevos vacía con explicación correcta;1642enTodos. Contexto real de un
  hilo45mensajes disponible; variante original separada accesible. Nada sintético
  añadido a la web/base principal. Screenshots desktop1440/móvil390 revisados.
- Runner propio reiniciado tras parada ordenada:PID73600, heartbeat disponible,
  automático habilitado (paused=false), configuración de usuario conservada. El
  resultado terminal de la primera automática anterior ya se observó:partial,
  107páginas,0nuevos, solo DM inaccesible. No repetirla por este incremento.

### Checks, intentos y evidencia

Obligatorios por solicitud/AGENTS, clasificados antes de ejecutar: pruebas de
contratos/HTTP/privacidad, paginación, anotaciones, variantes, importación idempotente,
fuentes/snapshot y frontend; checks globales; despliegue/navegador. Test-first RED
por módulo inbox ausente → implementación →GREEN. Se conservan también fallos
intermedios: nombre SQLAlchemy text sombreado por columna (alias corregido),
opción exact no válida en ByRoleOptions y seam showModal ausente en jsdom (adaptado
solo en pruebas), normalización/import-order. La migración0006 se iteró únicamente
en TESTDB, downgrade/upgrade de esa base separada; principal solo recibió la final.

- `make check`, `make test`, `node --check tools/slack-collection/index.js`,
  `node --test tools/slack-collection/failure.test.mjs`: todos exit0, entradas estables.
  397unitarias+94integración=491Python,9web,1Node. Warning de Starlette/httpx ya
  existente, sin nueva dependencia ni cambio del lock.
- Receipt/versiones/hashes antes/después/comandos/timestamps:
  `.local/collection/inbox-checks-20261026T005806888148Z.json`; salida completa en
  `.local/collection/inbox-checks-20261026T005806888148Z.log`.
- Importación/integridad completa:
  `.local/collection/inbox-import-20261026T005937434612Z.json`.
- Persistencia web tras recarga (antes de restaurar anotaciones):
  `.local/collection/inbox-browser-annotations-20261026T010206801821Z.json`.
- Aceptación API desplegada,33páginas,restauración,idempotencia,fuentes,runner y
  fingerprints aún equivalentes:
  `.local/collection/inbox-acceptance-20261026T010507759389Z.json`.
- Capturas privadas locales (no publicar cuerpos en reportes/Engram):
  `.openchamber/screenshots/slack-inbox-desktop-2026-10-26T01-00-13-824.jpg` y
  `.openchamber/screenshots/slack-inbox-mobile-2026-10-26T01-03-31-981.jpg`.
- Despliegue acotado: `docker compose --project-name efren-bot up --build --detach
  --wait --wait-timeout 90 db migrate api web`; host sin HOME/credenciales en Docker.
  La API no leyó el archivo host; solo el importador local lo hizo. No nueva lectura
  Slack manual, modelo, clasificación automática, tareas ni publicación.

Entrega funcional en http://127.0.0.1:5173/, pestaña abierta enTodos/primera página.
No equivale a cierre formal verified/done: riesgo exact-delta/revisión aplicable
siguen pendientes por Git diferido y árbol sin seguimiento. DM inaccesible permanece
parcial. No se garantiza continuidad temporal entre archivo histórico y activación,
ni captura durante suspensión o tras reinicio sin ejecutor. Clasificación automática
no implementada. Cobertura de métricas parcial, sin estimaciones ni cierre duplicado.
