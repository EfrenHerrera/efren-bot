# Revisión de MRs con propuestas y decisión humana

## Autorización y límites

Usuario: «Okay, pues procede, ¿qué necesitas?».
Alcance confirmado: «Core y konfio-app-web (Recommended)» para lecturas automáticas
de solicitudes nuevas en Slack. Prueba: «Sí, usar ese hilo», la solicitud aislada
https://konfio.slack.com/archives/C07SRBE0V1T/p1792770316988339 con !8573/!8594/!8616.
Corrección vinculante: «si viene más un Mr en el en el mensaje de Slack pues hay que
revisar todos los que». No selección de uno ni barrido del histórico.

Profundidad validada: seguir comportamiento/datos/dependencias y capas, Clean Code,
costos/consultas, contratos, pruebas e interacción entre MRs; no limitarse a CI/estilo.
Referencia histórica Charlybot no concede acceso a BD, Temporal o Storyblok, ni permiso
para ejecutar código de MR. No exigir cierto número de hallazgos; evidencia insuficiente
queda pendiente, comentarios anteriores/resueltos no se presentan como defectos nuevos.

Usuario sobre permisos: «haces tus propuestas, y tú me preguntas a mi en una sección»;
después él puede indicar publicar/correr/reorientar. Lecturas autónomas dentro de dos
proyectos; propuestas privadas primero. Una aprobación no significa resolver hilos,
aprobar MR o mergear. Demo nunca publica, ni siquiera por error de modelo/UI. Git y
checkout diferidos; sin credenciales/HOME en API/Docker ni config global modificada.

## Diseño mínimo y dependencias

Tablas/cola MR separadas de soporte/fixture/work; corte UTC propio y dedupe lógico de
mensajes como soporte. Un request Slack conserva contexto, N MRs tienen N ejecuciones
independientes/versionadas. Bloqueo/error de una no corta las otras. Repeticiones de URL
se deduplican. Revisión automática solo cuando la novedad pide review; enlaces por sí
solos no son órdenes. El modelo no decide destinos de red ni ejecuta herramientas.

Lector host `glab api --method GET` con proyectos exactos allowlist (Core40652545,
web64374983), snapshots inmutables de MR/versions/diff/discussions/CI, fuente y dependencias
solicitadas bajo límites. No lectura de secretos, URLs arbitrarias o código ejecutable.
Modelo oficial host text-only con denyall, sin fallback; referencias validadas al snapshot.
Cada etapa declara alcance parcial/truncado, evidencias nuevas y existentes; propuestas
con línea realmente cambiada y citas del código. Preguntas/rumbo/pausa y resultados
obsoletos se controlan por revisión/epoch; informe viejo no se vuelve vigente por editar.

Publicación es acción humana separada, ligada a contenido/versión exactos, revalidación
de head y estado, registro/idempotencia; sin retry ciego tras resultado ambiguo. Ejecutar
pruebas/comandos, resolver, aprobar y merge no se habilitan por esta entrega. Comprobaciones
adicionales se guardan como solicitudes humanas, no como shell del modelo.

Unidades: contratos/persistencia → captura GitLab acotada/revisor real → cola/controles
→ API/web propuestas/decisiones → pruebas/aceptación de las tres MRs. Reutilizar frontera
local, instantáneas de conversación y transporte oficial; acompañantes necesarios:
migración, fixtures TESTDB, registro de rutas, tab web, documentación y Makefile.

## Aceptación y estado inicial

Obligatorias por solicitud/AGENTS: RED→GREEN de corte/histórico/dedupe/múltiples MRs,
allowlist y URLs/ref/path, snapshot completo o limitación explícita, referencias/líneas,
no instrucciones desde datos, fallo independiente, pausa/revisión concurrente, decisiones
idempotentes/versión, demo sin publicación, HTTP protegido y UI. Checks globales y
aceptación real de una solicitud con tres MRs sin escribir en GitLab. DB tests siempre
TESTDB. Mantener recolector y soporte activos/sin tocar sus fuentes ni resultados.

Código todavía no implementado al crear este brief. Delta histórico untracked impide
risk-assess aislado: gate formal pendiente, sin improvisar Git ni declarar verified/done.
No hay index Codegraph en efren-bot; lectura dirigida, sin instalación/indexación.

## Checkpoint de implementación y hallazgos · 2026-10-25

Contratos, cinco tablas/migración0009, cola/runner host, lector glab y modelo text-only,
API protegida y sección web implementados. No implica todavía runtime desplegado.
Fuente Python/web revisada directamente; contrato de uso en `docs/mr-review.md`.

Evidencia conservada: RED inicial por módulo review.gitlab ausente → GREEN focal20
Python/18web. En la continuación, tres reproducciones RED adicionales: rangos inválidos
leían red antes de validar; aprobación pendiente sobrevivía pausa/reanudación global;
finish duplicado sobreescribía published con uncertain. Corrección: validar primero,
epoch de autorización persistido, admisión single-use y resultado final no sobreescribible.
Se añadió contexto Slack compartido a plan/análisis, validación de los tres SHA de
versión (no solo head), comprobación de dependencias leídas antes de aceptar informe,
herencia de todas las MRs del mensaje citado y referencias opacas sin redacción accidental.
Limitaciones/checks limited no se presentan como ready. No se ejecuta código remoto.

Web conserva borradores en memoria entre MRs/pestañas; si cambió revisión durante la
edición, conserva texto separado sin aplicarlo a otra versión. Focal posterior21Python
y19web PASS, typecheck/lint PASS, antes del último refuerzo de versión exacta. Checks
globales frescos en curso, evidencia `.local/review/global-checks.json` y logs adyacentes.
Advertencia heredada Starlette/httpx: visible, no cambiada incidentalmente.

Preflight runtime-observed lector glab: capturadas las tres MRs sin escrituras; !8573
mergeada, !8594/!8616 abiertas. !8616 excede presupuesto de diff y conserva limitaciones
explícitas. Modelo real, solo entrada sintética: detect=false y limpieza deny/archive
confirmada por transporte (`.local/review/model-preflight.json`). Perfil/runtime propios
con permisos700/600, sin config global ni credenciales copiadas. Principal todavía0008
al comenzar el checkpoint; TESTDB0009. Sin publicaciones GitLab ni acciones Git.

Siguiente: checks globales → migración/despliegue local propios → aceptación de la
solicitud histórica aislada con las tres MRs a través de runner.tick real → runner
permanente y navegador escritorio/móvil; preservación de originales/soporte/recolector.
Gate formal de riesgo sigue pendiente: checkout totalmente untracked, Git diferido;
no se inventa tier ni cierre verified/done. Publicación real continúa sin probar por
prohibición explícita de demo. Base/ramas/staging/commits/push no autorizados.

## Integración local y recuperación de aceptación · 2026-10-25

Principal0008→0009 migrada aditivamente. Se reconstruyeron/recrearon únicamente API y
web propios (`--no-deps`); sin servicios de terceros, Git ni cambios de configuración
global. Baseline per-row MD5 de fixture/work,3424variantes y2313capturas existentes:
ninguna modificada/borrada. El recolector añadió capturas normalmente; soporte y su
corte/runner permanecieron activos. Receipts `preservation-before.json` y
`preservation-after.json` bajo `.local/review/`.

Primer recorrido real `runner.tick`, doce pasos y writer explícitamente prohibido:
!8573 y !8616 fallaron `review_context_budget`; !8594 produjo informe parcial válido.
Inputs serializados242827/279839 caracteres: el presupuesto65k de archivos no incluía
overhead/metadatos/contexto. Artefactos originales preservados en `attempt-1/`.
Corrección mínima: compactar rangos añadidos sin perder líneas, reducir duplicados y
limitar lecturas por JSON total230k con reserva/limitaciones visibles, no aumentar el
acceso ni el modelo. Repetición explícita de las dos MRs fallidas con revisión nueva,
archivando snapshot/plan/error. Ambas produjeron informe parcial válido (`attempt-2/`).
No retry automático del modelo ni fallback. Informe previo de !8594 revalidado con el
validador reforzado; no se genera de nuevo sin necesidad.

Refuerzos de revisión directa: `addressed_in_code` requiere evidencia del head actual,
no solo base o un comentario; demo vinculada a su source_scope exacto; filtro de paths
también sobre cuerpos de diff antes de persistir/pasarlos al modelo. RED sintético de
`.env`→GREEN, sin secreto real ni cambio del input de las tres demos (todas sus rutas
son permitidas, incluyendo docs/errors.rst). El test de presupuesto largo sufrió
timeout120s: halló costo cuadrático heredado del saneador de correo sin `@`. Guarda
semánticamente equivalente antes del regex recuperó el focal en0.18s; regresión global
de soporte incluida. Se conservan timeout/fallos, no se cuentan como PASS.

Resultado observado: tres MRs, tres informes de ocho dimensiones, **todos parciales**;
!8573 mergeada y !8594/!8616 abiertas,0comentarios nuevos suficientemente sustentados.
No convertir esto en «sin defectos» ni «revisión completa»: faltan rangos, dependencias,
contratos y verificaciones externas explícitas en cada informe. Costo/negocio/call paths
y comentarios ya corregidos se contrastan con citas; métricas ajenas no se certifican.
La profundidad exhaustiva de composición entre MRs sigue limitada por los presupuestos.
Solicitud `f86792ab-86c8-48bb-a009-062b1de4803d`, corte propio inalterado
`2026-10-26T05:03:36.891641Z`, scope autorizado; no barrido histórico. Receipt
`demo-acceptance-latest.json` y denegación real HTTP409 `http-demo-deny.json`.

Últimos checks obligatorios: `make check`, `make test`,
`node --test tools/slack-collection/failure.test.mjs`, PASS con inputs cubiertos sin
mutación en `delivery-checks.json`, logs check/test/node-delivery.540Python (415unit,
125integration en TESTDB),19web,1Node. Fuente/config/locks/AGENTS cubiertos por hash;
docs de estado no alteran contratos ejecutables. Ruff/typecheck/build PASS. Advertencia
Starlette/httpx heredada visible. No se ejecutó código de ninguna MR.

Aceptación visual real: tres MRs juntas, fases y alcance visibles, soporte/recolector
disponibles. Borrador conservado al cambiar pestaña/MR y limpiado sin enviarlo; captura
`.openchamber/screenshots/mr-review-draft-retained-2026-10-26T05-06-04-068.jpg`.
Overflow móvil de paths reproducido y corregido; captura posterior
`.openchamber/screenshots/mr-review-mobile-paths-fixed-2026-10-26T05-17-30-254.jpg`.
Edición/descartes y publicaciones siguen probados solo con dobles; no se inventa una
propuesta para probar una publicación real. Cero publicaciones/admisiones en la demo.

Estado: incremento funcional desplegado con aceptación de informes **parcial**;
no cierre verified/done. Riesgo determinístico/revisión independiente correspondiente
siguen pendientes por delta no aislable y Git diferido. No sustituirlo por una revisión
subjetiva ni improvisar staging/ramas. Métricas ODD: una cobertura parcial de tiempos de
ejecutores en los receipts; sin estimación de duración total ni métricas de workers.

### Receipt final de ejecución local

`accept-final.py` revalidó los tres informes con el validador actual y confirmó sus
refs contra metadata GitLab fresca. El último filtro de archivos no cambia sus inputs:
todas sus rutas son permitidas. Pregunta real de !8594 contestada con modelo oficial,
sin lecturas nuevas ni cambio de revisión; sesión limpiada por transporte. Cero entradas
publish y cero llamadas de writer. `deployed-acceptance.json` conserva cada resultado.

Runner MR permanente84857 activo, corte inalterado, automático solo para novedades.
Receipts `runtime-final.json`: API sirve las tres demos partial (revisiones2/1/2),
HTTP409 demo_read_only, heartbeats frescos de los tres controles, ningún control pausado,
API sin mounts.539→540Python tras regresión de diff sensible;19web/1Node siguen PASS.
Fuentes/tests/config/locks no cambiaron después de los checks delivery; solo documentación
de aceptación y scripts propios ignorados. Datos fixture/work y3424variantes originales
intactos; capturas pasaron2313→2456 por actividad normal, sin modificar las originales.

Pendiente de entrega formal: aislamiento autorizado del delta/riesgo y revisión que
corresponda, más cobertura técnica exhaustiva hoy limitada en los informes. No se amplía
automáticamente el histórico ni se ejecutan comprobaciones remotas para cerrar faltantes.
El usuario puede ver, preguntar o reorientar cada MR en la sección ya desplegada.

## Ajuste de UX solicitado · 2026-10-25

Corrección del usuario: «hace falta agregar diseño para distinción de código, marcaje.
Imagínate el Notion con un bloque para sección de código» y «siento que está muy saturada».
Se invalida la aceptación visual de densidad, no los informes/evidencia ni sus límites.
Cambio acotado a web MR: resumen primero; navegación Resumen/Análisis/Conversación;
limitaciones/rutas/antecedentes bajo demanda, sin ocultar que la revisión es parcial.
Código inline y bloques con fuente/lenguaje, monospace, marcado y copia exacta; texto
Markdown seguro sin HTML ni recursos remotos. No nuevos accesos, modelos ni dependencias,
cambios de datos/contrato/runner, permisos o acciones. Se conserva texto original al
editar/copiar/publicar y los borradores al navegar. Solo se redespliega web propia.

Dirección: documento de revisión, no dashboard. Paleta existente: tinta#192f4b,
papel#ffffff, fondo#f3f6fb, azul#315cad, texto secundario#63738a y límite#dce4ef;
advertencias/diff reutilizan tokens semánticos. Avenir Next para lectura, SFMono/Menlo
para código. Firma: fragmento de evidencia con cabecera de archivo y diff marcado,
no otra tarjeta de estadísticas. Menos avisos repetidos y ningún éxito inferido del
formato. Tests RED→GREEN de formato, colapso/navegación y controles, checks globales
por proyecto y aceptación visual real sin repetir análisis ni modificar las MRs.

### Resultado del ajuste visual

Web redesplegada de forma aislada (`build web`, `up --no-deps web`). Sin cambios en
API/DB/runner, credenciales, contratos ni dependencias. `ReviewText.tsx` distingue
prosa, listas, negritas, código inline y bloques cercados sin HTML/enlaces/imágenes
activos. `CodeBlock` agrega archivo/lenguaje, tipografía mono, marcado léxico básico,
diff +/- y copia literal sin números de línea inventados. La copia/edición/publicación
del comentario sigue usando el cuerpo original, no el HTML ni el texto transformado.

Resumen abre por defecto con conclusión y faltantes plegados; el carácter parcial
permanece visible. Análisis agrupa dimensiones/evidencia/antecedentes/plan. Conversación
separa preguntas del historial de decisiones y evita repetir todo el informe en la
pantalla inicial. Los borradores permanecen al navegar vistas/MRs/pestañas. Se reutilizan
los hooks existentes; no se crea una nueva fuente de estado ni se reinician revisiones.

RED de renderer ausente → GREEN. Un fallo de regresión al renombrar visualmente una
tarjeta se corrigió con nombre accesible explícito de MR/título/estado. Checks finales
obligatorios `make check`, `make test`, Node failure.test.mjs PASS con hash de inputs
cubiertos idéntico antes/después (`.local/review/ux-checks.json`, ux-check/test/node.log).
540Python en entornos de pruebas separados,24web y1Node; typecheck/build PASS. Pruebas
incluyen contenido HTML inerte, marcaje/copia, texto original al editar, evidencia por
archivo, avisos plegados, borradores entre vistas y guardias de publicación de demo.

Aceptación visual real escritorio/móvil, sin enviar mensajes ni copiar datos reales al
clipboard: `.openchamber/screenshots/mr-ux-summary-2026-10-26T05-49-21-052.jpg`,
`mr-ux-code-blocks-2026-10-26T05-50-18-117.jpg`,
`mr-ux-code-mobile-2026-10-26T05-50-37-482.jpg` y
`mr-ux-chat-draft-retained-2026-10-26T05-53-13-640.jpg` bajo el mismo directorio.
El borrador de prueba se limpió sin enviar. Snapshot API de las tres MRs idéntico al
input de sus informes, revisiones1/2/2 y estado partial intactos; runner disponible,
automático activo (`.local/review/ux-data-acceptance.json`). No nuevos accesos GitLab,
generaciones de modelo, publicaciones ni operaciones Git por este cambio visual.

La objeción de saturación se atendió en la presentación; cobertura técnica parcial y
riesgo formal/delta histórico pendientes siguen siendo los mismos, no se dan por cerrados.
