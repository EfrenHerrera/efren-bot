# Solicitudes y decisiones

Una disposición humana no es una conclusión ni la resolución del problema original.
La capa común referencia casos de soporte y MRs; conserva sus colas, evidencia y reportes.
Fixture/work no participa. La política se aplica también desde rutas antiguas y el host.

Puede atender/continuar, reorientar, pausar, ignorar, delegar o detener. Delegar/ignorar/
detener impide nuevas operaciones y resultados obsoletos; no deshace efectos ya enviados.
Continuar es explícito, versionado y no inicia el proceso host ni amplía acceso.
Una decisión sobre MR afecta su misma identidad exacta de workspace/proyecto/iid para
que una nueva solicitud Slack no reactive trabajo delegado. No se infiere delegación
ni resolución por texto ambiguo de Slack.

La publicación GitLab existente requiere propuesta/cuerpo/ref/versión concretos y
vigencia limitada; la demo nunca publica. Esta entrega no habilita publicar en Slack,
ejecutar código/pruebas, modificar fuentes o usar accesos nuevos. Si falta capacidad,
se muestra bloqueada, no se transforma aprobación en permiso genérico. Aceptación sin
envíos reales: solo casos aislados y transportes dobles.

La reanudación global de procesos es una decisión separada: mostrar cortes, colas y
disponibilidad antes de acordarla. No resetear cortes, borrar pendientes ni barrer historia.

## API y vigencia

Migración aditiva `0010_human_control`: disposiciones e historial inmutable, sin alterar
fuentes ni tablas fixture/work. Rutas POST locales protegidas por las mismas barreras
Host/Origin/sesión/JSON/no-store que collection:

- `human/list {}`: hasta100 solicitudes por dominio, capacidad y heartbeat por separado.
- `human/detail {domain,id}`: resumen, informe/evidencia e historial humano compartido.
- `human/act {domain,id,request_id,revision,control_revision,action,text="",proposal_id=null,fingerprint=null}`:
  atender/continuar/reorientar/pausar/ignorar/delegar/detener o aprobar/denegar una propuesta.
  Versiones obsoletas y reutilización de request_id con otro contenido se rechazan.

La aprobación GitLab dura15 minutos y está ligada a cuerpo, destino, posición, refs,
versión de propuesta, revisión del trabajo y revisión humana. Pausa global o publicación
ya solicitada deshabilitan otra aprobación sin alterar la identidad del contenido.
La denegación conserva su snapshot; no borra evidencia ni conclusiones.

Una decisión cancela preguntas/publicaciones en cola o running, nunca un envío admitido
como sending. Invalida también trabajos hermanos de la misma identidad MR; continuar
encola solo el trabajo seleccionado, no reactiva automáticamente sus hermanos pausados.
Antes de cada GET se comprueba tanto el trabajo actual como la disposición de la MR
consultada, incluso si era una dependencia. No se cancela una petición ya enviada.
Un recover invalida los jobs antiguos; una clasificación tardía no reemplaza el contexto
tras una decisión humana, aunque se haya vuelto a continuar.

La bandeja abre en Necesita decisión; permite ver conclusiones o delegadas/pausadas sin
arrancar procesos. Informe/evidencia técnica se despliegan bajo demanda. Las indicaciones
se conservan entre pestañas en memoria; si cambia la versión se exige revalidar el texto.
No se promete conservar borradores tras recargar o cerrar el navegador.

## Estado de la entrega local

Principal migrada a0010; solo API/web propias actualizadas. Las30 tablas preexistentes
(excluida la versión Alembic) conservan conteo y checksum; tres informes MR parciales
intactos, sin decisiones sintéticas en principal. Health API200, bandeja comprobada en
escritorio/móvil, borrador no enviado conservado al cambiar de pestaña. Evidencia privada
en `.local/human/deployed-acceptance.json` y logs de checks en el mismo directorio.

No se reinició ningún runner, no hubo publicaciones ni lecturas remotas nuevas. La
reanudación operativa y evaluación formal de riesgo/revisión siguen pendientes; esta
última requiere resolver el delta histórico untracked sin asumir autorización Git.
