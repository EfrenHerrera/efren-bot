# Modelo de trabajo y responsabilidades

**DRAFT · propuesta para revisión · 2026-10-24.** No modifica el
[contrato implementado](../contract.md). Volver al [índice](README.md).

## Familias de trabajo

| Familia | Entrada admisible futura | Resultado revisable | Límite |
| --- | --- | --- | --- |
| Soporte | Caso o mención dentro del alcance aprobado | Diagnóstico, evidencia y respuesta propuesta | No corregir datos ni cerrar el caso por inferencia. |
| Desarrollo: bug, fix o feature | Tarea explícitamente encargada | Cambio aislado, checks y propuesta de MR | Permiso de código no equivale a permiso de publicación. |
| Investigación / discovery | Pregunta, hipótesis o tarea | Hallazgos, alternativas y decisión pendiente | Distinguir hechos, inferencias y desconocidos. |
| Análisis de flujo | Pregunta sobre recorrido o dependencia | Mapa con evidencia y puntos de fallo | No ejecutar el flujo real para documentarlo sin permiso. |
| Revisión de cambio / MR | Diff o MR seleccionado | Hallazgos accionables y estado de preparación | No resolver discusiones ni modificar por defecto. |
| Monitoreo | Regla estable aprobada y fuentes acotadas | Candidatos, alertas o cambios observados | No desplegar un agente LLM permanente por canal. |
| Planificación / documentación | Objetivo o material seleccionado | Plan, contrato, síntesis o retrospectiva | Redactar no autoriza ejecutar el plan. |

Un expediente puede reunir familias relacionadas mediante vínculos explícitos.
Una investigación que descubre un bug propone un trabajo de desarrollo; no cambia
su propio alcance ni hereda permisos para implementarlo.

## Identidades separadas

Campos lógicos propuestos, **no esquema SQL ni migración acordada**:

| Entidad | Identidad | Responsabilidad |
| --- | --- | --- |
| Expediente de trabajo | `work_id`, UUID interno | Objetivo, propietario, alcance y seguimiento durable |
| Referencia de fuente | UUID interno + identidad compuesta del proveedor | Ubicar la entidad externa y su versión sin confundir tenants |
| Tarea Notion | UUID de página externo, conservado como referencia | Registro administrativo enlazado, no PK del expediente |
| Clave de negocio | Clave completa `KNF-…` leída de Notion | Nombre humano/relación administrativa; no reemplaza UUID de página |
| Job | `job_id`, UUID interno | Encargo acotado para un rol y una versión de entrada |
| Intento | `attempt_id`, UUID interno | Ejecución concreta, lease, resultado y consumo del job |
| Aprobación | `approval_id`, UUID interno | Consentimiento para una acción y contenido exactos |
| Artefacto | `artifact_id`, UUID interno + versión | Informe, diff o borrador con procedencia |
| Resultado | `result_id`, UUID interno | Qué consiguió el job y qué quedó pendiente |

Un expediente puede tener varios jobs; un job, varios intentos; un resultado puede
referenciar varios artefactos. Una aprobación no es un resultado ni un permiso global.
Un mismo mensaje puede originar eventos distintos sin ser una nueva solicitud.
Preservar entrega, evento, mensaje e hilo como conceptos distintos del contrato actual.
En DB/dominio futuros se mantendrían UUID nativos y fechas aware UTC; JSON usaría strings.

Relacionar por identidades verificadas: proveedor/espacio/entidad, página, proyecto/MR
y clave completa. Una similitud textual solo propone un vínculo para revisión;
no fusiona expedientes, mensajes ni tareas y no suplanta una clave ausente.

## Dueños de la información

- **Notion:** asignación y seguimiento administrativo de la tarea externa.
- **GitLab:** diff, MR, pipeline y discusiones técnicas cuando estén autorizados.
- **Slack:** conversación y compromisos expresados en fuentes admitidas.
- **Efren Bot:** encargo, checkpoints, evidencias, decisiones y auditoría de acciones.

La plataforma guardaría referencias y observaciones versionadas, no una segunda
autoridad que sobrescriba silenciosamente el estado de los otros sistemas.

## Tres ciclos de estado, sin equivalencia automática

| Ciclo propuesto | Estados | Regla de transición |
| --- | --- | --- |
| Expediente | `candidate`, `accepted`, `active`, `waiting`, `delivered`, `closed`, `cancelled` | Aceptación/despacho explícitos; cierre con decisión y evidencia. |
| Job | `queued`, `running`, `waiting_human`, `waiting_external`, `succeeded`, `failed`, `cancelled` | El coordinador aplica resultados, espera y cancelación con historial. |
| Fuente Notion | Opciones observadas de su propiedad Status | Se registra el valor remoto; no se convierte automáticamente en estado interno. |

Un job terminado (`succeeded`, informalmente «job done») no cierra una tarea ni un
caso. `delivered` registra qué se entregó, a quién y con qué pendientes; `closed`
requiere criterio de cierre y actor autorizado. Puede haber entrega parcial.
Un agradecimiento, un merge o el valor `Done` remoto no demuestran cierre real.
Una modificación posterior puede requerir un nuevo job o reapertura explícita,
conservando el resultado anterior, no borrándolo.

## Recorrido: tarea Notion existente a entrega técnica

1. La persona crea o selecciona una tarea y encarga explícitamente investigar o
   implementar. Ser Assignee o ver `In Progress` no dispara un job sin regla estable aprobada.
2. Resolver el UUID de página y la clave completa existente. Reutilizar la tarea;
   no crear otra por no encontrarla con búsqueda semántica. Si falta certeza, preguntar.
3. Aceptar el expediente, fijar objetivo, repositorio/ref y alcance permitidos,
   criterios, política, skill y presupuesto. Una URL no concede acceso al repo.
4. Con permiso de Git/topología, preparar entorno aislado y rama según la política
   del repositorio usando la clave real; nunca inventar un número KNF.
5. El worker investiga y prepara el cambio. Clasifica los checks antes de ejecutarlos,
   conserva fallos y reintentos, y registra diff, base y resultados reproducibles.
6. Presentar propuesta de MR: destino, rama/base, contenido y limitaciones. Todavía
   no publicar ni hacer push; esos efectos necesitan capacidades y aprobaciones propias.
7. La persona aprueba las acciones exactas. El ejecutor revalida vigencia, contenido,
   destino y permisos antes de publicar; registra identificadores reales devueltos.
8. Comentarios de MR generan evidencia y, si se encarga, otro job acotado. No resolver
   discusiones, cambiar de alcance ni publicar una respuesta automáticamente.
9. Registrar entrega técnica, validación y pendientes; reconciliar Notion solo mediante
   una actualización expresamente autorizada. El cierre real se confirma por separado.

## Recorridos paralelos: soporte y solicitud nueva

**Soporte:** candidato autorizado → aceptación → job de triage → evidencia mínima →
diagnóstico y borrador → espera de aprobación → eventual envío aprobado → seguimiento.
Si requiere desarrollo, vincular un expediente nuevo o existente y pedir el alcance
correspondiente. Resolver soporte no otorga permiso para SQL de escritura ni fixes.

**Solicitud nueva en Slack:** candidato → confirmar intención y límites → aprobación
acotada para crear registro Notion → ejecución/reconciliación → UUID y clave reales →
aceptar desarrollo y permisos de repositorio/rama → recorrido técnico anterior.
La aprobación de crear la tarea no incluye preparar rama, push o MR.

Ambos recorridos pueden avanzar mientras un tercer job espera respuesta. La espera
libera capacidad y conserva un checkpoint; no se comparte checkout ni conversación.
Ver [orquestación](orchestration.md), [memoria](memory.md) y
[aprobaciones](policies-and-skills.md#aprobaciones-y-revocación).
