# Integraciones: evidencia y fronteras

**DRAFT · propuesta para revisión · corte: 2026-10-24.** Inventario de observaciones
previas proporcionadas para el diseño; esta redacción no repite consultas externas.
[Índice](README.md) · [Reglas vigentes](../../AGENTS.md).

## Evidencia frente a permiso

| Fuente | Observado previamente en sesión | No acreditado para el producto |
| --- | --- | --- |
| Slack MCP | Sesión autenticada; catálogo de ocho herramientas de lectura; dos canales y cinco hilos seleccionados | Colector, OAuth de producto, eventos, publicación o escucha continua |
| Notion | Esquema de colección global, muestra de tareas y relaciones | Escritura, reglas de validación efectivas o sincronización |
| glab host | Versión 1.114.0, identidad activa y metadatos privados de tres proyectos | Lectura de código/MRs, permisos de escritura, pipelines o push |
| Cliente oficial Claude Code | Puente local parcial y contrato específico | Motor exclusivo de la plataforma o autorización de conectores generales |
| n8n | Candidato discutido y retirado | Instalación, decisión de arquitectura o suscripción a eventos |

La evidencia pertenece a la sesión que la obtuvo, no a una API pública reutilizable.
No usar la sesión del usuario en OpenChamber como backend del producto. Un adaptador
host futuro consumiría interfaces oficiales aprobadas, con alcance propio y revisado.
Un enlace sirve de referencia, no de permiso ni de instrucción de navegación.

## Slack

El mapeo previo se limitó a dos canales autorizados y cinco hilos. No demuestra
acceso a otros canales, DMs, búsquedas globales o historial ilimitado. Una allowlist
futura tendría que identificar espacios/canales y tipos de entrada; las menciones
y DMs requieren reglas explícitas de recepción y consentimiento, no escucha implícita.

El MCP autenticado en chat no acredita scopes de escritura ni un SDK corporativo
permitido. Tampoco equivale a OAuth para un servicio nuevo, Event Subscriptions o
un trigger de n8n. Separar recibir eventos, consultar evidencia y publicar mensajes.
Cada una necesita su propia autorización, límites, dedupe y política de retención.

`source_url` sigue siendo metadato: el backend no visita permalinks ni genera previews.
La excepción del [puente manual](../claude-bridge.md) es un solo hilo elegido por
la persona, con perfil y barrera fail-closed aprobados; no autoriza los colectores,
workers de desarrollo ni publicaciones descritos aquí. La implementación parcial
y el estado deshabilitado se conservan según su evidencia histórica.

## Notion: identidad y esquema observado

Fuente administrativa observada: colección
[`895aa8b8-9502-47dc-ab9f-92faade51bc2`](https://www.notion.so/895aa8b8950247dcab9f92faade51bc2).
El identificador enlaza la fuente, no copia cuerpos de tareas ni acredita acceso actual.

- `ID` es la etiqueta autogenerada de clave KNF y figura como solo lectura. Obtener
  la clave completa desde Notion; no intentar asignarla al crear una página.
- El UUID interno de página es distinto de la clave de negocio y de `work_id`.
  Un número extraído por SQL no sustituye la clave completa real ni su procedencia.
- Status observado: grupo inicial `Backlog` / `To Do`; en progreso `In Review`,
  `Blocked`, `In Progress`; grupo completo `Approved`, `Cancelled`, `Done`.
  Esos grupos no significan entrega técnica ni mapeo automático al expediente.
- Type observado: `Discovery`, `Bug`, `Task`, `User Story`, `Support`.
- Priority observado: `Low`, `Medium`, `High`, `Very High`. No traducirlo a P0/P1
  ni imponer SLA sin una política revisada.
- `Substatus` y `URL` están deprecados; no elegirlos como fuente de verdad.
- Se observaron Assignee, Squad, Sprint con máximo uno, Epic y Projects por rollup
  a través de Epic. La diferencia operativa entre `Project` y `Projects` queda ambigua.
- No se observó un campo dedicado MR/branch. Una muestra de tres páginas con plantilla
  sin MR no demuestra que ninguna página contenga enlaces técnicos en su cuerpo.

Los campos descritos como obligatorios en documentación no acreditan enforcement.
La inspección visual de una página quedó truncada con cinco bloques sin conocer;
no afirmar que se leyó todo. Antes de diseñar escrituras habrá que resolver ubicación,
propiedades mínimas, relaciones y contenido aprobado sin inventar campos nuevos.

Documentos de workflow consultados previamente mencionaban dos aprobaciones,
cobertura >80 % y 48 horas. Son afirmaciones documentales no verificadas como política
vigente de runtime; hay conflictos/ambigüedades pendientes. No convertirlas en gates
universales de jobs o MR. La referencia exacta de cada documento deberá fijarse en
el piloto autorizado; este inventario no inventa IDs de páginas que no tiene.

## GitLab mediante host

La observación previa con glab 1.114.0 incluyó GET de identidad activa y metadatos
de proyectos privados: Core `40652545`, web `64374983`, workers `70356711`.
El resultado mostró `group_access=5` y `project_access=null`; no deducir de ello
permisos efectivos de código, MR o escritura. Esas operaciones **no se probaron**.

Elegir repositorio y tarea es una decisión pendiente por encargo. La política del
repositorio, permisos Git, ramas protegidas y publicación deben revisarse antes
de preparar cambios reales. Conocer el ID del proyecto no autoriza clonarlo,
crear una rama, comentar una MR o ejecutar pipelines.

El flujo futuro reutiliza la tarea Notion existente o espera la creación aprobada
de una nueva antes de la rama. Los vínculos MR/branch pueden vivir como referencias
de expediente hasta acordar cómo reflejarlos en Notion; no usar campos deprecados
ni cambiar el esquema externo desde este diseño.

## Frontera host, motor y secretos

Las credenciales nativas permanecen administradas por el cliente oficial del host.
No copiar tokens ni montar HOME en API, Docker, DB, web o logs. No convertir una
suscripción del usuario en API de modelo, proxy OAuth o fallback de facturación.
El contrato actual del puente admite únicamente su secreto propio y perfil no secreto
mediante override opt-in; no ampliar esa excepción a credenciales de proveedores.

Claude Code no queda elegido como motor exclusivo. Un motor futuro debe cumplir
los mismos contratos de job, evidencia, límites y capacidades. La compatibilidad
con herramientas oficiales y condiciones de uso requiere evaluación específica,
sin heredar login, modelos o herramientas globales por defecto.

La activación de una fuente real exige decisión explícita sobre las restricciones
actuales de [AGENTS.md](../../AGENTS.md), alcance, datos admitidos y controles; no
editar reglas para sortearlas ni considerar este inventario como excepción nueva.
No se eligió proveedor de embeddings, credencial, servicio cloud ni conector corporativo.

## Pendientes antes de cualquier piloto

Precisar allowlists y consentimiento, retención/revocación, identidad del adaptador,
capacidad real de solo lectura y prueba fail-closed. Para efectos, añadir aprobación
exacta, idempotencia soportada y reconciliación de resultado remoto desconocido.
Un n8n opcional solo encolaría entradas autorizadas; no sería segundo dueño de estado.
Ver [incrementos y gates](implementation-plan.md), sin activación automática.
