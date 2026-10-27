# Recolección Slack local

## Corrección vigente: conversaciones y asuntos humanos

La navegación principal ya no es una cola de comentarios a clasificar. Conversación
por `(source_scope,channel_id,raíz explícita)`; se usan las referencias no nulas de
todas las variantes guardadas, no solo la última. Una única raíz explícita resuelve
el hilo; ninguna referencia queda como mensaje sin relación confirmada; referencias
contradictorias se aíslan y muestran como conflicto. Nunca agrupación semántica.
Inicio no guardado y contexto parcial se indican; «todo» es todo lo conservado, no
una garantía de exportación Slack completa. Variantes/anotaciones anteriores intactas.

Mención = token literal de la cuenta fijada en cualquier mensaje/variante del hilo,
incluidas respuestas posteriores a la primera página. Puede ser cita/reenvío y no
prueba notificación ni encargo. Root/preview son texto real, no resumen generado.
Actividad nueva = mensaje lógico no histórico ingresado después del corte visto;
una variante repetida o agradecimiento no crea un asunto/tarea automáticamente.
Abrir una conversación no la marca vista ni clasifica sus comentarios.

POST protegidos `/api/collection/conversations/` (JSON cerrado, sin querystrings):
- `list`: `{offset=0,snapshot_at=null,channel_id="",query="",view="all",
  category=null,attention=null}` →conversations,total,offset,next_offset,snapshot_at,
  channels. Views all/mentions/following/new; tipo/atención filtran asuntos humanos.
  Cada entrada: UUID de mensaje ancla,idexterno conversación,preview,root_present,
  relation_status confirmed/unlinked/conflict,message_count,mention_count,new_count,
  group_count,last_activity_at,mention_previews. Orden por actividad;50por página.
- `detail`: `{id,offset=0,snapshot_at=null}` →conversation,groups,messages,total,
  offset,next_offset,snapshot_at,mention_locations(id/offset/excerpt). Mensajes
  cronológicos; root disponible en conversation, menciones localizables por página.
- `seen`: `{id,snapshot_at}` marca solo actividad hasta la instantánea observada,
  sin modificar atención/asuntos ni marcas antiguas por mensaje.
- `group-save`: `{conversation_message_id,request_id,id=null,revision=null,title,
  category="unclassified",attention="undecided",message_ids=[]}` →id,revision.
  Crea opcionalmente uno o varios asuntos collection, no tareas fixture/work.
  Evidencia vacía=todo el contexto; subconjunto=IDs de mensajes de esa conversación.
  Pueden compartir evidencia. Creación idempotente por request_id UUID, cambio de
  payload con misma clave→409; edición requiere revisión vigente, si no→409.
- `group-delete`: `{id,revision}` quita solo el asunto/evidencia propios, no mensajes.

Asuntos anclados a identidad lógica de mensaje, no a UUID de una variante: cambios
de representación no pierden el seguimiento. No migrar clasificaciones antiguas de
un comentario a todo un hilo. Esta unidad permite organización humana después de
leer contexto, no clasificación automática ni transición a done. Lista/contexto
simultáneos en desktop; selección/regreso en móvil. Checkboxes de evidencia aparecen
únicamente al organizar voluntariamente un asunto, no como requisito de lectura.

## Bandeja y revisión local — incremento autorizado

Historial y mensajes nuevos comparten bandeja paginada por50mensajes lógicos, no por
variantes. Una identidad es `(source_scope,channel_id,message_id)`; las capturas y
variantes se conservan. La representación mostrada es la última observada, no una
reconstrucción garantizada de ediciones Slack. Hilos accesibles cronológicamente;
representaciones distintas consultables aparte. Sin texto se muestra su ausencia,
sin fingir descarga de adjuntos. Importar no equivale a una captura nueva.

POST protegidos bajo `/api/collection`, JSON cerrado y errores sin eco de entrada:
- `/inbox/list`: `{offset=0,snapshot_at=null,channel_id="",query="",review="all",
  origin="all",category=null,attention=null}`. Devuelve messages,total,snapshot_at,
  offset,next_offset,channels. Mantener snapshot_at durante paginación; actualizar
  inicia otra instantánea. Revisión all/new/unreviewed/reviewed; origen all/historical/live.
- Mensaje añade historical,variant_count,reviewed_at,reviewed,is_new,category,
  attention y provenance. Nuevo = no histórico y no revisado; no implica un encargo.
- `/inbox/annotate`: `{id,reviewed?,category?,attention?}`. UUID de una variante
  resuelve identidad lógica. Campos omitidos se conservan; null no borra. Categorías
  unclassified/support/code_review/coordination/information. Atención
  undecided/required/not_required. No clasificador automático. Revisado no resuelve
  atención; reclasificar no modifica texto, tareas ni Slack. Estado local persistente.
- `/inbox/thread` y `/inbox/variants`: `{id,offset=0}` →messages,total,next_offset.
  Contexto por identidad de hilo explícita, sin asociación semántica inventada.
- `/sources/list`: `{}` →channels,observed_at; catálogo de membresía de último run
  conservado (sin lectura remota en API), fecha visible. Canales no confirmados no
  pueden habilitarse. El runner vuelve a comprobar membresía al recolectar.
- `/sources/save`: `{channel_id,mode}`. Modos full/mentions/off. Solo canales propios
  del catálogo; no une canales ni concede permisos. La configuración queda congelada
  al encolar un run. Cambios se aplican a siguientes ejecuciones, no al activo.
  Al habilitar captura completa nueva, inicio=guardado actual, sin backfill implícito.
  Desactivar no borra historia; DMs propios conservan política acordada por separado.

`python -m efren_bot.collection.archive` importa offline los dos índices auditados
del piloto autorizado de cinco canales. Verifica hashes de índices/registros y
fuentes inmutables antes/después; transacción única/idempotente, procedencia por
captura/hash/locator, originales externos intactos. No llama Slack ni adelanta
watermark/control. Tipo de run import se distingue de manual/automatic. Los tres
canales históricos adicionales no se habilitan para recolección futura por importarlos.
No se promete continuidad entre la ventana del archivo y la activación del recolector.

La interfaz concentra mensajes, filtros y anotaciones; «Actividad de recolección»
abre un diálogo lateral. Fuentes en otro diálogo, controles automáticos compactos.
Esc/Escape cierra, foco contenido y restaurado al disparador. No mocks en la web real.

Incremento autorizado independiente de demo y puente Claude. No clasifica, crea
tareas ni publica. Host/CLI/API oficial OpenCode con conexión Slack existente;
ningún token/HOME corporativo entra en API o Docker.

## Controles

POST /api/collection/activate fija inicio real UTC una sola vez y habilita automático.
POST /pause pausa nuevas ejecuciones automáticas, no captura en curso ni manual.
POST /resume habilita automático con próximo vencimiento15min.
POST /run encola ahora también pausado. Devuelve ejecución existente si ya hay
queued/running; no acumula clicks. GET /status devuelve control, heartbeat real,
ejecución activa, últimas20ejecuciones, conteo y últimos50registros de mensajes.

Todos bajo prefijo /api/collection: Host loopback conocido, Origin web exacto o
Fetch-Metadata same-origin, header no simple X-Efren-Local:1, sin CORS ni caché.
GET /session bajo esa barrera entrega capacidad efímera propia del proceso API;
resto exige X-Collection-Token. No se guarda en URLs/localStorage/logs. POST JSON
vacío acotado, campos extras rechazados. No autenticación multiusuario.

## Ejecutor y datos

Runner host único mediante advisory lock PostgreSQL de sesión, sin transacción
durante red. Control/cola en transacciones cortas. API nunca ejecuta Slack.
Heartbeat durante captura; sin ejecutor no se simula actualización. Tras caída,
run interrumpido failed sin avanzar watermark. Cada fuente/consulta conserva su
avance confirmado con solape de una hora para índice tardío, nunca anterior a
activación. Un DM inaccesible no bloquea el avance de otras fuentes. No adelantar
una fuente con páginas/formatos/hilos dependientes pendientes. Watermark global
solo cuando todo el run se confirma; parcial nunca se presenta como éxito global.
Capturas originales del conector se conservan. Migración0005 reconstruye solo
checkpoints de scopes agotados en runs históricos sin mensajes ni hilos; los
estados parciales históricos y capturas originales no cambian.

Fuentes: C08MAH1JNC8/devs y C07SRBE0V1T/tech completos en ventana; IM/MPIM propios
descubiertos por membresía; menciones literales al usuario autenticado fijado en
perfil en canales propios. Fuera de completos, solo mención e hilo. Historial y
búsqueda estructural para actividad de replies; hilos seleccionados sin filtros
temporales con contexto anterior rotulado. Sin descargar archivos ni visitar URLs.
Cursores repetidos/límites/formato desconocido →partial. Agotar búsqueda no prueba
totalidad del workspace; se muestra limitación del índice. Fechas aware UTC.

Tablas slack_collection_control/runs/captures/messages, independientes de
fixture/bridge/work. UUID internos nativos; canal/mensaje/hilo externos strings
opacos. source_scope fija la cuenta Slack del perfil y su workspace predeterminado,
no pretende ser un team_id Slack. Perfil fijado a usuario y dos canales evita
mezclar cuentas. Variantes por identidad compuesta+hash se conservan sin overwrite
ni merge semántico. Textos son representaciones, no exportación original Slack.
Pruebas solo efren_bot_test:55433. Sin nuevos servicios ni credenciales corporativos.

## Arranque y uso

API/web: `docker compose --project-name efren-bot up --build --detach --wait db migrate api web`.
Host: `make collection-runner` desde este checkout. No iniciarlo dentro de Docker;
requiere la CLI integrada en OpenChamber, su servicio y conexión Slack existentes.
Configuración propia ignorada `.local/collection/runtime/opencode.json`: plugin
local `tools/slack-collection`, options enabled=true y userId fijado a la cuenta
aprobada. No se instala otro SDK ni se leen/copian tokens. Antes de capturar se
contrasta esa identidad contra la descripción nativa del lector de búsqueda.

Abrir http://127.0.0.1:5173. Activar fija el inicio y programa15min; Recolectar ahora
no espera15min. Pausar no impide la ejecución manual ni corta una captura iniciada.
Recargar conserva pausa/avance/historia. La web no necesita permanecer abierta.
El runner debe seguir activo y el host despierto; no se promete ejecución suspendido.
Sin ejecutor se deshabilita el botón manual; no se muestran éxitos ficticios.

El puerto solo escucha loopback. El secret efímero web es propio de esta aplicación,
se reinicia con API y no es una credencial Slack. Tras reinicio API una solicitud
puede perder su capacidad; la siguiente lectura la obtiene otra vez, sin nuevo login.
Las capturas y representaciones pueden incluir información privada: no exportarlas
a Git, telemetría, logs, reportes de ejemplo ni herramientas de análisis no autorizadas.
