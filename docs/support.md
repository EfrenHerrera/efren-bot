# Soporte nuevo supervisado — alcance real de este incremento

La pestaña **Investigaciones de soporte** es independiente de conversaciones/asuntos,
recolección y `work/fake_db_v1`. No publica ni resuelve tickets, no modifica código ni
datos remotos. Ejecuta clasificación, análisis preliminar y respuestas mediante la
API oficial de OpenCode del host. No es todavía diagnóstico con logs y código.

## Qué funciona y qué está bloqueado

- Detección incremental de mensajes nuevos y clasificación real en su contexto.
- Si la novedad es soporte, caso automático con cola y progreso, sin selección inicial.
- Preliminar y borrador copiable, explícitamente **solo lo reportado en Slack**.
- Preguntas por caso, aportaciones/cambio de rumbo, pausa/reanudación y descarte humano.
- CloudWatch, GitLab y repositorios locales **no están conectados**: faltan alcance y
  mapeos aprobados. Estado `blocked/source_scope_pending`, nunca éxito ni causa confirmada.
  No existe un adaptador habilitable mediante texto Slack, instrucciones del modelo o
  contenido del chat. Aprobar un alcance futuro requiere implementar/validar ese adaptador.

El flujo completo solicitado sigue pendiente por esas fuentes. El catálogo documental
AWS no es autorización. La política instalada requiere plan acotado aprobado (perfil,
cuenta esperada, grupos exactos, entidad, ventana UTC y presupuesto). Para código hacen
falta repositorios/proyectos y referencias autorizadas, y contrastar versión desplegada.
No hay consultas AWS/GitLab ni lecturas de otros repositorios en esta entrega.

## Corte, identidades y preservación

Activación explícita fija un único `activated_at` UTC. Se examinan solo identidades
lógicas `(source_scope, channel_id, message_id)` cuya primera persistencia y fecha
original son posteriores al corte. Importaciones y cualquier identidad con variante
histórica quedan excluidas. Escanear de nuevo no modifica ese corte. Pausar/reanudar
no trae el histórico ni pierde novedades recibidas durante la pausa.

Una identidad se evalúa una vez; variantes y reentregas no son eventos nuevos. Ediciones
de mensajes anteriores no se autoactivan en esta versión. Una respuesta nueva en un hilo
antiguo sí puede disparar evaluación con contexto previo. El clasificador distingue
novedad accionable de gracias/repetición; ante incertidumbre no inicia investigación y
conserva la decisión para revisión. Clasificaciones humanas explícitas distintas de
soporte se preservan; un descarte/pausa no se deshace por un nuevo mensaje automático.

Casos por identidad explícita de conversación, sin agrupación semántica. No cambiar
identidades externas a UUID: UUID solo para filas internas y referencias JSON string.
Contexto congelado con IDs exactos y fechas, hasta 200 mensajes/65k caracteres, 4k por
mensaje, priorizando trigger, inicio y contexto reciente. Se marca truncado/parcial y
los originales siguen en collection. Los reportes son reportados/hipótesis/faltantes,
no una colección de hechos confirmados. No visitar source_url ni descargar archivos.

## Ejecución local

`make support-runner` inicia un proceso host separado. Requiere DB migrada a
`0010_human_control`, `APP_ENV=local`, CLI oficial OpenChamber existente y archivos propios:

```
.local/support/profile.json   {"providerID":"...","id":"..."}
.local/support/runtime/opencode.json  {"plugins":[]}
```

Perfil no secreto fijado al modelo existente de esta sesión de implementación,
`openai/gpt-6.1-sol`; no se copian credenciales ni se configura el HOME/global. No usa
el modelo genérico por defecto, no elige proveedores gratuitos ni hace fallback.
Cambiar perfil es decisión del usuario, no una respuesta a un error. No montar estos
archivos ni HOME en Docker; API/DB solo reciben estados y contenido local ya guardado.

Cada paso abre sesión técnica `agent=build`, modelo fijado y wildcard deny, verifica
metadatos y usa exclusivamente `POST /api/session/{id}/generate` transitorio. No llama
`prompt`, no programa agent-loop, no expone shell, MCP, herramientas ni endpoints de
fuentes. Salida JSON cerrada, sin markdown, IDs de evidencia validados; referencias
inventadas fallan. Sanitización previa al modelo y de su salida (secretos frecuentes,
correo, teléfono, RFC/CURP); no equivale a un DLP exhaustivo. Datos no confiables nunca
conceden permisos. Revocar/archivar y confirmar limpieza antes de aplicar un resultado.

Un paso de modelo por turno, máximo 150 s más cierre. Sin retry automático del modelo.
Fallo o interrupción se conservan como fallo, sin éxito ficticio. Si no se confirma la
limpieza de una sesión, se pausa el control global para impedir nuevas generaciones.
Advisory lock propio
impide dos runners. Heartbeat independiente; claim/finish y controles en transacciones
cortas, sin mantener locks durante generación. Preguntas pendientes tienen prioridad
al terminar el paso en vuelo; los casos se procesan por separado en cola serial, no
se promete ejecución paralela ni respuesta instantánea mientras genera.

Pausa global impide nuevas generaciones, no pausa Slack. Pausa de caso impide nuevo
análisis, pero preguntas explícitas pueden responder con evidencia ya guardada mientras
el control global siga activo. No se cancela una operación en vuelo: epoch/revisión
impiden aplicar su resultado invalidado. Preguntar no reinicia; cambiar rumbo incrementa
revisión y programa reanálisis, sin habilitar fuentes adicionales. Correcciones y
resultados anteriores permanecen en historial. Reanudar un caso descartado es explícito.

## HTTP y web

Todo bajo `/api/collection/support/`, mismas guardias Host/Origin/local/capability,
JSON cerrado, sin querystrings, no-store, errores sin payload privado:

- `POST list {}` →control, casos recientes (100, resúmenes sin contexto completo),
  decisiones recientes (30), fuentes pendientes. No es un conteo total del histórico.
- `POST detail {id}` →caso, contexto, reporte e historial de intervenciones.
- `POST activate|pause|resume {}` →control global; activate no reingiere histórico.
- `POST act {id,request_id,action,text=""}` →ID de entrada. Actions ask/redirect/pause/
  resume/dismiss. Ask y redirect requieren texto (máx.4k). Clave UUID idempotente por
  caso; payload distinto con misma clave→409. La corrección no se pierde al fallar.

La web hace polling cada 4s sin requests solapadas, cancela al desmontar y mantiene
texto ante fallo. No cambia silenciosamente de caso durante un borrador. Copiar solo
escribe al clipboard local por acción del usuario, nunca envía a Slack.

## Evidencia y pendientes

Pruebas sintéticas obligatorias: exclusión histórica/imports, replies nuevas, dedupe,
decisiones humanas, resultado invalidado por pausa/rumbo, pregunta idempotente, reinicio,
contratos protegidos, IDs inventados, sanitización, denegación de herramientas y UI.
La aceptación real de modelo se hizo exclusivamente con datos sintéticos; ningún caso
histórico usado. El soporte real con logs/código y la evaluación formal de riesgo siguen
pendientes. Git continúa diferido; sin commits, ramas, staging ni push.
