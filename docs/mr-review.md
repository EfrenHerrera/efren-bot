# Revisiones de MR: evidencia privada y decisiones humanas

Incremento independiente de conversaciones, soporte y fixture/work. La sección
**Revisiones por decidir** muestra todas las MRs de una solicitud Slack, con cola,
versión, avance y propuestas por MR. No publica por decisión del modelo.

## Fuentes y alcance

Lecturas host `glab api --hostname gitlab.com --method GET`, conexión existente:

- Core: `konfio/organization/guilds/core/core`, proyecto `40652545`.
- Web: `konfio/organization/scope/p01/contexts/c01/domains/web/konfio-app-web`, `64374983`.

URLs se validan y convierten en destinos construidos por el lector, nunca endpoints
propuestos por el modelo. Otro proyecto queda bloqueado sin impedir los autorizados.
Sin Git/checkout, código de MR ejecutado, BD, CloudWatch, Temporal, CMS, adjuntos ni
fuentes nuevas. La autorización de MR no amplía los adaptadores pendientes de soporte.
API/Docker no reciben HOME, tokens ni credenciales GitLab/OpenCode.

Activar fija un corte UTC propio. Solo mensajes nuevos por identidad compuesta
`(source_scope, channel_id, message_id)`, primera persistencia y fecha original posteriores
al corte, sin variantes históricas/importadas. Reentregas y ediciones no disparan otra
revisión; una respuesta nueva en un hilo anterior puede pedir re-review. El modelo evalúa
la novedad, no agradecimientos ni todos los links antiguos automáticamente. Anotaciones
humanas explícitas sin `code_review` prevalecen. La pausa conserva el corte y novedades.

La única demo histórica habilitada es el mensaje ya guardado
`C07SRBE0V1T/1792770316.988339`, con !8573/!8594/!8616. No hay URL libre ni barrido.
`demo=true` impide publicación tanto en admisión API como en el host. Repetir demo no
duplica la solicitud ni cambia el corte.

## Revisión estática, no certificación runtime

1. Capturar metadata, refs SHA, versión de diff, discusiones y jobs CI del head.
2. Planear hipótesis y hasta24 rangos de dependencias propias o de MRs de la solicitud.
3. Leer rangos inmutables bajo allowlist de archivos, máximo501 líneas/rango y65k
   caracteres de contexto adicional. No se interpretan comandos del modelo.
4. Analizar arquitectura, Clean Code con impacto, datos/costo, contratos, negocio,
   seguridad, pruebas e integración. Contrastar head propio y dependencias leídas antes
   de aceptar el informe. Propuestas sobre líneas añadidas, con citas existentes.

Captura acotada:60 llamadas/cliente,45s/GET, respuesta máxima4MB; diff95k caracteres,
discusiones3 páginas de100, texto45k aproximado, pipelines20/jobs100. Cualquier omisión,
truncado o fuente no disponible se muestra como limitación, nunca revisión completa.
El plan no es búsqueda global ni indexación; archivos fuera de la allowlist se bloquean.
El filtro también se aplica al contenido de diffs: un archivo fuera de alcance conserva
solo metadatos/limitación, no su cuerpo. Docs `.rst` están permitidos, secretos no.
Los originales de collection no se modifican. La sanitización de texto no es DLP exhaustivo.

El límite del modelo es230k caracteres JSON serializados, no solo texto de archivos.
Rangos de líneas añadidas se compactan sin perder líneas y se eliminan metadatos
duplicados; fuentes originales permanecen. Las dependencias consumen además ese límite
total y reservan espacio para limitaciones. Agotar presupuesto detiene lecturas restantes
y deja cobertura parcial visible, sin error de contexto ni borrado silencioso de evidencia.

Cada dimensión distingue inspeccionado con evidencia estática, limitado y no aplicable.
No se exige cantidad de hallazgos. Los comentarios anteriores no son prueba de corrección;
`addressed_in_code` necesita cita de código. Métricas reportadas por otro revisor no se
presentan como mediciones propias. CI con `allow_failure` no implica E2E exitoso.
`partial` conserva informes útiles y faltantes; no habilita publicación. `ready` significa
propuestas para decisión, nunca aprobación de MR ni pruebas ejecutadas por este producto.

## Control, historial y publicación individual

### Lectura en la web

La vista abre en **Resumen**: conclusión, carácter parcial y comentarios para decidir.
Los faltantes y límites de lectura se despliegan por separado; no hace falta recorrer
listas de rutas para llegar al resultado. **Análisis** reúne las ocho dimensiones y
antecedentes; abrir una dimensión permite consultar sus fragmentos de evidencia.
**Conversación** separa preguntas/respuestas del historial de resultados y decisiones.
Navegar estas vistas no reinicia una revisión ni envía el borrador.

Código inline y bloques cercados se muestran con tipografía monoespaciada. Cada fragmento
de evidencia conserva archivo/ref y lenguaje; los diffs distinguen adiciones y eliminaciones.
Los bloques tienen desplazamiento horizontal propio y botón para copiar su texto, sin
números de línea inventados. El formato soporta párrafos, listas, negritas y código;
no interpreta HTML, descarga imágenes ni activa enlaces del contenido no confiable.
Copiar/editar/publicar un comentario conserva su cuerpo original, incluido el Markdown:
la presentación nunca reescribe el texto aprobado. El estado parcial y la demo sin
publicación siguen visibles aunque se colapse el detalle técnico.

Pregunta: responde con evidencia guardada y no reinicia. Cambio de rumbo o reanudación:
incrementa revisión y recaptura, conservando informes anteriores. Pausa: invalida el paso
en vuelo; no puede deshacer una petición remota ya enviada. Epoch global/revisión impiden
aplicar resultados obsoletos. Una MR fallida no impide las demás. Ejecutor serial: preguntas
y autorizaciones se atienden al terminar el paso en vuelo, no durante una generación.

Editar/descartar requiere revisión y versión de propuesta exactas. La web conserva
borradores en memoria al cambiar de MR/pestaña o fallar; no promete recuperarlos tras
cerrar/recargar el navegador. No se sobrescribe la decisión humana con una generación.

Publicar exige acción humana individual y confirmación del cuerpo concreto. Se congela
cuerpo/posición/refs/versión y epoch; el host relee MR, exige abierta y mismo head, comprueba
que la propuesta siga privada y sin editar, y registra durablemente `sending` antes del
único POST a `discussions`. No existe operación de aprobar, resolver ni mergear.
Pausa previa/edit/revisión nueva cancela la admisión; pausa posterior al envío conserva
el resultado. Una caída tras `sending` o respuesta ambigua queda `uncertain`, sin retry
automático ni nueva autorización sobre la misma propuesta. Reintento HTTP con el mismo
request_id devuelve la misma entrada; mismo ID/contenido diferente da409.

La comprobación del head no es un compare-and-swap remoto: el código puede cambiar
entre GET y POST. La posición del comentario siempre queda ligada a los SHA aprobados;
no se promete atomicidad entre GitLab y la DB local ni exactly-once de red.
**No se prueba publicación real con esta demo**; solo dobles de transporte.

## Ejecución y HTTP

Migrar primero a `0010_human_control`. `make review-runner` inicia el host, con advisory lock
propio, heartbeat10s y loop2s; no se inicia desde la API ni desde Docker. Requiere
`APP_ENV=local` y archivos ignorados con permisos restrictivos:

```
.local/review/profile.json           {"providerID":"openai","id":"gpt-6.1-sol"}
.local/review/runtime/opencode.json  {"plugins":[]}
```

La capa de [control humano común](human-control.md) también se aplica desde estas rutas
y antes de cada lectura host. Esta actualización no autoriza arrancar los ejecutores:
actualmente detenidos; reanudación operativa requiere acuerdo separado.

Una sesión oficial text-only transitoria por paso, deny-all verificado, sin agent-loop,
herramientas ni fallback. Generación180s más cierre; salida JSON cerrada y citas validadas.
Limpieza no confirmada pausa el control global. Error conserva código seguro sin payload
privado; no se reintenta modelo automáticamente. Reiniciar marca pasos interrumpidos
fallidos y publicaciones en vuelo inciertas. Reanudar una MR es decisión explícita.

Rutas `POST /api/collection/reviews/`, guardias locales Host/Origin/capability/JSON/no-store:

- `list {}`: control,100 MRs recientes,30 decisiones recientes; no total histórico.
- `detail {id}`: solicitud/contexto, snapshot, plan, informe, propuestas e historial.
- `activate|pause|resume {}`: control global independiente del recolector/soporte.
- `demo {request_id}`: solo el mensaje histórico aprobado ya persistido.
- `act {id,request_id,revision,action,text="",proposal_id=null,proposal_version=null}`:
  `ask|redirect|pause|resume|edit|discard|publish`. Texto requerido ask/redirect/edit,
  máximo5k. IDs internos UUID DB/string JSON; IDs GitLab/Slack strings externos.

## Estado de aceptación

API/web desplegadas y principal migrada a0009; recolección y soporte conservados.
Las tres MRs autorizadas produjeron informes reales de ocho dimensiones. Todos son
**parciales**, con faltantes de dependencias/pruebas e integración explícitos; cero
comentarios nuevos suficientemente sustentados, sin fabricar hallazgos para llenar la UI.
Hay evaluaciones de discusiones anteriores contrastadas con el head actual. Ninguna MR
se considera aprobada ni completamente verificada. Publicaciones reales: cero.

Primer intento: dos fallos `review_context_budget`, conservados en
`.local/review/attempt-1/`. Corregido el cálculo/proyección de contexto, repetición
controlada de esas dos MRs: informes parciales válidos, artefactos en `attempt-2/`;
el informe anterior válido de !8594 se revalidó con evidencia de head reforzada.
Aceptación en `.local/review/demo-acceptance-latest.json`, checks/preservación y
capturas de escritorio/móvil en los archivos enlazados desde `.odd/mr-review.md`.
No inferir runtime del build. La edición/publicación se probaron con dobles; la demo
real verifica la denegación HTTP409 `demo_read_only`, nunca realiza un envío de prueba.
Git y evaluación formal de riesgo siguen pendientes por delta histórico no aislado.
