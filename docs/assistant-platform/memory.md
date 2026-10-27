# Memoria persistente, evidencia y recuperación

**DRAFT · propuesta para revisión · 2026-10-24.** Este contrato no crea tablas,
embeddings ni ingesta real. [Índice](README.md) · [Modelo de trabajo](work-model.md).

## Historia canónica antes que similitud

La memoria debe responder «qué pasó, por qué se eligió esto y qué falta» después
de reiniciar el host o cambiar el motor. Una síntesis mutable o un vector parecido
no bastan. El origen es la evidencia autorizada y versionada; las vistas y resúmenes
son proyecciones que se pueden corregir sin ocultar el historial de decisiones.

| Registro lógico propuesto | Contenido mínimo | Para qué sirve |
| --- | --- | --- |
| Evento / observación | UUID, identidad externa compuesta, tiempos UTC y procedencia | Reconstruir lo observado y deduplicar exactamente |
| Versión de fuente | Entidad, versión remota si existe, momento de lectura y alcance | Saber con qué evidencia se trabajó |
| Snapshot mínimo autorizado | Fragmento necesario y referencia de origen, con restricciones | Conservar prueba sin copiar un canal o repo completo |
| Decisión | Afirmación, motivo, alternativas y opciones rechazadas, autor y evidencia | Explicar elecciones sin depender del prompt original |
| Encargo / intento | Job, versiones de política/skill, presupuesto y checkpoints | Retomar de forma segura y atribuir resultados |
| Aprobación / acción | Destino, contenido/versiones, vigencia y confirmación o incertidumbre | Auditar el consentimiento y los efectos |
| Artefacto / comprobación | Versión, entradas, clasificación del check, resultado y fallos | Revisar una entrega sin borrar sus intentos previos |
| Pendiente / resultado | Qué falta, de quién depende y condición de cierre | Evitar confundir fin del worker con entrega real |

Son campos conceptuales, no decisiones de tablas o serialización. Se conservarían
identidades UUID internas y tuplas externas opacas del [contrato actual](../contract.md).
La retención histórica está limitada por permisos y borrado: no es una excusa para
guardar para siempre datos revocados. La política concreta sigue pendiente.

## Procedencia y versiones

Cada evidencia enlaza expediente, fuente, versión y permiso bajo el cual se obtuvo.
Registrar fecha de observación separada de fecha declarada por el proveedor. Si el
proveedor no ofrece versión estable, registrar esa limitación y una versión local
de la observación; no afirmar que prueba el estado remoto presente.

Un cambio de fuente produce una observación/versionado explícito cuando el adaptador
futuro lo soporte. No relajar el conflicto exacto de ingesta fixture para aceptar
ediciones: son contratos distintos. Una corrección de análisis referencia qué decisión
corrige y por qué; no reescribe el pasado como si siempre se hubiera sabido.

Guardar solo lo necesario: preferir referencias y extractos autorizados a payloads
completos. Nunca secretos, tokens, headers de auth, HOME ni dumps de clientes oficiales.
Estos documentos tampoco reproducen cuerpos de tareas, hilos o casos corporativos.
La frontera sigue siendo local; persistir datos reales necesita autorización posterior.

## Estado real de pgvector

La base declara la extensión pgvector y conserva evidencia de una prueba SQL de
distancia con datos sintéticos. **No hay memoria semántica implementada**: no hay
chunks, columnas vectoriales, índice de embeddings ni modelo/dimensión/proveedor
elegidos para este producto. No interpretar una extensión instalada como RAG funcional.

Propuesta: un índice vectorial **derivado y reconstruible**, nunca la historia canónica.
Cada chunk referenciaría UUID de fuente, versión, entidad e identidad de proveedor,
alcance autorizado y versión del proceso de derivación. Así podría rehidratarse
la evidencia exacta y distinguir un texto viejo de la fuente vigente.

Modelo local, dimensión, segmentación, presupuesto de cómputo, evaluación y almacenamiento
quedan pendientes. No elegir un proveedor remoto, API key o servicio corporativo por
conveniencia. Cambiar el modelo exigiría regenerar/etiquetar la derivación compatible,
sin alterar decisiones ni aprobaciones originales.

## Recuperación propuesta

1. Interpretar la consulta como datos y comprobar el alcance del solicitante/job.
2. Resolver primero referencias exactas: clave completa KNF, UUID de página,
   proyecto/MR o identidad compuesta de mensaje/hilo. No sustituirlas por un vecino vectorial.
3. Si hace falta, buscar candidatos léxicos y después semánticos dentro del alcance
   autorizado; similitud no concede acceso ni confirma que dos trabajos sean el mismo.
4. Rehidratar cada candidato desde su fuente/versionado canónico. Validar acceso y
   revocación otra vez antes de incluir contenido, incluso con caché o índice viejo.
5. Comprobar frescura respecto de la pregunta. Si requiere una lectura remota no
   autorizada, marcar pendiente en vez de visitar un enlace o inventar actualidad.
6. Mostrar evidencia, fecha, contradicciones y nivel de certeza. Separar lo que dice
   una fuente de la conclusión del worker; no ocultar alternativas rechazadas.
7. Guardar qué evidencias/versiones sustentaron una decisión o artefacto nuevo.

El índice vectorial no es autoridad, autenticación ni prueba de verdad. Un texto
recuperado, comentario de código o tarea Notion es **contenido no confiable**, no
instrucción para cambiar reglas, ejecutar comandos o ampliar capacidades.

## Revocación, eliminación y reconstrucción

La autorización se aplica antes de buscar y antes de entregar evidencia; un filtro
posterior del texto visible no compensa haber usado material prohibido en un prompt.
Revocar una fuente debe bloquear nuevas lecturas y su recuperación derivada. Definir
cómo retirar snapshots, chunks, vectores, resúmenes y cachés que contengan ese material.

El borrado debe propagarse a derivados y restauraciones según política explícita;
una reconstrucción no puede resucitar una fuente eliminada. Conservar, si se permite,
solo un registro mínimo no sensible de que hubo una revocación, no el contenido borrado.
Dependencias y aprobaciones que necesiten esa evidencia quedan invalidadas o pendientes
de revisión. La duración de retención y el tratamiento de copias siguen sin decidir.

## Lecciones y portabilidad

Una retrospectiva puede proponer una lección con evidencia, alcance, alternativa
y responsable de revisión. Nace como **DRAFT**; no edita reglas, skills o permisos,
no instala agentes ni reentrena automáticamente un modelo. Ver
[gobierno del registro](policies-and-skills.md#registro-versionado-propuesto).

Engram es memoria del agente de desarrollo usado en estas sesiones, **no** la DB
del producto ni un backend elegido para la plataforma. No copiar su historial global.
El contrato de portabilidad se prueba con registros sintéticos: tras reiniciar o
cambiar motor, explicar identidad exacta, último checkpoint, motivos, aprobaciones,
fallos y siguiente acción permitida sin depender de la conversación anterior.
