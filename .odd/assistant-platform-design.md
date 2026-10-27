# Diseño de la plataforma del asistente

## Objective
Bajar a documentos Markdown el diseño del ecosistema de Efren Bot: familias de trabajo, memoria, ejecuciones paralelas, aprobaciones, integraciones y registro de reglas/skills por rol, como base revisable antes de implementar.

## Problem
La demo implementada no cubre la plataforma descrita por el usuario. Las decisiones de conversación necesitan contratos compartidos y límites explícitos para que los workers no pierdan contexto, mezclen tareas, concedan permisos mediante skills o ejecuten efectos externos sin aprobación.

## Scope
- In scope: siete documentos de diseño propuesto, enlazados y coherentes; matriz de capacidades actuales/propuestas; registro documental DRAFT de roles/skills; contratos de trabajo, orquestación, memoria, integraciones y plan de incrementos; navegación mínima desde README raíz.
- Out of scope: backend, web, esquema/migraciones/BD, embeddings, conectores reales, automatizaciones/schedules, perfiles o SKILL.md ejecutables, instalaciones de agentes/n8n, configuración global, credenciales, lecturas externas adicionales, escrituras Notion/Slack/GitLab, ramas/worktrees/commits/push.

## Authorized scope
Usuario solicita «empezar armando una estructura de md con todo esto bajarlo correctamente diseñarlo bien», incluyendo reglas y skills coordinadas para los workers. Archivos autorizados: docs/assistant-platform/{README,work-model,orchestration,memory,policies-and-skills,integrations,implementation-plan}.md; README.md raíz únicamente un enlace de navegación rotulado diseño futuro; este documento y su espejo Engram. No cambiar AGENTS.md, docs/contract.md, docs/architecture.md ni livingdocs históricos. Los permisos actuales del proyecto siguen vigentes; la visión futura no los amplía.

## TDD
Not applicable para runtime: entrega exclusivamente documental. Verificación estática obligatoria de enlaces/anchors, contenido, estados DRAFT/propuesto, consistencia de permisos/identidades y preservación de archivos ajenos. No ejecutar pruebas DB, npm, Docker o comandos de proyecto que puedan escribir.

## Delivery
Checkout actual main, trabajo previo no aislado. No autorización Git/topología/entrega. Baseline SHA256 de 95 archivos relevantes en scratch efren-platform-docs-jj23fhvf/baseline.json; no sustituye aislamiento exacto de feature para riesgo formal. Riesgo formal, eventual scraft-judge y cierre global permanecen pendientes; no declarar implementación o plataforma verificada por documentación.

## Acceptance criteria
- Índice enlazado y siete documentos sustantivos, sin plantillas vacías. Diferenciar evidencia actual, propuesta y pendientes; no transformar acceso de chat en integración de producto.
- Familias soporte, desarrollo, investigación/discovery, análisis de flujos, revisión y monitoreo/planificación. Separar expediente, tarea externa, job, intento, aprobación, artefacto y resultado; Notion administrativo, GitLab técnico, Slack conversación, Efren Bot coordinación.
- Memoria canónica versionada con motivos/evidencias/auditoría; índice vectorial derivado/reconstruible y lecciones revisadas. Extensión pgvector no equivale a embeddings existentes; modelo/dimensión/retención siguen pendientes.
- Ejecuciones paralelas acotadas, aisladas por trabajo/repo autorizado, despacho explícito, checkpoints, espera humana sin ocupar capacidad, leases/fencing y reconciliación/idempotencia sin prometer exactly-once externo. El outbox fixture actual no se reinterpreta como ejecutor de código.
- Reglas, roles, skills y capacidades autorizadas separados; catálogo DRAFT con contratos concretos para soporte/desarrollo/revisión/investigación, versionado, revisión, resolución por job y revocación. Skill o contenido recuperado no concede permisos; ampliaciones requieren aprobación; ninguna lección activa reglas automáticamente.
- Perfil futuro prepara fixes y exige aprobar publicaciones; tarea Notion existente se reutiliza, clave KNF real antes de rama solo con autorizaciones. Assignee/In Progress no dispara ejecución. Estado complete/Done de Notion no prueba entrega técnica; campos deprecados no mandan.
- Integraciones incluyen límites observados de Slack/Notion/glab y frontera host/producto/secretos. n8n solo candidato retirado; GitLab observado solo metadatos, políticas de repos pendientes. No copiar cuerpos corporativos ni tokens a los documentos.
- Plan de incrementos con dependencias, permisos y criterios/checks preclasificados. Este incremento no autoriza los siguientes.
- Enlaces locales válidos, referencias entre contratos coherentes, hashes ajenos preservados. Fuente/contrato/arquitectura, implementaciones y configuración sin modificaciones.

## Tasks
- [x] Mapear documentación y evitar duplicados — files: AGENTS, README, docs y .odd existentes — depends on: none — route: delegated direct (mapping: 4+ fuentes) — evidence: siete documentos recomendados; no livingdoc de plataforma previo; búsqueda Engram exacta sin resultados. No escrituras ni fallos; grep histórico truncado no acredita lectura completa de todos los planes.
- [x] Escribir contratos y registro documental — files: siete docs autorizados y enlace README raíz — depends on: mapeo — route: delegated direct (writer: múltiples documentos no triviales) — evidence: siete documentos DRAFT, 835 líneas, cuatro procedimientos concretos por rol y una línea de navegación raíz. Tres PATCH aceptados; dos validaciones estáticas del writer PASS, sin fallos. La coherencia de contratos justifica superar heurística de 400 líneas en esta unidad documental, sin dividir artificialmente ni crear implementaciones.
- [x] Comprobar documentación y revisar coherencia — files: documentos autorizados y baseline de preservación — depends on: escritura — route: delegated direct (revisión independiente) + direct inline (checks de enlaces/hashes) — evidence: padre PASS en 33 enlaces de docs + enlace raíz, 5 anchors, siete encabezados DRAFT; 94 archivos protegidos idénticos y README solo nueva línea. Revisión semántica independiente approve-as-draft, sin correcciones requeridas ni fallos; no sustituye riesgo formal.
- [x] Registrar resultados y límites — files: este livingdoc y espejo — depends on: comprobaciones — route: direct inline — evidence: comprobaciones documentales obligatorias PASS, sin fallos recuperados o pendientes documentales. Runtime no aplica; riesgo exact-delta, eventual judge y Git continúan diferidos. Sin cierre global ni métrica ODD de cierre.
- [x] Entregar índice para comentarios del usuario — files: índice y enlaces — depends on: registro — route: direct inline — evidence: docs/assistant-platform/README.md abierto en panel de archivos; siete documentos disponibles como DRAFT. Esperar comentarios del usuario; implementación posterior requiere nueva autorización.

## Findings & adjustments
- Reset de alcance previo preservado: la plataforma no es solo una bandeja Slack; debe asistir al equipo, preparar fixes/MRs y seguir resultados. Documentación nueva separada de la demo sintética y del puente histórico.
- El usuario añade reglas/skills específicas por rol como componente del diseño. En este corte se documenta un registro DRAFT, no se instalan skills ni agentes activos.
- Accesos de sesión observados: Slack lectura, Notion esquema/muestra y glab identidad/metadatos de tres proyectos. No equivalen a permisos de código/publicación ni a conectores del producto. No se repiten consultas externas para redactar.
- Reglas vigentes mantienen producto local y límites de fuentes. Integraciones reales de la visión necesitan alcance y revisión explícitos posteriores; no editar AGENTS para sortearlas.
- Baseline previo PASS: directorio docs/assistant-platform y este livingdoc ausentes; 95 archivos relevantes hasheados sin leer secretos. Comprobación obligatoria por criterio de preservación.
- Writer informa dos validadores documentales obligatorios PASS (833 líneas iniciales, 835 tras precisar claim exclusivo de acción/aprobación en transacción corta); readback completo y cuatro procedimientos concretos. Sin fallos ni PATCH rechazados. No modificó ODD/espejo ni ejecutó runtime.
- Check obligatorio del padre mediante Python read-only PASS: siete docs regulares, DRAFT fechado, 33 enlaces locales en docs y navegación raíz adicional, 5 anchors, una URL externa solo inventariada; 94 hashes ajenos idénticos, README reconstruido al retirar la única línea nueva coincide con baseline; ningún archivo nuevo inesperado en árboles monitorizados. Reporte scratch efren-platform-docs-jj23fhvf/checks.json. No comprobaciones runtime, pues no aplican al cambio documental.
- Revisor independiente leyó reglas, livingdoc, los siete documentos, README raíz y contratos canónicos. Veredicto approve-as-draft, sin hallazgos que requieran corrección ni ampliaciones opcionales necesarias; sin fallos/reintentos. Esta revisión no es scraft-judge ni evaluación formal del delta. No se ejecutaron pruebas, consultas externas o cambios por el revisor.
- Entrega documental acotada: no cambios de código, DB, configuración, agentes/skills ejecutables, servicios o recursos externos. Inicio del padre 2026-10-24T06:04:45Z conservado para eventual cierre; evaluación formal y Git siguen pendientes por checkout histórico no aislado, sin repetir una decisión ya diferida.

## Next step
Esperar comentarios del usuario sobre los siete DRAFT. Después delimitar y autorizar el primer incremento; no instalar ni ejecutar workers, skills, conectores, embeddings o automatizaciones por la mera aprobación de este diseño.
