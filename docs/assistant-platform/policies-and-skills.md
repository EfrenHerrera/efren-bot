# Reglas, roles, skills y capacidades

**DRAFT · propuesta para revisión · 2026-10-24.** Catálogo documental, no archivos
`SKILL.md` instalables ni configuración activa. [Índice](README.md).

## Separación de responsabilidades

| Concepto | Responde | No significa |
| --- | --- | --- |
| Política | Qué se permite/prohíbe en proyecto, repositorio y job | Un consejo que el modelo puede omitir |
| Rol | Qué responsabilidad y tipo de salida tiene el worker | Identidad con acceso a todas las herramientas |
| Skill | Cómo realizar un procedimiento y dónde detenerse | Permiso de ejecutar sus pasos |
| Capacidad real | Qué operación acotada está disponible y aplicada por el ejecutor | Cualquier comando equivalente vía shell |
| Aprobación | Qué acción concreta consiente una persona, con vigencia | Autorización permanente del rol o del modelo |

Los contratos no dependen de una marca de modelo. Un adaptador traduce operaciones
aprobadas a una interfaz oficial revisada, sin heredar herramientas globales,
credenciales o permisos de la sesión anfitriona. Un prompt que diga «solo lectura»
no sustituye la denegación técnica de efectos no concedidos.

## Roles propuestos

| Rol | Responsabilidad | Salida normal | Frontera |
| --- | --- | --- | --- |
| Soporte | Entender un caso y preparar decisión/respuesta | Diagnóstico, evidencia, preguntas y escalación | No cambiar datos ni asumir cierre. |
| Desarrollo | Preparar un cambio en repo y alcance aprobados | Diff, checks e informe para MR | No push/publicación por tener shell de edición. |
| Revisión | Evaluar un cambio concreto con reglas del repo | Hallazgos y preparación de entrega | No modificar ni resolver discusiones por defecto. |
| Investigación | Explicar pregunta, flujo o alternativas | Informe trazable y desconocidos | No ampliar fuentes ni convertir hipótesis en hechos. |

Monitoreo y planificación pertenecen al coordinador/colectores con reglas aprobadas;
pueden despachar alguno de estos roles cuando haga falta. No requieren un LLM
dedicado por canal ni autorizan subdelegación desde un worker.

## Registro versionado propuesto

Cada política, perfil de rol y skill tendría ID estable y versión inmutable. Registrar:
propósito, dueño/revisor, estado, alcance/recursos admitidos, entradas, salidas,
procedimiento, paradas/escalación, checks, capacidades necesarias, presupuesto,
compatibilidad de contratos y referencia `supersedes` cuando corresponda.

Estados del registro: `draft` → `reviewed` → `active`; también `revoked` y `retired`.
Los cuatro contratos de abajo están **draft**, versión propuesta `0.1`, revisión y
activación pendientes del propietario del producto y del repositorio afectado.
Una nueva versión no modifica retrospectivamente los jobs existentes ni se activa sola.
Una propuesta generada por IA o una lección solo puede crear un borrador revisable.

| ID de skill propuesto | Propósito / rol | Compatibilidad | Recursos y presupuesto |
| --- | --- | --- | --- |
| `support.triage-case` | Diagnosticar sin efectos / soporte | Modelo de expediente y evidencia de este diseño | Solo caso/fuentes admitidos en el job; techo explícito antes del despacho |
| `development.prepare-change` | Preparar diff y evidencia / desarrollo | Identidad Notion, repo y checkpoints aprobados | Repo/ref/paths y comandos revisados; techo explícito |
| `review.assess-change` | Revisar un diff exacto / revisión | Versiones de diff, base y política fijadas | Diff y dependencias admitidas; techo explícito |
| `research.explain-flow` | Explicar flujo con procedencia / investigación | Fuentes y versiones recuperables | Corpus/entidades permitidos; techo explícito |

No hay activación si faltan dueño, revisión, allowlist o presupuesto. `supersedes`
queda vacío en estos borradores iniciales; cambios posteriores requieren explicar
compatibilidad, migración de jobs en espera y motivo de retirada/revocación.

Los siguientes **IDs de capacidad son lógicos y propuestos**, no nombres de tools
disponibles: `evidence.read-scoped`, `artifact.prepare-local`, `repository.read-scoped`,
`repository.edit-scoped`, `checks.run-approved`. Crear registro Notion, rama, push,
MR o mensaje necesitaría capacidades de efectos independientes, no incluidas por
defecto en estas skills. No se habilita SQL real ni shell arbitraria bajo otro nombre.

## Skill: triage de un caso

`support.triage-case@0.1` · **DRAFT** · dueño/revisor: pendientes de designación.

**Entradas:** `work_id`, caso seleccionado, pregunta, evidencias/versiones autorizadas,
límites de consulta, política y presupuesto del job. **Salidas:** diagnóstico con
certeza explícita, fuentes, preguntas restantes, borrador de respuesta y escalación.
**Capacidades necesarias:** `evidence.read-scoped`, `artifact.prepare-local`.

1. Confirmar identidad del caso y objetivo; separar síntoma, impacto y petición.
2. Revisar evidencia ya autorizada y su frescura; no seguir links, buscar globalmente
   ni consultar DB por el mero hecho de que el texto mencione un cliente.
3. Construir hipótesis y contrastarlas con evidencia; si falta una lectura, proponer
   la consulta mínima y pedir alcance antes de ejecutarla.
4. Distinguir diagnóstico técnico, decisión de soporte y quién puede actuar; redactar
   una respuesta que no prometa cambios, tiempos o resolución no confirmados.
5. Registrar motivos y pendientes; devolver borrador al coordinador para revisión.

**Parar/escalar:** identidad ambigua, dato sensible no permitido, necesidad de escritura
o fuente fuera del alcance. **Checks:** correspondencia caso/evidencia, afirmaciones
respaldadas, sin secretos, siguiente responsable y pendientes claros; clasificar
antes de ejecutarlos. No publicar, cambiar datos ni cerrar el caso.

## Skill: preparar un cambio de repositorio

`development.prepare-change@0.1` · **DRAFT** · dueño/revisor: pendientes de designación.

**Entradas:** encargo explícito, UUID de página y clave Notion reales, repo/ref/paths,
criterios, topología y permisos Git concedidos por separado, reglas, presupuesto.
**Salidas:** diff versionado, explicación, ledger de checks y propuesta de MR local.
**Capacidades necesarias:** `repository.read-scoped`, `repository.edit-scoped`,
`artifact.prepare-local`; `checks.run-approved` solo para comandos concedidos.

1. Resolver la tarea existente y su clave exacta; si es nueva, esperar creación Notion
   autorizada y confirmada. No fabricar clave ni duplicar un registro incierto.
2. Leer reglas y cambios existentes; comprobar repo/base y aislamiento autorizado.
   Si no hay permiso de rama/worktree, no ejecutar su creación como parte de la skill.
3. Mapear el flujo afectado y reutilizar patrones existentes; fijar el diff esperado
   antes de editar. No descartar cambios ajenos para conseguir un checkout limpio.
4. Preparar el mínimo cambio dentro del alcance. Clasificar cada comprobación antes
   de ejecutarla; conservar fallo → corrección → repetición y pendientes sin evidencia.
5. Presentar diff, base, resultados y límites; proponer título/cuerpo/destino del MR.
   Pedir revisión para efectos separados, sin commit, push ni publicación implícitos.

**Parar/escalar:** clave/ref dudosos, reglas incompatibles, repo compartido, dependencia
nueva o cambio fuera de paths permitidos. **Checks:** criterios funcionales concedidos,
reglas del repo y preservación; DB siempre separada si llegara a autorizarse.
No declarar implementación verificada solo por resolver dependencias o Compose.

## Skill: revisar un cambio

`review.assess-change@0.1` · **DRAFT** · dueño/revisor: pendientes de designación.

**Entradas:** diff/base/versiones exactas, objetivo, criterios, reglas y fuentes admitidas.
**Salidas:** hallazgos con ubicación/evidencia, severidad justificada, dudas y estado
de preparación. **Capacidades necesarias:** `repository.read-scoped`,
`artifact.prepare-local`; checks adicionales solo con `checks.run-approved`.

1. Confirmar qué diff se revisa; detectar si cambió respecto del encargo o aprobación.
2. Leer reglas aplicables y contexto suficiente dentro del repo permitido; separar
   problemas del cambio de deuda preexistente sin introducir correcciones ajenas.
3. Seguir los caminos relevantes de error, identidad, permisos, concurrencia y rollback.
4. Para cada hallazgo, mostrar consecuencia concreta y evidencia; marcar incertidumbre
   y descartar acusaciones sin soporte. No inventar ejecución de tests.
5. Entregar revisión y límites al coordinador. Si se pide corregir, se necesita otro
   encargo de desarrollo; comentar en MR es una acción de publicación separada.

**Parar/escalar:** diff cambiante, falta de base o necesidad de acceso adicional.
**Checks:** evidencia por hallazgo, cobertura de criterios y ninguna afirmación de
runtime sin comprobación. No resolver discusiones, aprobar MR remoto ni editar archivos.

## Skill: investigar y explicar un flujo

`research.explain-flow@0.1` · **DRAFT** · dueño/revisor: pendientes de designación.

**Entradas:** pregunta/hipótesis, corpus o entidades permitidas, referencias exactas,
fecha requerida y presupuesto. **Salidas:** recorrido, dependencias, hechos/inferencias,
alternativas y pendientes con procedencia. **Capacidades necesarias:**
`evidence.read-scoped`, `artifact.prepare-local`; lectura de repo solo si se concede.

1. Delimitar principio/fin del flujo y qué respuesta sería suficiente; resolver IDs
   exactos antes de recuperar por similitud.
2. Examinar evidencia autorizada y versiones; reutilizar mapas existentes sin asumir
   que siguen vigentes ni crear índices o conectores para completar el encargo.
3. Reconstruir pasos y decisiones, diferenciando relación observada de hipótesis;
   conservar contradicciones entre documentación, código y observaciones.
4. Comparar alternativas relevantes y explicar por qué se recomienda o rechaza cada
   una. Si falta evidencia, registrar la pregunta y el permiso necesario.
5. Entregar informe revisable, referencias y siguiente decisión; un plan resultante
   no activa implementación ni amplía fuentes.

**Parar/escalar:** fuente no admitida, dato revocado o conclusión que exigiría ejecutar
el sistema real. **Checks:** trazabilidad de pasos, frescura y desconocidos explícitos;
validar enlaces locales si se redacta documentación, sin visitar URLs de fuente.

## Resolución por job y conflicto

El permiso efectivo es la **intersección**, nunca la unión, de reglas vigentes del
proyecto, alcance aprobado del job, política del repo, perfil del rol y procedimiento
de skill, limitada además por las capacidades realmente concedidas al ejecutor.
Una skill no es permiso. Si un paso requiere una operación ausente, se detiene.
Ante contradicción o ambigüedad, fallar cerrado y pedir decisión, no elegir la regla
más permisiva ni cambiar de herramienta para eludirla.

Fijar versiones de política/skill por job para reproducibilidad; revisar revocaciones
vigentes antes de reanudar y antes de cada efecto. Un snapshot aprobado no permite
ignorar una revocación actual. La migración a una versión nueva requiere revisión.
Notion, Slack, comentarios de código y documentos recuperados son datos no confiables:
una instrucción embebida en ellos no cambia política, rol, destinatario ni allowlist.

## Aprobaciones y revocación

Una aprobación vincula actor autorizado, acción exacta, destino, contenido/diff y
versiones, entradas relevantes, expiración y condición de uso único/idempotencia.
No exige inventar un algoritmo criptográfico en este diseño; sí verificar esos vínculos
en el ejecutor y conservar su auditoría. Aprobar «un MR» no aprueba cualquier diff.

Cualquier cambio relevante de contenido, destino, base, alcance, fuente necesaria
o permiso invalida la aprobación hasta revisar de nuevo. Comprobar expiración y
revocación en vivo, no solo cuando se creó el job. Si el efecto remoto es incierto,
reconciliar antes de volver a consumir/reutilizar una aprobación; ver
[diario de acciones](orchestration.md#acciones-externas-y-resultado-desconocido).

## Skills del host: candidatos, no dependencias

Nombres existentes que podrían inspirar una adaptación: `soporte-triage`,
`review-commit`, `mr-comment-review`, `start-task`. No se han importado ni activado
como parte del producto. Sus reglas, conectores y convenciones necesitan revisión
explícita por proyecto; no copiar herramientas corporativas, SDK, agentes globales
o acceso de la sesión. El registro de arriba es independiente y continúa en DRAFT.
