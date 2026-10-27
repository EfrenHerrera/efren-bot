# Plan de incrementos y decisiones pendientes

**DRAFT · propuesta para revisión del usuario · 2026-10-24.** En el corte original
solo estaba autorizada la documentación; este plan no autorizaba implementación.
Después, el usuario seleccionó explícitamente «Sí, implementar A»: código,
migración, web y pruebas sintéticas en DB separada. Una ampliación posterior del
2026-10-24 autorizó y activó únicamente A en el runtime local. No activa ni aprueba
la plataforma completa. Ver el
[contrato y evidencia de A](../synthetic-work.md) y el [índice](README.md).

**Corte posterior · retiro web del 2026-10-24:** se eliminó la interfaz de simulaciones
y toda bandeja/panel/cliente/hook/proxy; la fuente web ahora es una página en blanco.
El backend A, workers y datos se mantienen. La lectura web y aceptación de botones
descritas en el corte anterior son históricas, no capacidades actuales. El despliegue
web vacío requiere aceptación separada. No se implementan B–F ni conectores por este
retiro; revisar el sistema completo precede a autorizar nuevos flujos.

## Forma de avanzar

Incrementos pequeños con resultado revisable, no una pipeline SDD fija ni una
promesa de construir todo el ecosistema de una vez. Cada incremento necesita objetivo,
archivos/repositorios permitidos, reglas aplicables, criterios y aprobación propia.
Mantener el backend demo y su evidencia histórica, no la UI retirada;
no renombrarlos como plataforma terminada.

La primera vertical propuesta fue **contrato + memoria durable + cola +
lectura web + ejecutor falso**, solo con datos sintéticos. La autorización separada
de A permitió implementarla de forma acotada a `request_video`, con decisión simulada
y reanudación comprobada en pruebas; la activación posterior también observó reinicio
del worker y recarga con contexto persistido, sin conectores reales ni efectos externos.
No autoriza B ni los siguientes incrementos: cada uno requiere aprobación propia.

## Incrementos candidatos

| Incremento | Entregable revisable | Dependencias | Alcance que habría que autorizar |
| --- | --- | --- | --- |
| A. Vertical sintética — backend implementado y activo localmente; UI retirada después | Modelo de trabajo, historia/decisiones, cola y checkpoint con ejecutor falso; lectura web solo histórica; [contrato acotado](../synthetic-work.md) | Contrato específico de A; no aprobación global del DRAFT | Código/tests en DB separada; ampliación adicional del 2026-10-24 para backup privado, migración principal aditiva y activación local observada. Retiro web posterior sin efectos sobre backend/datos |
| B. Coordinación y control | Dos jobs aislados, espera sin ocupar cupo, policy/skill enforcement y aprobaciones falsas | A, criterios de capacidad y aislamiento | Scheduler, ejecutores de prueba, perfiles revisados y simulación de fallos |
| C. Piloto host de lectura | Una fuente/entidad allowlisted, evidencia mínima y revocación | A/B, decisión explícita sobre reglas de fuentes reales | Adaptador oficial read-only y prueba fail-closed, sin publicaciones |
| D. Preparación de código | Tarea Notion exacta, repo autorizado, entorno aislado, diff y checks | B/C, clave real y política del repo | Lectura/edición y Git/topología específicos; no asumir permisos del host |
| E. Publicación controlada | Acción aprobada, ejecutor separado, confirmación/reconciliación | B/D y permiso del destino | Cada conector/operación por separado: registro Notion, push/MR o Slack |
| F. Retrospectiva y recuperación | Explicación tras reinicio/cambio de motor y lecciones DRAFT | Evidencia de incrementos anteriores | Evaluación y revisión humana; ninguna edición automática de reglas |

La indexación semántica es opcional y posterior a memoria exacta evaluada. Puede
proponerse dentro de otro incremento si demuestra utilidad; no bloquea A/B ni viene
incluida en «tener pgvector». Requiere decisión de modelo local, dimensión, datos,
presupuesto, ACL, retención y pruebas de borrado/reconstrucción.

Una integración Notion de lectura no autoriza crear tareas. Una rama local autorizada
no autoriza commit/push. Publicar un MR no autoriza comentar Slack ni cerrar una tarea.
El orden puede ajustarse con revisión; las dependencias de seguridad no se omiten.

## Criterios de aceptación futuros

Son criterios de plataforma, no una lista de logros de A. La evidencia sintética
acotada de A consta en su [ledger](../synthetic-work.md#evidencia-de-comprobaciones);
no acredita completos los criterios compartidos con B/C/D/F ni efectos remotos.
Los alcances futuros siguen pendientes y son obligatorios por criterio si el
incremento correspondiente se autoriza, además de las reglas del proyecto.

| Criterio | Evidencia mínima futura | Incremento |
| --- | --- | --- |
| Reanudación durable | Reinicio conserva IDs, motivo, checkpoint y próximo paso permitido | A/B |
| Recuperación exacta | KNF, página y MR exactos no se sustituyen por similitud | A/C/D |
| Ingesta duplicada | Misma identidad/contenido no duplica job; conflicto distinto queda explícito | A/C |
| Dos jobs y una espera | Uno espera persona y libera cupo mientras otro progresa sin mezclar contexto | B |
| Propietario obsoleto | Intento con fencing vencido no confirma resultado ni inicia efecto nuevo | B/E |
| Cancelación | No admite efectos nuevos; conserva confirmados y reconcilia los inciertos | B/E |
| Revocación de permiso | Job en espera no reutiliza snapshot aprobado para eludir bloqueo vivo | B/C/E |
| Cambio de contenido | Cambiar diff/destino/base relevante invalida aprobación antes del efecto | B/E |
| Resultado remoto desconocido | Se reconcilia antes de repetir; no duplica tarea Notion, MR o Slack | E |
| Aislamiento | Jobs no comparten checkout/rama mutable; no heredan credenciales globales | B/D |
| Datos no son instrucciones | Texto de fuente no amplía tools, allowlist, rol ni presupuesto | B/C |
| Memoria explicable | Resultado incluye alternativas, porqués, checks fallidos y pendientes | A/F |
| Vector seguro, si se incorpora | ACL y revocación impiden recuperación; borrar propaga y rebuild no resucita datos | Incremento semántico por autorizar |
| Cambio de motor | Se reconstruye el encargo sin conversación oculta ni pérdida de auditoría | F |

En efectos remotos, la prueba debe contemplar caída entre envío y confirmación,
no solo un error antes del envío. Si el proveedor no permite verificar duplicidad,
el criterio exige bloqueo/revisión humana y límite explícito, no inventar exactly-once.

## Protocolo de comprobaciones

Antes de **cada** ejecución, clasificarla como obligatoria por criterio/proyecto u
opcional e indicar fuente, alcance y efectos esperados. Registrar comando/operación,
entrada sintética o autorizada, resultado exacto y pendientes. Conservar la secuencia
fallo → corrección → reintento → resultado; no sustituirla por el último verde.

Pruebas de DB siempre en base separada. Compose válido, lock resuelto o modelo falso
no acreditan runtime real, enforcement del cliente oficial ni permisos de publicación.
Una comprobación opcional de rendimiento/ergonomía debe declararse como tal, con
fuente de la hipótesis, antes de ejecutarse; no convertirla después en gate retroactivo.

Para la entrega documental original, las comprobaciones obligatorias son enlaces/anchors
locales añadidos, siete contratos DRAFT, consistencia de identidades/permisos y
preservación del trabajo ajeno. Los enlaces externos solo se inventariarían en un listado
de URLs presentes para inspección documental, **sin HTTP**; no crear fuentes nuevas.
No corresponden tests de runtime, DB, instalaciones, Docker, npm ni activación de skills.

Esta actualización de estado solo comprueba enlaces/anclas locales y consistencia
documental con el alcance A y la activación ya observada; no repite ni sustituye las
pruebas de implementación ni vuelve a ejecutar runtime/DB/Docker. URLs externas se
inventarían sin HTTP. Las suites históricas usaron DB separada; la aceptación de
activación fue un recorrido sintético autorizado por API/web y lecturas SQL de
preservación, nunca tests o TRUNCATE contra la principal.

## Decisiones abiertas

- Ampliación del almacenamiento y API de expedientes más allá del contrato sintético A,
  sin romper el contrato fixture.
- Motor/orquestador y frontera de proceso capaz de aplicar permisos, no solo prompts.
- Concurrencia, prioridades, fairness, budgets y operación del host suspendido.
- Fuentes y repos concretos, allowlists, consentimiento y revisión de reglas vigentes.
- Propietarios/revisores del registro de skills y proceso de activación/revocación.
- Política de aprobación por destino, vigencia y cambios relevantes que la invalidan.
- Política de cierre administrativo/técnico y actualización Notion sin campos deprecados.
- Dudas de esquema/workflow Notion y políticas MR realmente aplicables por repositorio.
- Retención, eliminación, derivados y copias; modelo/dimensión/proveedor local de embeddings.
- Selección o descarte de n8n; no es una dependencia aprobada ni un servicio a restaurar.

No hay metas numéricas de respuesta aprobadas ni promesa 24/7. Las hipótesis previas
de cadencia o métricas requieren revisión y medición antes de convertirse en compromisos.

## Límites de entrega y siguiente decisión

Esta documentación no acredita por sí misma permisos reales ni implementación.
A sí tiene código/pruebas sintéticas y activación local por autorizaciones separadas;
no conectores, memoria vectorial ni jobs remotos. La principal está en
`0003_synthetic_work`, API/web fueron reconstruidos/recreados y `work-worker` está
iniciado por Compose. La aceptación observó `waiting_human`, reinicio solo de ese
worker y recarga con detalle idéntico, aprobación exacta y `delivered`/`succeeded`
(2 intentos, 0 fallos). Ocho tablas originales y cuatro servicios protegidos se
conservaron. El backup privado tiene inventario verificado, **no restauración probada**.
Ver [evidencia de activación](../synthetic-work.md#activación-local-autorizada--2026-10-24).

Esta evidencia acredita solo el recorrido sintético local observado, no cierre global
de features anteriores ni disponibilidad 24/7. Los checks documentales no son un diff
Git aislado ni revisión formal. Riesgo exact-delta/judge y entrega Git siguen diferidos
en el checkout con trabajo histórico, sin declarar verified/done global.

Git sigue sin autorización: nada aquí permite staging, ramas/worktrees, commits o push.
La activación local de A ya autorizada no concede nuevos despliegues ni B–F; cualquier
otro alcance necesita permiso explícito y comprobaciones propios. La visión de
plataforma permanece DRAFT, no activada.
