# Traspaso de sesión — Efren Bot

## Leer primero

Snapshot de continuidad del **2026-10-25**. El usuario pidió: «necesito abrir otra sesión [...] todos estos pendientes y todo, revisa que está documentado [...] en un Md de punto d».

Este archivo es la entrada a los documentos locales; no sustituye sus historias ni autoriza acciones nuevas. Leer las decisiones vigentes antes de recetas antiguas. La sesión de origen es `ses_e98e61417ffeX7Km8S0Q7Zp7R0`; puede consultarse su conversación si se necesita recuperar evidencia del ejercicio, sin volver a consultar sistemas externos por defecto.

## Prioridad al retomar

Prioridad vigente posterior: [slack-collection.md](slack-collection.md). Usuario pidió recolección manual desde web y automática cada 15 minutos, desde activación, en devs/tech, DMs individuales/grupales propios y menciones en sus canales. Flujo distinto del piloto asistido siguiente; su interfaz oficial de ejecución host aún no está acreditada. No se ha activado ni recolectado nada nuevo. CloudWatch y Git siguen diferidos.

Actualización 2026-10-25: Efrén aprobó el contrato asistido («Ok, estoy de acuerdo. Continuemos entonces.»), recogido en [docs/slack-assisted-pilot.md](../docs/slack-assisted-pilot.md). El acuerdo de producto ya no está pendiente; sí la autorización de implementación y la admisión del paquete real. Las prioridades y casillas del snapshot siguientes son historia previa a este acuerdo. Próximo paso vigente: solicitar permiso para implementación con pruebas sintéticas, sin importar el hilo ni iniciar servicios. CloudWatch y Git siguen diferidos.

**Acordar el contrato del primer recorrido asistido de Slack: entrada real → interpretación/propuesta con evidencia → decisión/corrección persistida → vista mínima.** Es el siguiente paso propuesto al usuario, no una implementación ya iniciada ni permiso implícito para iniciar servicios o cambiar contratos.

Antes de escribir código, precisar:
1. Qué paquete mínimo de un hilo histórico entra, con autor/fechas/fuentes/cobertura, y cómo se autoriza su admisión local.
2. Qué interpretación, relaciones opcionales, incertidumbre y siguiente paso entrega esta conversación como propuesta asistida.
3. Qué decisión/corrección se guarda, dónde se conserva separada de fixtures/historia anteriores y qué sucede al recargar/reintentar.
4. Cómo se traspasa el resultado entre la sesión y la aplicación. **Esta conversación no está conectada como motor autónomo de la API/web** y no transfiere su autenticación a un proceso externo.

Después, con autorización de implementación, construir admisión/persistencia y una vista mínima. No restaurar paneles falsos ni usar fixtures/keywords como IA. No resolver primero el rendimiento CloudWatch: quedó diferido.

## Decisiones vigentes que no hay que reabrir por accidente

- ChatGPT/OpenAI es el motor principal. Usar la sesión actual en modalidad asistida; no pedir otro perfil/login. Cita que corrigió la vía: «mejor usa la sesion actual es mucho pedo». El perfil aislado anterior es historia sin uso; no ejecutar sign_in.py.
- Claude no es el motor elegido para este piloto. Su uso para desarrollo/otros roles y el reparto de modelos por función siguen diferidos. Compartir una skill entre clientes no significa ejecutar Claude o Codex.
- Relaciones solo con evidencia; pueden ser inexistentes o ambiguas. No crear trabajo por cada mención, reenvío o mensaje informativo. Mención literal no acredita notificación ni encargo.
- Conservar autores, tiempos, hilo completo disponible y enlaces; separar fuente, afirmación ajena, observación e hipótesis. No visitar enlaces/descargar adjuntos automáticamente.
- Soporte es ocasional, no el foco permanente del asistente. Las siete capacidades conceptuales no son categorías forzosas ni una secuencia universal.
- No copiar credenciales, contratar APIs, modificar configuración global, publicar mensajes, crear tareas externas, clonar/modificar repositorios ni ampliar fuentes por extensión. Sin staging, commits, ramas, worktrees, push ni despliegues autorizados.
- Producto independiente/local; no incorporar SDK o servicios corporativos reales al producto. Las investigaciones manuales autorizadas del host no constituyen conectores activos ni admisión al backend. La excepción acotada antigua de Claude no se convierte en permiso general para OpenAI/datos reales: cerrar el contrato y la autorización correspondiente antes de admitirlos al producto.

## Estado real, no equivalencias

| Área | Estado al cierre de esta sesión |
|---|---|
| Base local/backend/DB/historia | Se conservaron; esta sesión no los modificó durante las pruebas ni este traspaso. No es una nueva aceptación runtime de sus servicios. |
| Web | Última aceptación histórica: vacía tras eliminar UI de simulación. Esta sesión no construyó la nueva vista. Inspeccionar el checkout al implementar; no asumir que chat equivale a pantalla. |
| Archivo Slack | Corpus privado y expansión de hilos existentes; inmutables. No recopilación continua ni ingestión al producto. |
| Interpretación asistida | Dos ejemplos reales aceptados por Efrén: informativo sin tarea y seguimiento de trabajo. El contraste GitLab ajustó la interpretación; no se modificaron MRs/tickets. |
| Investigación de soporte | Hubo lecturas AWS autorizadas, con fuentes incompletas; causa y resolución del caso no demostradas. No resumirla como incidente vigente confirmado ni como trabajo terminado. |
| Persistencia de propuestas/correcciones y recarga | Pendiente del producto. No se logró por conversar o guardar memoria técnica. |
| Conexión automática modelo↔app | No implementada ni demostrada. No simularla para construir otra UI. |

## Pendientes activos y diferidos

### Próximo incremento propuesto
- [ ] Acordar contrato de entrada/salida/decisión y traspaso asistido de un solo hilo histórico.
- [ ] Aprobar la admisión local real y los acompañantes mínimos en reglas/contratos, sin abrir acceso corporativo general.
- [ ] Implementar persistencia separada y vista mínima después del acuerdo/autorización.
- [ ] Probar corrección humana, continuidad/recarga, fuentes incompletas, acceso denegado, fallo de motor, cancelación/reintento. No declarar aceptación global por los ejemplos del chat.

### Diferidos por el usuario
- [ ] **CloudWatch: rendimiento y lector reutilizable.** Backlog `03cc6676-144a-40ed-9c96-dbec8efba400`. Mantener método/ruta/respuesta unidos, paginación y contabilidad final, salida sanitizada y medición extremo a extremo. No generar otro colector ad hoc ni retomar consultas por iniciativa propia. Cita: «Ok, vamos a dejar como pendiente esta parte de ajustes. ¿Cuál sería el siguiente paso?»
- [ ] **Git/primera entrega y cierre formal de la base.** Backlog `0a082f57-31df-4b1b-b4a7-d53cc6d7665c`. Sin permiso Git/topología; no aislar por cuenta propia para satisfacer un gate.
- [ ] **Notion/Ocean, otros conectores, listeners/automatización y selección de modelos por rol.** No activarlos con el piloto.

### Límites de verificación pendientes, sin bloquear artificialmente lo demás
- [ ] Carga real de la skill compartida en sesiones Codex/Claude Code: hay compatibilidad documentada/enlace, solo OpenCode se probó aquí.
- [ ] Riesgo formal del delta externo de la skill y del checkout histórico: sin base exacta aislada autorizada; no inventar aprobación de scraft-judge.
- [ ] Investigación de soporte incompleta: si se reabre, necesita plan y presupuesto expresos; no aprovechar saldos ni reiniciar contadores por cambiar de sesión.

## Skill AWS: dónde está y qué sí significa

- Fuente única: `~/.agents/skills/aws-support-investigation-readonly/`.
- Claude Code: `~/.claude/skills/aws-support-investigation-readonly` enlaza a `../../.agents/skills/aws-support-investigation-readonly`. OpenCode V2/Codex descubren la fuente compartida según documentación.
- Puente: `~/.claude/skills/soporte-triage/{SKILL.md,references/cloudwatch.md}`. La biblioteca de decisiones permanece intacta.
- **La skill limita al agente, no cambia IAM.** Cita que sustituyó el bloqueo anterior: «sé que el perfil tiene muchos permisos [...] el skill debe ser la limitante». No exigir nuevo rol, sandbox, ejecutor o verificador externo como prerrequisito inventado.
- Allowlist vigente: `sts:GetCallerIdentity`, `logs:FilterLogEvents`, `logs:GetLogEvents`; perfil existente, alcance finito, sanitización antes del modelo, sin escrituras/invocaciones/fallback. Insights (`StartQuery`/resultados/`StopQuery`) sigue fuera salvo autorización distinta; no habilitarlo implícitamente.
- Temporalidad: el mensaje marca **reporte**, no incidente. Horizonte retrospectivo contextual de días/semanas; tramos técnicos pequeños no reducen el alcance lógico. Plan completo aprobado una vez, no pregunta por cada tramo. Token pendiente/timeout/tope dejan huecos, no ausencia de actividad.
- Catálogo: `references/technical-catalog.json`, revisión0; tres grupos Core **documented**, cuenta/entorno desconocidos. Sin promoción a observed por nombre/sufijo, dictado o fuente vacía. Guardado local técnico revisado ya autorizado; no casos, IDsclientes, PII, secretos ni logs crudos. Helper con validación/CAS/locks/atomicidad; cambios de asociación/conflictos requieren revisión.
- Evidencia local histórica: 25 tests PASS y carga de skill en OpenCode. No se repiten tests ni se acredita estado remoto nuevo por leer este archivo.

## Lo aprendido de las pruebas AWS y latencia

1. Fechas alrededor del reporte dejaron fuera referencias anteriores: se corrigió la metodología, no se confirmó una fecha real de fallo.
2. El primer colector omitió su resumen al alcanzar el límite de salida; podía seguir llamando. Solo21 de hasta25 llamadas quedaron auditables. Se reservó el presupuesto potencial completo; no inventar saldo.
3. La prueba inline posterior conservó todas las cuentas:18llamadas,229eventos con duplicados, blue8/green8/prod1+STS. Se corroboraron consultas Backoffice con respuesta200, no la causa del rechazo del cliente. Algunos matches numéricos eran campos como duration, no el préstamo. Cobertura histórica parcial; no confundir cantidad de consultas con cronología completa.
4. Rendimiento de esa prueba:20m07s hasta la auditoría local,62.79s acumulados de AWS CLI,3m10s antes de la primera llamada. La entrega sumó cierre. Sin delegación no hubo mejora suficiente: preparación/parseo ad hoc entre llamadas siguió siendo el cuello. No culpar CloudWatch, no prometer dos minutos, no comparar recorridos distintos como benchmark controlado.
5. Fuente operacional: CLI AWS oficial ejecutado en el host mediante Python/argv estructurado y buffers privados; no backend Efren Bot, AWS Lambda, nueva API de IA ni Boto3. Auth SSO nativa del CLI; no leer/copiar tokens. Última identidad comprobada2026-10-25T20:31UTC; **no garantiza vigencia al retomar**. Ahora no hacer STS ni pedir login: AWS está diferido, no bloqueado por IAM.

## Documentos y evidencia para retomar

- [slack-first-journey.md](slack-first-journey.md): unidad activa de producto y aceptaciones conversacionales; contrato/admisión/persistencia/vista pendientes.
- [aws-support-investigation-readonly.md](aws-support-investigation-readonly.md): instalación, correcciones, pruebas, fallos recuperados y diferimiento de investigación/latencia. Leer entradas vigentes, no ejecutar recetas históricas.
- [slack-history-pilot.md](slack-history-pilot.md): colección y cobertura del archivo.
- [frontend-reset-and-system-map.md](frontend-reset-and-system-map.md) y [diagrama entregado](frontend-reset-and-system-map-diagram.html): frontend retirado y mapa conceptual, no interfaz nueva.
- [assistant-platform-design.md](assistant-platform-design.md): decisiones conceptuales; no implementación de una V1 completa.
- [base-local.md](base-local.md), [reglas del repo](../AGENTS.md), [contrato base](../docs/contract.md), [arquitectura base](../docs/architecture.md): preservar contratos y evidencia existentes.
- Archivo privado: `~/.local/share/efren-bot/research/slack/20261025T000658Z/`; expansión `thread-expansion-20261025T011719Z/REPORT.md` e índice `derived/messages-combined.jsonl`. No copiar cuerpos ni importarlo masivamente al repo.
- Plan OpenChamber «Primer recorrido real de Slack con ChatGPT», ID `d3eaea48-0e6f-4bae-a063-b2ed7aaecebe`, todavía0/4: sus criterios de producto exceden las pruebas del chat. Requiere conciliar el modo asistido antes de implementación; no revivir el login aislado ni eliminar condiciones para tildar pasos.
- Índices Engram opcionales:3991/4002 son espejos históricos;3999 estado de investigación;4016 método retrospectivo;4018 fallo de salida;4038 diferimiento. Si difieren, leer el estado local actual. No hacer ciclos de espejo completo ni delegar bookkeeping. No usar la memoria como diagnóstico del caso.

Los documentos y pendientes viejos de Claude bridge, mock/synthetic, n8n o pruebas de canal son historia, no la siguiente tarea. El backlog antiguo `ca65df3b-9682-42f1-994d-7f8a3a9d8301` de lectura vía Claude no se debe reactivar sin nueva petición: la vía elegida después fue esta sesión OpenAI.

## Mensaje sugerido para la nueva sesión

> Lee `.odd/session-handoff.md` y `.odd/slack-first-journey.md`. Retomemos el acuerdo del contrato del piloto asistido de un hilo Slack y su futura persistencia/vista mínima. Los ajustes CloudWatch y Git están diferidos. No ejecutes consultas, logins, servicios ni implementación por extensión; primero propón el contrato mínimo según las decisiones vigentes.
