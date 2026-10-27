# Plataforma del asistente: diseño del ecosistema

**DRAFT · propuesta para revisión · corte de evidencia: 2026-10-24.**
Este conjunto documenta una dirección de producto, no una implementación completa ni una
autorización para activar integraciones, agentes, tareas o publicaciones.

**Actualización posterior · retiro web del 2026-10-24:** la fuente de la web queda
en blanco; se eliminaron bandeja, simulaciones y paneles con sus clientes/hooks/proxy
y pruebas. El backend A, sus workers y los datos existentes se conservan.
La aceptación visual anterior y la matriz histórica de abajo no describen la UI
actual. La aceptación del despliegue vacío es separada; este cambio no implementa
B–F, colectores reales ni otra experiencia. Ver [estado web](../../apps/web/README.md).

## Propósito

Efren Bot podría coordinar asistencia al equipo: entender solicitudes, investigar,
preparar cambios y respuestas, pedir aprobaciones y seguir entregas con memoria.
Slack sería una entrada, no el centro exclusivo del producto. Notion conservaría
el registro administrativo; GitLab, la evidencia técnica; Efren Bot, la coordinación
y los motivos de cada decisión. La persona mantiene el control de los efectos.

## Recorrido de lectura

1. [Modelo de trabajo](work-model.md): familias, identidades y ciclos completos.
2. [Orquestación](orchestration.md): cola durable, paralelismo acotado y recuperación.
3. [Memoria](memory.md): historia explicable, recuperación exacta e índice derivado.
4. [Políticas y skills](policies-and-skills.md): reglas por rol sin conceder permisos.
5. [Integraciones](integrations.md): evidencia disponible y límites de cada frontera.
6. [Plan de implementación](implementation-plan.md): incrementos sujetos a aprobación.

## Autoridad documental

| Documento | Qué gobierna hoy | Relación con este diseño |
| --- | --- | --- |
| [Reglas del repositorio](../../AGENTS.md) | Alcance local, permisos, fuentes y comprobaciones | Siguen vigentes; este borrador no las sustituye. |
| [Arquitectura actual](../architecture.md) | Componentes y límites de la base implementada | No reinterpretar el worker fixture como agente. |
| [Contrato actual](../contract.md) | Identidades, API, dedupe y tres fixtures | No cambiar estados ni contratos desde estos documentos. |
| [Puente manual](../claude-bridge.md) | Excepción acotada Claude–Slack | No heredar su excepción para conectores generales. |
| [Evidencia de la base](../verification.md) | Comprobaciones históricas y límites | No convertir resultados anteriores en pruebas de la plataforma. |
| [Trabajo sintético A](../synthetic-work.md) | Contrato implementado, pruebas sintéticas y activación local acotada observada | Autorizado por separado; no convierte esta visión en plataforma activa. |
| Este directorio | Contratos propuestos para discutir | Solo documentación; requiere decisiones e implementación posteriores. |

Ante conflicto prevalecen las reglas vigentes y el contrato aplicable. Una decisión
futura necesitará alcance explícito y revisión de las reglas afectadas; no basta
con aprobar un párrafo de visión para habilitar una capacidad real.

## Vocabulario de evidencia

- **Actual / implementado:** existe en la base, según los contratos y su evidencia
  histórica; no significa que se haya vuelto a probar durante esta redacción.
- **Observado en sesión:** acceso o metadatos comprobados previamente por el operador;
  no equivale a integración del producto ni a permiso para repetir la consulta.
- **Propuesto / DRAFT:** contrato futuro sujeto a revisión, sin activación implícita.
- **Pendiente / no comprobado:** decisión o capacidad sin evidencia suficiente;
  no completar el hueco con una suposición del modelo.

## Actual frente a propuesto

La matriz conserva el corte de la base anterior a A; no es un inventario actualizado
de toda la implementación. El avance posterior acotado se distingue debajo.

| Área | Actual | Propuesta | Pendiente principal |
| --- | --- | --- | --- |
| Entrada | Tres fixtures, proveedor `fixture` | Solicitudes autorizadas de varias fuentes | Allowlist y autorización de cada fuente real |
| API y web | Ingesta, bandeja y detalle local | Expedientes, checkpoints, aprobaciones y auditoría | Contratos y controles de acceso nuevos |
| Ejecución | Outbox transaccional, worker sin red | Jobs largos, roles y ejecutores separados | Motor, aislamiento y presupuestos |
| Trabajo | Pendientes `needs_context` / `ready` | Familias de trabajo y seguimiento de entregas | Política de cierre humano |
| Memoria | Eventos, mensajes y actividades | Decisiones, versiones, intentos y evidencias | Retención, revocación y esquema futuro |
| Vector | Extensión pgvector y prueba SQL sintética | Recuperación semántica derivada | Modelo, dimensión y proveedor local |
| Reglas | `AGENTS.md` y contratos de la base | Registro versionado de roles y skills revisadas | Revisión y activación explícitas |
| Adaptadores | Ningún colector general de producto | Adaptadores host limitados y autorizados | Permisos reales y frontera host/producto |

### Avance posterior: incremento A

El usuario autorizó por separado «Sí, implementar A»: código, migración aditiva,
web y pruebas sintéticas en DB separada. Se implementó la vertical `request_video`
con cinco tablas, worker DB-only separado y panel cerrado por defecto/opt-in;
el panel fue eliminado en el retiro posterior, no el backend.
Su [contrato y ledger de pruebas](../synthetic-work.md) delimitan la evidencia;
los checks de backend y web por sí solos no acreditan runtime. En ese primer corte
no se migró la DB principal ni se reconstruyó/inició el nuevo runtime.

La autorización adicional del 2026-10-24 permitió **solo activar A localmente**:
backup privado, migración principal aditiva a `0003_synthetic_work`, reconstrucción/
recreación de API/web y nuevo servicio Compose `work-worker`. Se observó en navegador
propuesta persistida, reinicio exclusivo del worker y recarga sin pérdida, aprobación
simulada exacta y `delivered`/`succeeded`, con datos originales y cuatro servicios
protegidos intactos. Ver [activación y límites](../synthetic-work.md#activación-local-autorizada--2026-10-24).

A está activo **solo como simulación local**. No implementa B, roles
paralelos, leases de jobs reales, skills activas, adaptadores Notion/Slack/GitLab,
embeddings ni n8n. Fuentes reales, Git, nuevos despliegues e incrementos conservan
sus permisos separados; las reglas locales siguen vigentes. No se cierra la Task
fuente ni se afirma cierre global verified/done, riesgo formal resuelto u operación 24/7.

El puente manual tiene implementación parcial y controles propios; permanece
deshabilitado por política/opt-in según su documentación. No es el adaptador general
de esta propuesta. Tampoco se atribuye al producto el acceso de Slack, Notion o
glab observado en otras sesiones; ver [inventario](integrations.md).

## Decisiones de diseño que se someten a revisión

- Preparar fixes y borradores; aprobar publicaciones concretas antes de ejecutarlas.
- Reutilizar una tarea Notion existente; para una nueva, obtener la clave real antes
  de preparar una rama, siempre con permiso separado para repositorio y Git.
- Compartir evidencia autorizada y versionada, no conversaciones ilimitadas entre workers.
- Resolver reglas, skill y capacidades por job; ninguna skill amplía permisos.
- Conservar el porqué después de reiniciar o cambiar de motor de modelos.
- Empezar por un recorrido vertical sintético antes de fuentes reales; A fue autorizado
  por separado, sin extender ese permiso a otros incrementos.

## Cómo revisar sin activar

Revisar primero identidad, autoridad y límites; después los procedimientos por rol
y los criterios del plan. Registrar qué se acepta, qué cambia y qué queda pendiente.
La revisión de este índice no crea jobs, páginas, ramas ni schedules. El siguiente
incremento solo empieza con una nueva autorización delimitada.
