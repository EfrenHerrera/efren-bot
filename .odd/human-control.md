# Control humano común

## Autorización y límite

Usuario: «Ok, procedemos con tu recomendación.» Recomendación aceptada: primera entrega
del plan OpenChamber9c4cf2c3-2a36-4b3f-99ef-e56bb8191fa2, bandeja común y barreras reales;
no implementar sus pasos4/5 ni reanudar procesos. Política confirmada: «Exactamente,
estoy muy de acuerdo con lo que planteas». No pedir permiso por cada lectura aprobada.
No nuevas fuentes, ejecutores, publicaciones reales, Git, credenciales ni código de MRs.
Soporte cancelado manualmente permanece detenido. Solo API/web locales afectados pueden
desplegarse; migración aditiva propia, pruebas DB siempre TESTDB separada.

## Estado y decisiones

Base0009; API/web disponibles, collection pausado, tres heartbeats no recientes.
Soporte solo Slack, MR estático acotado, tres demos partial; sus fuentes/reportes intactos.
No index Codegraph/.ath: lectura dirigida, no infraestructura incidental. Checkout
histórico totalmente untracked: delta/riesgo formal pendiente, sin improvisar Git.

Reutilizar servicios, revisiones, controles globales, propuestas y colas existentes.
Complementos necesarios: tablas de disposición/auditoría, migración0010, guardias en
claim/finish y antes de nuevas lecturas MR, API local protegida y pestaña unificada.
No convertir fixture/work en tareas reales ni reemplazar identidades de dominio.
UUID internos nativos/JSON string; referencias externas opacas y columnas compuestas.

Disposición por caso support UUID y por MR exacta (scope,project_path,iid), compartida
entre reentregas de la misma MR en ese scope. Activa/pausada/ignorada/delegada/detenida;
disposición no equivale a conclusión ni resolución remota. Revisiones propias y epoch
invalidan trabajo en vuelo y autorizaciones obsoletas. No deshacer un envío ya admitido.
Acciones importantes usan propuestas existentes: publicar comentario MR solo cuando
ya estaba permitido, con contenido/destino/versión/vigencia exactos; demo siempre deny.
Publicar Slack/ejecutar pruebas/cambiar código/nuevas fuentes permanecen bloqueados.
Denegar conserva la decisión; ninguna aprobación crea un adaptador inexistente.
No iniciar publicación desde la aceptación: solo dobles. Preguntas activas no reinician;
una disposición detenida/delegada no puede deshacerse desde los controles antiguos.

## Unidades y aceptación obligatoria

Contrato/modelos/política → integración ejecutores y API → bandeja ligera → aceptación.
Pruebas RED→GREEN: versionado/idempotencia, delegado en vuelo, repetición, bypass HTTP,
reanudación explícita, cancelación, aprobación caducada/obsoleta, reinicio e incertidumbre;
soporte sintético y MR fixture/demo, cero red/escrituras remotas. Guardias antiguas
compatibles y controles globales sin arrancar procesos. Frontend conserva evidencia y
campos humanos, no permite aprobar capacidades inexistentes, estados disponibles vs
habilitados diferenciados. Checks globales obligatorios AGENTS/Makefile y navegador
escritorio/móvil. No declarar verified/done por el gate formal pendiente.

Plan: se marcarán solo pasos realmente terminados; paso3 incluye acuerdo de reanudación
que sigue separado y no se presume. No modificar otros puntos del plan al marcarlo.

## Checkpoint de continuación — 2026-10-26

Implementados contrato0010, API, guardias en colas/resultados/GET y bandeja común.
RED inicial por módulo ausente; primer pase7 humanos PASS, luego4 errores lint.
Corregidos; continuación detectó5 fallos (fixtures sin estado opened y cancelación entre
hermanos/recover); corregidos. Focal posterior47 backend PASS,5 UI PASS y typecheck PASS.
Se ampliaron después guardias de clasificación tardía/fase y detalle técnico/confirmación
con posición y refs: resultados globales frescos aún pendientes para esta versión.

Decisiones humanas invalidan también hermanos de misma identidad; continuar solo encola
el seleccionado. Preguntas y autorizaciones no admitidas quedan canceladas. Callback por
GET comprueba MR consultada además del trabajo actual. Recover impide nuevas lecturas
de jobs fallidos. Disponibilidad de aprobación considera pausa global y publicación previa;
fingerprint no depende de esos estados operativos. Ningún runner se ha reiniciado.

Falta: checks globales, revisión navegador, preservación/migración principal y despliegue
solo API/web. Gate formal riesgo sigue pendiente: todo el checkout histórico untracked,
sin autorización de aislamiento Git ni enfoque de entrega alternativo. No declarar cierre
formal. Pasos4/5 del plan no iniciados; reanudación operativa requiere otro acuerdo.

## Checkpoint local entregable — 2026-10-26

Contrato y bandeja implementados; primeros2 pasos del plan marcados. Paso3 abierto
porque reanudación operativa no acordada; pasos4/5 intactos. No cierre formal mientras
riesgo/revisión estén pendientes por delta untracked. Git permanece sin tocar.

Comprobaciones obligatorias por AGENTS/Makefile/aceptación:
- `make check` PASS, intento2: Compose, Ruff/check-format, npm ci/tipos/build.
- `make test` PASS, intento3:415 unitarias+144 integración(TESTDB)=559 Python;29 web.
- Node failure.test.mjs PASS1.19 pruebas nuevas humanas y5 UI incluidas en globales.
- Intento global2 falló en test de paginación histórico(total4 vs3). Sin tocar collection:
  focal repetido PASS y global3 PASS. Causa no confirmada; conservar el fallo, no ocultarlo
  ni atribuirlo a control humano. Advertencia Starlette/httpx sigue sin cambiar dependencia.

Logs: `.local/human/{make-check-attempt-2,make-test-attempt-2,paging-retry-1,
make-test-attempt-3,node-attempt-3}.log`. Python3.14.6/uv0.11.28/Node26/npm11.12.1.
Cobertura temporal parcial: timestamps/duraciones observados de herramientas; sin
medición completa del tiempo de la iniciativa ni estimación inventada.

Principal0010; solo API/web recreadas con `--no-deps`, sin reiniciar ejecutores. Baseline
y aceptación: `.local/human/{baseline-before,deployed-acceptance}.json`;30 tablas previas
con conteo/checksum idénticos excepto Alembic. Tres MR partial1/2/2 intactas,0 propuestas,
0 decisiones humanas sintéticas en principal,0 publicaciones,0 fuentes nuevas.
Health API200 y bandeja real escritorio/móvil. Borrador local sobrevivió cambio de pestaña
y fue limpiado sin enviarlo. Evidencia técnica cerrada por defecto, estados/capacidades
separados. Capturas `.openchamber/screenshots/human-{desktop-detail,mobile-detail}-*.jpg`.

Estado de procesos comprobado: collection pausado, soporte/MR habilitados pero sin
ejecutor confirmado; pgrep no mostró runners de esos dominios. No convertir esos flags
en afirmación de operación automática. Siguiente decisión del usuario: qué procesos
reanudar, tras mostrar colas/cortes/novedades; sin resets ni barrido histórico. Riesgo/Git
continúan en su pendiente existente; no inventar base ni delegar un review sustituto.
