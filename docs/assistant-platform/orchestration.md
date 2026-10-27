# Orquestación durable y ejecución paralela

**DRAFT · propuesta para revisión · 2026-10-24.** No es el comportamiento del
worker actual. [Índice](README.md) · [Identidades y estados](work-model.md).

## Componentes propuestos y un solo dueño del estado

```text
Fuentes autorizadas -> colectores ligeros -> eventos/candidatos persistidos
                                               |
Persona / regla aprobada -> coordinador -> cola durable de jobs
                                               |
                               workers por rol y alcance acotado
                                               |
                         artefactos + checkpoints + propuestas
                                               |
                      aprobación -> ejecutor de efectos autorizados
                                               |
                           confirmación o reconciliación -> historial
```

Los colectores aplicarían cursores, dedupe y filtros deterministas antes de solicitar
interpretación. No llamar al LLM en cada poll ni crear un worker permanente por canal.
El coordinador administra admisión, dependencias y estados; los workers reciben
encargos con entradas delimitadas. Una cola durable, no la conversación del modelo,
conserva lo pendiente. Cambiar el motor no debe perder ni reiniciar el encargo.

La memoria compartida se consulta por expediente, fuente y permiso; no es una sala
común con todos los prompts. El worker devuelve artefactos y decisiones estructuradas.
No delega a otros workers ni amplía fuentes por iniciativa propia; una nueva necesidad
vuelve al coordinador para su autorización y despacho.

## Contrato de despacho y aislamiento

Cada job referencia `work_id`, entradas/versiones, rol/skill/política fijados,
repositorio y ref permitidos si aplican, presupuesto, criterios, acciones prohibidas
y condición de parada. El coordinador comprueba dependencias y permisos actuales.
Un job sin esos datos queda bloqueado, no «completa» los huecos con defaults amplios.

Paralelismo solo entre alcances compatibles. Dos jobs no escriben el mismo checkout,
rama o recurso mutable. Una dependencia serializa el cambio que otro deba revisar.
Worktrees o entornos separados son opciones futuras, solo en repositorios y topologías
autorizados después; este diseño no crea ramas ni mueve trabajo existente.
Cada entorno recibe el mínimo de archivos y herramientas, nunca HOME o credenciales
globales por herencia. Aislar carpeta no equivale a aislar permisos de proceso.

## Claim, leases y fencing para jobs largos

1. En transacción corta, reclamar exclusivamente un job elegible, crear un intento,
   asignar propietario, vencimiento y generación de fencing; confirmar y liberar DB.
2. Ejecutar lectura, modelo, red o proceso **fuera** de la transacción. Renovar por
   heartbeat condicionado a propietario/generación vigentes y ausencia de cancelación.
3. Antes de aceptar checkpoint o resultado, validar la generación en una transacción
   corta. Un propietario vencido no puede sobrescribir el resultado del sucesor.
4. Antes de cada efecto, el ejecutor valida claim de acción, lease/fencing, aprobación,
   permisos vivos y contenido exacto. No confiar en una validación hecha al iniciar el job.
5. Si expira el lease o se pierde la renovación, el worker deja de iniciar operaciones;
   el coordinador recupera desde evidencia durable, no desde una respuesta tardía.

El fencing debe proteger la persistencia y la admisión de efectos, no ser solo un
campo informativo. Un servicio remoto puede no aceptar generaciones: una llamada ya
en vuelo podría completarse aunque el lease venza. Ese límite exige registrar el
intento y reconciliar; no se promete impedir ni deshacer todo efecto remoto tardío.
La elección concreta de leases, reloj, almacenamiento y ejecutor sigue pendiente.

## Acciones externas y resultado desconocido

Una acción es distinta del job: crear tarea Notion, hacer push, crear MR o publicar
Slack tienen destino, contenido/versiones, aprobación y clave de idempotencia propios.
Solo un ejecutor habilitado puede reclamarlas. El claim exclusivo de acción y la
validación de su aprobación se confirman en una transacción corta; la llamada de red
se ejecuta fuera de ella. El modelo que prepara código no recibe una shell con
publicación irrestricta; la frontera debe impedir el bypass por CLI.

Antes del envío se registra intención en un diario local durable. Después se guarda
confirmación y referencia remota; si falta respuesta, el estado es **resultado remoto
desconocido**, no «falló, repetir». Primero reconciliar con la identidad devuelta o
con una referencia/correlación soportada y autorizada por el destino.
Si no hay idempotencia o consulta inequívoca, pedir revisión humana: no crear otra
página, MR o respuesta «por si acaso». No se promete exactly-once externo.

Los reintentos tienen límite, backoff y presupuesto. Separar error transitorio,
entrada inválida, permiso denegado y resultado desconocido. No reintentar denegaciones
con otro modelo, credencial o herramienta. Los fallos conservan su evidencia original.

## Espera, reanudación y cancelación

- Al esperar persona o sistema externo, guardar checkpoint: entradas/versiones,
  avance, artefactos, preguntas, acciones enviadas y próximo paso permitido.
- Liberar capacidad de ejecución. La espera vive en la cola y el expediente;
  no mantener una sesión de DB, shell o conversación de modelo abierta.
- Para reanudar, comprobar permisos, revocaciones, fuente actual, ref del repo,
  versiones de skill/política y vigencia de aprobación. Un cambio relevante requiere
  revisión o nueva aprobación, no continuación ciega desde un snapshot antiguo.
- Cancelar bloquea nuevos claims y efectos. Señalizar al worker activo y registrar
  efectos ya confirmados; cancelación no es rollback remoto ni borra historial.
- Si hay una escritura incierta, reconciliar primero incluso al cancelar. No lanzar
  compensaciones o borrados sin autorización específica para esa nueva acción.

## Capacidad y scheduling

Prioridad, antigüedad, dependencias y límites por fuente/repositorio permitirían
equilibrar urgencia y justicia. Reservar un cupo o pausar trabajo son decisiones
configurables, no números fijados por este borrador. Limitar concurrencia, tiempo,
coste de modelo, tamaño de contexto y volumen de llamadas por job y por operador.

Un Mac suspendido o sin red no garantiza atención urgente ni disponibilidad 24/7.
Guardar retrasos y señales de salud; no prometer capacidad ilimitada. Las cadencias
anteriores de 30/5 o 2/1 minutos son hipótesis de conversación, no SLA aprobado.

n8n es un candidato opcional previamente retirado, no un componente instalado o
elegido. Si se reconsidera, solo propondría/encolaría eventos o encargos autorizados;
no tendría otro estado de jobs, aprobaciones ni reintentos que duplique al coordinador.

## Lo que no se cambia en la base

El [outbox actual](../architecture.md#transacciones-y-recuperación) proyecta fixtures
y confirma ack en una transacción corta, sin red. Su recuperación por rollback no
necesita estos leases de trabajos largos. No extenderlo implícitamente a ejecutar
modelos, código o publicaciones. La cola futura requiere contrato y pruebas propios.
Ver [criterios de recuperación](implementation-plan.md#criterios-de-aceptación-futuros).
