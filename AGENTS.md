# Reglas de este repositorio

- Producto independiente, exclusivamente local. No incorporar servicios, credenciales,
  conectores ni SDK corporativos reales. No commits, push, ramas o despliegues sin autorización.
- El contrato común está en `docs/contract.md`; arquitectura en `docs/architecture.md`.
  Son decisiones de esta base, no una copia ni implementación de una especificación V1 completa.
- Dominio Python en `src/efren_bot`; API ASGI `efren_bot.api:app`, worker
  `python -m efren_bot.worker`, CLI demo `python -m efren_bot.demo`; web en `apps/web`.
- Python `>=3.12,<3.15`, entorno fijado a 3.14.6; uv 0.11.28 y lock real. Usar
  FastAPI/Pydantic 2, SQLAlchemy 2, Alembic y psycopg 3. No hace falta cliente Python
  pgvector mientras alcance SQL. Dependencias web con `package-lock.json` y `npm ci`.
- UUID nativos en DB/dominio, strings UUID en JSON; IDs del proveedor son strings
  opacos y claves compuestas. Nunca mezclar entrega, evento, mensaje e hilo.
- Validar `APP_ENV=local` al iniciar API, worker y demo. Fechas aware, persistencia UTC;
  `APP_TIMEZONE` solo para presentación. Nunca visitar `source_url` desde el backend.
- Ingesta evento/outbox atómica. Dedupe por evento **y** mensaje; conflicto explícito
  ante contenido distinto, sin merge semántico. Worker sin red, proyección/ack en una
  transacción corta con locks; rollback debe permitir reintento sin proyección parcial.
- No implementar semántica fuera de los tres fixtures ni transición automática a `done`.
- Docker aislado en proyecto `efren-bot`, publicaciones solo loopback. No modificar
  servicios de otros proyectos ni ejecutar `down -v` automáticamente. La preparación
  de contratos no inicia servicios; el arranque local corresponde a la integración posterior.
- Clasificar cada comprobación **antes** de ejecutarla: obligatoria por criterio/proyecto
  u opcional, indicando fuente. Conservar fallos/reintentos y no declarar runtime verificado
  solo porque Compose o el resolver pasan. Pruebas de DB siempre en base separada.
- Revisar reglas y trabajo existente antes de editar. No crear implementaciones vacías
  para hacer pasar checks. API, worker, web y pruebas están implementados; conservar
  la evidencia y los límites de la demo al integrarlos.

## Excepción acotada: claude-slack-bridge

La solicitud de recolección Slack local manual/periódica con pausa web autoriza
además el incremento independiente de `docs/slack-collection.md`: host/CLI oficial
OpenCode y conexión existente, tablas collection separadas y web local protegida.
Solo devs/tech, DMs propios individuales/grupales y menciones en canales propios
con su hilo. No SDK/tokens corporativos en producto, HOME en Docker, fuentes nuevas,
publicaciones, archivos descargados ni cambios en fixtures/tareas. API nunca visita
permalinks. Git y demás límites intactos. No es extensión del puente Claude.

La autorización posterior de bandeja permite importar offline el archivo histórico
ya aprobado de cinco canales a collection, preservando originales/procedencia,
mostrarlo localmente y guardar anotaciones manuales de revisión/atención/tipo.
Permite seleccionar canales propios accesibles para futuras lecturas completas,
solo menciones o desactivadas. Importar historia no habilita fuentes futuras.
Sin clasificación automática/modelos, tareas, publicaciones ni nuevos conectores.

La corrección posterior autoriza vista por conversación con relaciones explícitas,
menciones literales en todo el contexto guardado y organización humana opcional en
uno o varios asuntos locales con evidencia y clasificación por grupo. Son registros
collection independientes, no tareas fixture/work ni automatizaciones. No inferir
encargos/relaciones ni exigir clasificación de todos los comentarios. Conservar
fuentes originales y anotaciones previas; no nuevos accesos Slack por extensión.

## Incremento autorizado: soporte nuevo

La solicitud posterior autoriza clasificación por modelo e investigaciones automáticas
solo a partir de mensajes nuevos de soporte, con chat/intervención/pausa durante el
trabajo, preliminar y borrador para copiar a Slack. Tablas y ejecutor host separados
de fixture/work y del recolector. Histórico solo contexto; máximo un ejemplo aislado,
nunca barrido. Sin sobrescribir correcciones humanas, fuentes ni evidencia previa.
Modelo mediante interfaz oficial del host, sin herramientas de escritura ni fallback.
Logs CloudWatch y repos GitLab/local requieren alcance explícito aprobado; no inferir
permisos del catálogo ni del texto Slack. Si falta alcance/acceso, mostrar bloqueo.
No credenciales corporativas en API/Docker ni nuevos accesos Slack por extensión.
Sin publicar, modificar fuentes, datos remotos o repos, ni operaciones Git. Permite
actualizar y arrancar únicamente servicios locales propios para mostrar el incremento.

## Incremento autorizado: revisiones de MR

Solicitudes nuevas de revisión Slack pueden activar lectura automática de TODAS sus
MRs en Core y konfio-app-web, proyectos GitLab40652545 y64374983 exclusivamente. Cola,
instantáneas, propuestas y controles propios, sin cambiar fixture/work/soporte. Prueba
histórica aislada autorizada: hilo C07SRBE0V1T/1792770316.988339 con8573/8594/8616;
sin habilitar barrido histórico ni fuentes extra. glab oficial del host/conexión actual,
modelo text-only sin herramientas ni fallback. Demo sin publicaciones. Acciones de
publicación futuras requieren aprobación humana de contenido/versión concretos y
guardia de vigencia; nunca permiso implícito para resolver/aprobar/mergear. Ejecución
de código, tests de MR, BD, Temporal y CMS no quedan autorizados. Sin Git/checkout,
credenciales en API/Docker, cambios en otros repos o configuración global. Permite
desplegar solo los servicios locales propios afectados para mostrar la sección.

- Autorizada la lectura manual de un único hilo Slack elegido por el usuario mediante
  Claude Code oficial del host y su propia suscripción, según `docs/claude-bridge.md`.
  Esta excepción a las restricciones de fuentes reales/semántica de demo solo permite
  runs separados y propuestas revisables; no cambia provider `fixture`, worker,
  contratos ni evidencia histórica de la base. No es permiso para otros conectores.
- Se autoriza el actualizador oficial `claude update`, sin editar configuración global,
  cambiar canales ni copiar credenciales. Sin perfil local aprobado o barrera fail-closed
  comprobada, el puente permanece deshabilitado; sin fallback de modelo/API/proveedor.
- Docker/API/DB/logs nunca reciben HOME ni tokens Claude/Slack. Solo el secreto propio
  del puente y el perfil no secreto pueden montarse readonly en la API por un override
  opt-in. Archivos propios bajo `.local/bridge/` ignorados, permisos restrictivos.
- Sin escucha, búsqueda global, publicación, delegados ni efectos automáticos sobre
  tareas. Backend no visita permalinks. Host/Origin/JSON/auth se validan antes de
  admitir datos reales. Todas las demás reglas y la decisión de Git intacto se conservan.
