# Efren Bot · base local

Base independiente y local. La web dispone ahora de recolección Slack con controles
**Pausar/Reanudar automático** y **Recolectar ahora**, también mientras está pausada.
El host usa su conexión oficial existente, sin inferencia ni credenciales copiadas.
Los fixtures, tareas y trabajo sintético se mantienen separados.

## Estado

Actualización local: **Solicitudes y decisiones**, bandeja común para soporte/MR con
continuar/reorientar/pausar/ignorar/delegar/detener y autorización de acciones concretas.
Esquema actual `0010_human_control`; [contrato](docs/human-control.md).
Se conservan informes y datos previos. API/web actualizadas; recolección pausada y
ejecutores host detenidos: esta entrega no los reanuda ni habilita nuevas capacidades.
El cierre formal de riesgo/Git sigue pendiente. Los esquemas de los incrementos
anteriores que se describen abajo son referencias históricas, no el head de migración.

Nuevo incremento local: **Revisiones por decidir**, todas las MRs de una solicitud
nueva, revisión estática por dimensiones, evidencia, propuestas privadas y chat/pausa.
Solo Core y konfio-app-web. Demo aislada de tres MRs sin publicación. Esquema
`0009_mr_review`, host `make review-runner`; [contrato y aceptación](docs/mr-review.md).
No equivale a ejecutar tests/código de MRs ni habilita fuentes de soporte pendientes.
API/web desplegadas; los tres informes de la demo son parciales y muestran sus faltantes,
sin publicaciones ni nuevos hallazgos artificiales. Riesgo formal/Git siguen pendientes.

Nuevo incremento local: pestaña **Investigaciones de soporte**, detección de soporte
solo desde mensajes nuevos, preliminar/chat/pausa y borrador copiable. **CloudWatch y
código aún no conectados**: los casos quedan bloqueados por alcance pendiente y no
se presentan como diagnósticos confirmados. Ver [contrato y límites](docs/support.md).
Ejecutor independiente `make support-runner`, esquema `0008_support`. El histórico
no se investiga automáticamente. La vista de conversaciones y el recolector continúan.

Vista vigente: **Conversaciones**, no comentarios sueltos a clasificar. Lista y
contexto se muestran juntos en escritorio; las menciones en cualquier respuesta
guardada se pueden localizar sin salir a Slack. Seguimiento opcional: organiza
uno o varios asuntos locales por hilo, con título, tipo, atención y mensajes de
evidencia (o contexto completo). Sin clasificación automática ni tareas inferidas.
Las referencias desconocidas/contradictorias se señalan, no se inventan relaciones.
Esquema vigente `0007_collection_conversations`; las notas de bandeja por mensaje
siguientes son históricas y sus anotaciones originales se conservan.

La web incorpora bandeja con todo el historial paginado, nuevos/sin revisar,
filtros y contexto de hilos. Tipo, atención y revisión son anotaciones manuales
locales e independientes: no cambian Slack ni crean tareas. «Actividad de
recolección» abre un panel lateral; «Configurar fuentes» permite cambiar los
canales accesibles y su modo para siguientes ejecuciones, sin borrar historia.
El archivo piloto autorizado se incorpora offline con
`uv run --frozen python -m efren_bot.collection.archive`, preservando sus originales;
no habilita automáticamente canales futuros ni se marca como mensaje nuevo.
Esquema vigente: `0006_collection_inbox`; los números de migraciones siguientes
son evidencia de entregas previas. Contrato completo en `docs/slack-collection.md`.

Incremento vigente: [Recolección Slack local](docs/slack-collection.md).
Abrir **http://127.0.0.1:5173**. La programación es cada15min y requiere host/ejecutor
disponible; la web no necesita permanecer abierta. `make collection-runner` ejecuta
el lector del host. Pausa, avance por fuente e historia persisten en PostgreSQL;
los fallos parciales se muestran sin bloquear el progreso de otras fuentes.
Principal migrada a `0005_collection_progress`. Sin publicaciones, adjuntos
descargados, interpretación ni tareas automáticas. Git y riesgo formal diferidos.

Los apartados de retiro/demo siguientes conservan evidencia histórica, no describen
la pantalla ni el esquema vigentes tras este incremento autorizado.

Retiro de fuentes web del 2026-10-24: scaffold React/Vite conservado, `App` vacío,
sin clientes/hooks/proxy, polling ni paneles. La aceptación del despliegue en navegador
es un paso separado; cambiar fuentes no acredita el runtime servido.

La evidencia anterior corresponde a la demo antes del retiro: stack Docker, tres
fixtures por HTTP, dedupe/conflicto, reinicio del worker sin pérdida de reply,
PostgreSQL/vector sintético y recorrido visual/teclado de escritorio/móvil con horas
de Mérida y JSON UTC. No describe una interfaz disponible ahora.
Tarea 5 funcional histórica completada; tarea 6 (riesgo exacto,
revisión requerida y entrega formal) diferida por el usuario junto con Git.
La feature sigue **pending**, no verified/done ni V1 completa.
[Evidencia, fallos y reintentos](docs/verification.md).

- [Arquitectura y límites](docs/architecture.md)
- [Contrato compartido de API e identidad](docs/contract.md)
- [Diseño futuro de la plataforma del asistente · DRAFT](docs/assistant-platform/README.md)
- [Entorno y comprobaciones](docs/local-development.md)

### Puente Claude–Slack: entrega parcial separada

La entrega previa incluyó API y panel propios; se conserva su evidencia histórica.
El retiro web elimina también el componente manual y su proxy, no el backend Bridge.
No hay controles ni consultas del puente desde la web en blanco.
El puente manual está **deshabilitado por política/opt-in**, sin
perfil aprobado ni prueba nativa fresca: no es un fallo de conexión. La sesión CLI
renovada y los metadatos oficiales Slack están acreditados; **no se ha leído ningún
hilo Slack**. Tarea 5 parcial, 6 pendiente; sin cierre verified/done global.

El usuario eligió «Lo compartiré después»: esperar su enlace/workspace sin volver
a pedirlos. Solo entonces corresponden revisión/aprobación del perfil y host,
prueba nativa real y habilitación opt-in/runner. Git y riesgo formal siguen diferidos.
[Contrato del puente](docs/claude-bridge.md) ·
[Evidencia e intentos conservados](docs/claude-bridge-verification.md).

## Arranque

### Incremento A activo en el runtime local · 2026-10-24

El trabajo sintético persistente añade `/api/work`, cinco tablas, historia/checkpoint,
propuesta ASK_CONTEXT y aprobación **simulada** con worker DB-only separado
`python -m efren_bot.work_worker`. [Contrato, dos ejemplos y evidencia](docs/synthetic-work.md).
La primera entrega fue solo fuente/pruebas en DB separada. Tras autorización adicional,
la base principal se migró aditivamente a `0003_synthetic_work`, API/web se reconstruyeron
y recrearon, y el servicio Compose `work-worker` quedó iniciado. El worker fixture y
los servicios DB/test-db/migrate históricos se conservaron; publicaciones solo loopback.

La aceptación anterior al retiro observó propuesta en `waiting_human`, reinicio
exclusivo de `work-worker`, recarga sin perder contexto y aprobación simulada hasta
`delivered`/`succeeded`. Es un corte histórico, no un inventario actual de expedientes.
El panel y sus controles se eliminaron; la API, la principal en `0003_synthetic_work`,
el proceso `work-worker` y los datos existentes se conservan. No hace falta arrancar
otro worker ni crear un expediente para aceptar la página vacía. La entrega A es **sintética local**:
no sube video ni cierra Task/fuente; la tarea original sigue `needs_context` con
`has_new_reply`. Sin conectores, B–F ni promesa 24/7. Riesgo formal/Git siguen pendientes.
[Activación, preservación y límites de evidencia](docs/synthetic-work.md#activación-local-autorizada--2026-10-24).
Los comandos siguientes son referencia operativa, no permiso para acciones adicionales.

Requisitos: Python 3.14.6 (rango admitido `>=3.12,<3.15`), uv 0.11.28,
Docker con Compose. Para checks en el host: Python/uv y Node 26/npm.

```sh
make up        # db sana -> migración -> API/worker -> web; espera readiness
make demo      # CLI: ingesta backend compartida; worker procesa por separado
```

No hace falta `.env` para los defaults demo. Compose interpola variables; los procesos
Python del host solo leen el entorno explícito (no cargan `.env` automáticamente).
`make sync` instala el proyecto y dependencias bloqueadas. `uv.lock` se genera con
el resolver, no se edita manualmente. No hace falta PostgreSQL instalado en el host.

## Pruebas y operación

### Base local

```sh
make sync
make test-db   # crea/espera DB exclusiva efren_bot_test en 55433
make check     # Compose, Ruff src/tests/migrations, npm ci/typecheck/build
make test      # unitarias, integración DB separada (migra) y web
make logs
make down      # solo este proyecto; conserva volúmenes, nunca añade -v
```

Web local `http://127.0.0.1:5173`, API directa `http://127.0.0.1:8000`, PostgreSQL
`127.0.0.1:55432`. Proyecto Compose `efren-bot`; no reutilizar contenedores ni
volúmenes ajenos. La DB de pruebas es `efren_bot_test` en `55433`, con volumen
separado; los tests rechazan la DB demo. Para pausar sin retirar contenedores:
`docker compose --project-name efren-bot --profile test stop`.

No quedan botones de simulación ni acceso API mediante proxy web. La CLI/backend
conservan los tres fixtures canónicos y sus identidades, sin borrar datos al repetir.
Su semántica sigue siendo: petición de video -> `needs_context`; agradecimiento ->
sin tarea; respuesta sin nueva mención -> mismo pendiente con `has_new_reply`.
No se cierra nada automáticamente. Solo los tres mensajes exactos tienen semántica
de demo; el resto queda `ignored` sin tarea, para revisión manual. pgvector tiene
una prueba SQL sintética: eso **no** equivale a LLM, RAG ni embeddings implementados.
