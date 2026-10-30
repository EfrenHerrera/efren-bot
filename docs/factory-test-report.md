# Prueba local de actualización de la fábrica

## Alcance de esta ejecución

Main actualizado a `23b6fe6`. Autorización posterior del usuario: «okay con esto podemos
proceder con la acutlizacion.» Se procede solo con ensayo simulado y actualización local
condicionada a sus resultados. Sin fuentes/efectos reales ni reanudación de los runners
preexistentes detenidos. No corregir código para forzar una prueba verde.

## Etapa 0 — bloqueada

Comprobaciones obligatorias por `docs/factory-test-plan.md`, etapa0:

- Python3.14.6, uv0.11.28, Node26.0.0 y Go1.26.5 observados.
- Docker29.9.2 accesible; API/db/test-db/web propios en ejecución, API/DB saludables.
- CLIs presentes: OpenCode2.1.4 y Claude Code2.1.310. Solo se consultó versión;
  autenticación y ejecución real no verificadas.
- Binario instalado: `/Users/efren.herrera/go/bin/scraft-ops`.
- `scraft-ops factory --help`: **FAIL**, exit2, `unknown command "factory"`.
  Salida conservada en `.local/factory/validation/scraft-factory-precondition.log`.
  La ayuda del binario instalado no anuncia el subcomando requerido.

No se construyó ni instaló scraft-ops ni se modificó su repo/configuración global.
La precondición de una unidad de ejecución compatible queda pendiente.

## Etapas siguientes

Etapas1–8: **no realizadas**. No se ejecutó `factory-rehearsal`, no se migró la base
principal a0011, no se recrearon API/web ni se iniciaron workers o conexiones.
No hubo publicaciones, agentes reales ni efectos externos.

## Para continuar

Proporcionar una ruta a un binario actualizado con `factory run`, o autorizar expresamente
su preparación desde el repositorio scraft-ops. Después retomar etapa0 y ensayo simulado
con `SCRAFT_OPS_BIN` explícito y TESTDB. No omitir pruebas cross ni sustituirlas por mocks
para declarar aceptación. Conservar este intento y añadir resultados posteriores.

## Recuperación de la dependencia — actualización autorizada

Usuario: «en scraft-ops actualiza el remote baja los cambios y reinstalalo».
Repo localizado en `/Users/efren.herrera/Downloads/scraft-ops` (no en la ruta histórica
workspace/scraft). `main` limpio, pull fast-forward `ada0df5`→`ba1d4b1` desde su origin
existente. Sin cambiar URL, ramas, commits ni código.

Comprobaciones obligatorias por reglas Go y README de instalación:
- `gofmt -l` sobre fuentes Go: PASS, sin modificar fuentes.
- `go vet ./...`: PASS.
- `go test ./...`: PASS, incluidos factory/cli; parte de los paquetes usó caché Go.
- `go install ./cmd/scraft-ops`: PASS. Metadata del binario: revisión
  `ba1d4b109a5c20fd4508e3de22c356b44aaff886`, `vcs.modified=false`.
- `scraft-ops factory profiles`: PASS, lista frontend/lambdas/orchestrator-multirepo.
- `install --dry-run` revisado, después `install` y `doctor`: PASS para OpenCode/Claude Code.
  Segundo dry-run sin nuevas escrituras previstas. El instalador mantuvo opciones guardadas
  y volvió a ejecutar instalación de AnyDoc y Archify ya habilitados; sin limpieza de huérfanos.
- Sondeo adicional `factory run --help`: responde `flag: help requested`; no cuenta como
  prueba de ejecución ni reemplaza `factory-rehearsal`.

Logs en `.local/factory/validation/scraft-{vet,tests,install-dry-run,install,doctor,
install-after}.log`. El fallo previo exit2 se conserva como intento anterior.
El bloqueo por subcomando ausente queda resuelto; el ensayo integrado Python/Go y
las etapas posteriores de Efren Bot continúan pendientes. No se migraron bases ni
se reiniciaron sus servicios o runners durante esta reinstalación.

## Ensayo y actualización local — continuación aprobada

Usuario: «okay ya con esto, puedes comenzar?».
Base efren-bot23b6fe6, scraft-opsba1d4b1; Python3.14.6/uv0.11.28/Node26.0.0.
Comprobaciones clasificadas obligatorias antes de ejecutarse, según guion y Makefile.

| Etapa | Resultado de esta continuación | Evidencia |
| --- | --- | --- |
| 0 | Dependencia recuperada; herramientas disponibles. Agentes reales/autenticación no probados. | Logs scraft previos; `factory profiles` reconocido |
| 1 | PASS: ensayo87 pruebas, cero omitidas; suite global646 Python,33 web,1 Node PASS. | `rehearsal-attempt-1.log`, `test-attempt-1.log`, `node-attempt-1.log` |
| 2 | PASS acotado:0011/API-web/health200 y vista vacía real escritorio/móvil. Registro de proyectos vacío. | `deployed-acceptance.json`, capturas |
| 3 | No realizada manualmente. Firma/webhook cubiertos por dobles automáticos, no conexión Meta. | Sin evidencia de conexión real |
| 4 | No realizada: ninguna lectura nueva Slack/Notion ni tabla de10 pedidos reales. | Pendiente de alcance/configuración |
| 5 | No realizada con agente real. Ensayo cruzado usó binario real y agente falso. | No acredita headless real ni checks npm en worktree nuevo |
| 6 | Guardias probadas automáticamente; ejercicio manual con jobs/efectos en pantalla pendiente. | Vista local sin datos sintéticos; tests no equivalen a esa aceptación manual |
| 7 | No realizada: cero efectos reales. | Pasarela recording, ningún worker host iniciado |
| 8 | Sin runs de agentes reales por perfil. | Perfiles idénticos contrastados automáticamente, no aceptación runtime real |

También PASS: `make check` (Compose, Ruff/check-format, npm ci, typecheck/build),
`make sync`, `make test-db`. Variables explícitas `SCRAFT_OPS_BIN` y
`FACTORY_AGENT_EXECUTOR=fake`, `FACTORY_GATEWAY=recording`; integración en55433/efren_bot_test.
Advertencia existente Starlette/httpx sin modificar dependencias. No falló ninguna prueba
de esta continuación; el fallo previo del binario permanece registrado arriba.

### Despliegue y preservación

Antes de migrar se guardaron conteos y checksum de33 tablas. Tras migrar0010→0011,
las32 tablas previas distintas de Alembic tienen contenido idéntico: incluidos fuentes,
informes, anotaciones y controles. Las cuatro tablas nuevas factory tienen cero filas.
No se insertó simulación en principal ni se tocaron cortes o disposiciones humanas.

Solo se construyeron/recrearon API/web con `--no-deps`, usando compose.yaml más
compose.factory.yaml. Migración ejecutada como servicio one-shot con `--no-deps`.
No se usó `make up`, evitando iniciar los workers fixture/work por arrastre.
Registry propio ignorado `.local/factory/projects.json`: `{"projects":[]}`, readonly.
Desviación explícita del guion2: no se apuntó a repos sandbox todavía; no se inventaron
proyectos ni se dio acceso a los repos corporativos existentes.

Comprobación HTTP real: health200, factory/list con sesión200 y vacío; sin token401.
API con gateway recording, sin secretos Notion/WhatsApp, sin montajes de credenciales.
Ningún proceso collection/support/review/factory visto al final. Interfaz real solo
comprobada vacía: no adjudicar aprobación, pausa, reorientación ni ejecución reales.

### Evidencia local

Directorio `.local/factory/validation/`: logs de sync/test-db/rehearsal/check/test/node,
build-local/migrate-local/deploy-local; `inputs.json` (hashes de entradas/binario),
`baseline-before.json`, `deployed-acceptance.json`. Hashes de entradas comprobados sin
cambios entre pruebas y aceptación. Artefactos privados, no commits ni push nuevos.

Capturas observadas:
- `.openchamber/screenshots/factory-desktop-empty-2026-10-28T03-54-32-726.jpg`
- `.openchamber/screenshots/factory-mobile-empty-2026-10-28T03-54-42-810.jpg`

### Límites y observaciones pendientes

La fábrica no se declara lista para operar fuentes/agentes/efectos reales: faltan etapas
reales, topes de costo, orden entre repos y setup por perfil documentados en factory.md.
La interfaz dice «Nada se publica sin que apruebes» pero el contrato admite efectos auto
en determinados perfiles/riesgos; ese mensaje absoluto requiere aclaración antes de
pruebas con efectos reales. Observación de presentación/contrato, no publicación ocurrida;
no se cambió código ni política durante esta aceptación.

## Piloto banners WC — preparación de etapa5, bloqueada

Usuario aprobó probar el requisito de Slack C07SRBE0V1T/1792701231.534479:
«La página no espera a los banners: si `wc-banners` falla o tarda, la sección se pinta igual».
Copia aislada elegida, después main remoto y finalmente revisión !1351 expresamente
autorizada al comprobar que main no tenía la integración visual. Sin fuentes nuevas,
sesiones reales, CMS real, publicaciones ni cambios al checkout original.

- Main sandbox `cb35ae05dfe9629cd4ac56daa7fa0aac1c4ded05`: solo capa de datos,
  sin consumidores de useGetWcBanners en apps/packages. No acredita prueba de UI.
- !1351 consultada con glab: abierta, target main, SHA
  `5a8e44b8c8b37002d10f9e63434dca407d358590`. Fetch de esa referencia exacta y
  checkout detached en sandbox, sin remoto configurado. Sí contiene integración y
  `credito-banners.cy.ts` para éxito/fallo/lentitud; inspección estática, no PASS runtime.
- Preparación obligatoria: Node22.23.1/pnpm10.3.0 (stack del monorepo, no Node26 de
  Efren Bot). Perfil frontend genérico npm/--if-present no acredita sus checks reales.
- `pnpm install --offline --frozen-lockfile --ignore-scripts --filter @app/working-capital... --filter @e2e/working-capital-e2e...`:
  **FAIL exit1, ERR_PNPM_NO_OFFLINE_TARBALL**, falta `@konfio/design-system@1.18.0`.
  Sin tokens heredados, userconfig /dev/null; descargados0; sin fallback online,
  cambio de lock/versiones ni scripts. Árbol fuente continúa limpio.

Evidencia en `.local/factory/pilot-banners/install-offline{.log,-result.json}`;
autorizaciones y continuidad canónica en `.odd/factory-banners-pilot.md`.
Sin agente real/JobSpec/admisión/servidor/E2E/capturas ni datos piloto en principal.
El bloqueo vigente es la dependencia privada ausente; luego falta aislar CMS de servidor
y red (intercepts de navegador no cubren CmsService de la página). No corregir producto
para forzar verde, no pedir tokens por chat. Original permanece en su tarea, intacto.
Etapa5 sigue **sin verificar** y las demás etapas no avanzan por esta preparación.

### Recuperación del bloqueo de dependencias del piloto

Usuario autorizó intentar la instalación online con la autenticación existente del host.
Mismo comando sin `--offline`, SHA5a8e44b8/Node22.23.1/pnpm10.3.0,
`--frozen-lockfile --ignore-scripts`: **PASS exit0**, pnpm reportó30.4s.
1404 paquetes añadidos,1382 reutilizados y1 descargado en salida final; árbol fuente
limpio. No se cambió el token ni se copiaron secretos. No demuestra vigencia futura
ni permisos de otras operaciones. Fallo offline anterior conservado.

Evidencia sanitizada: `.local/factory/pilot-banners/install-online-attempt-1.log`
y `install-online-attempt-1-result.json`. Bloqueo de dependencias resuelto para la copia;
CMS/red, lifecycle necesarios, worktree/perfil, agente real y E2E continúan pendientes.
Etapa5 permanece sin verificar: instalación no equivale a ejecución del requisito.

### Pruebas del piloto solicitadas — ejecución sobre !1351

Base SHA5a8e44b8, Node22.23.1/pnpm10.3.0; checks clasificados obligatorios antes
de ejecutarse. Código y suite de la MR sin cambios; sin credenciales reales en runtime.

| Check | Resultado observado | Evidencia en `.local/factory/pilot-banners/` |
| --- | --- | --- |
| Unitarias WC | PASS11suites/128tests, sin suite vacía | `unit-attempt-1.log`, `unit-attempt-1-result.json` |
| Tipos WC | PASS | `types-attempt-1.log` y resultado |
| Lint WC | PASS0errores/0warnings | `lint-attempt-1.log` y resultado |
| E2E banners desktop | PASS5/5,0omitidos,retries0 | `e2e-desktop-attempt-3.log` y resultado; vídeo en subdirectorio |
| Build WC | PASS con CMS simulado, no despliegue | `build-attempt-1.log` y resultado |

E2E cubre sin banner,fecha interpolada,oferta,502 y demora3000ms. Cypress15.13.0
con Electron37.6.0,viewport1200x800. Servidor127.0.0.1:3109.
Unitarias bajo sandbox nativo deny-network; E2E/build solo loopback,verificado con
prueba de localhost permitido/exterior EPERM. Story CMS exacto respondido por mock
HTTP fuera de fuentes,reutilizando fixtures de tests existentes y labels sintéticos.
No se consultó Storyblok ni se sustituyó la pantalla real por otra aplicación.

Se conservan dos intentos de preparación fallidos:1)HTTP500 por ruta con doble slash
no prevista por el mock,corregido solo en el mock;2)Cypress exit1/0casos por tsconfig
del soporte adicional de capturas,retirado para usar soporte original. Intento3 pasó.
No se corrigió producto para verde. Vídeo:
`e2e-desktop-attempt-3/videos/credito-banners.cy.ts.mp4`.
Frames inspeccionados muestran Crédito/acciones mientras getWcBanners espera;
también404 locales de flags/sidebar y skeleton,no aceptación completa de ese shell.

Original y sandbox fuente intactos;servidor propio detenido. Sin publicaciones,datos
principal ni runners reanudados. No se probó móvil,CMS real,interacciones extensas,
agente real,JobSpec ni despacho por fábrica. **Etapa5 sigue sin verificar de extremo
a extremo**; estos PASS pertenecen a checks de la revisión aislada,no a toda la planta.

### Pedido → fábrica → ejecutor real — ejecución autorizada, bloqueada

Usuario autorizó continuar esa parte. Pedido manual derivado del requisito Slack,
sin lecturas Slack nuevas ni cambio al registry principal. TESTDB55433,schemas
aditivos propios factory_banners_pilot_20261028a/b,solo cuatro tablas factory por
schema,sin truncar el public compartido. FactoryService.ingest/process_one reales,
ScraftOpsExecutor/binario real y ejecutor Claude predeterminado;sin fake agent.
Perfil local pnpm,checks obligatorios reales y todos los efectos forbidden,pasarela
RecordingGateway. Scope del agente:solo nuevo spec causal,sin UI ni lógica producto.

Preflight del driver tuvo dos problemas conservados:brief operativo mezclado con
pedido disparó rol research/inbox por texto de instrucciones;pedido concreto separado
de metadatos/proveniencia dio admit/development,sin cambiar política. ImportCreateSchema
mal ubicado en driver de ensayo se corrigió a sqlalchemy.schema antes de DB/agente.

| Tramo | Resultado observado |
| --- | --- |
| Admisión de pedido explícito | PASS,policy admission/1,proyecto/rol development resueltos |
| Repetición de contenido | PASS,duplicate=true,sin segundo job en cada schema |
| Cola y claim | PASS,un intento por job |
| Worktree de unidad | PASS,branches factory/* en copia aislada desde5a8e44b8 |
| Primer lanzamiento | FAIL antes de CLI:PATH del driver omitía ~/.local/bin |
| Recuperación del entorno | Ubicación instalada añadida,primer job fallido conservado |
| Segundo lanzamiento real Claude | FAIL exit1:individual spend limit;sin trabajo del agente |
| RunRecord → persistencia | PASS acotado:failed/requires_human almacenado,no éxito |
| Cambios/checks/risk/review del agente | No realizados,delta vacío;obligatorios pendientes |
| Publicaciones/efectos |0propuestos,0gateway calls;ninguna publicación |

Primer job4a85fa5d-50d0-4589-b996-841360847119,unidadfj-454b9bcfbf9d-a1.
Segundo job3ec9bd2f-28ec-46bf-ac82-b51ee8b17b64,unidadfj-583f19e01b3a-a1.
Segundo intento es otra solicitud de ensayo con recovery_of_job,no funcionalidad
de retry del producto ni reseteo manual del estado anterior. Cada schema conserva
1item/1admission/1job/0effects;cada job termina failed,attempt_count1.

Error literal del segundo execute.log:
`You've hit your individual spend limit · run /usage-credits to ask your admin for a higher limit`.
No implica fallo de GitLab ni permite afirmar modelo/herramientas cargados. No nuevo
reintento,cambio de proveedor/modelo ni fallback. Fuente y original intactos,ningún
worker general arrancado,puerto3110 sin listener. Etapa5 continúa **bloqueada por cuota**.

Evidencia bajo `.local/factory/pilot-banners/factory/`:result/trace iniciales,
attempt-2/{result.json,trace.jsonl,queued-job-spec.json,agent-delta.patch},state/runs
y state/worktrees. Para retomar hace falta resolver cuota oficial del host o autorización
explícita de otro ejecutor,conservando fallos;no modificar fábrica para forzar PASS.

### Cambio posterior autorizado de ejecutor y respaldo

Usuario pidió OpenCode principal y autorizó Claude como respaldo,además de cambios
acotados en Efren Bot/scraft-ops. Implementación local aditiva:policy.fallback_executors
y RunRecord.execution_attempts,allowlist explícita,sin fake→real,con guard de worktree
limpio y sin repetición ante timeout,cancelación,logs truncados,errores de código o
checks fallidos. Presupuesto de tiempo compartido;revisión fallida sigue para humano.
Frontend usa OpenCode V2 sin --dir/--variant;revisión conserva texto,build usa JSON.
Config global se fija en jobs nuevos,no cambia la selección de un job ya encolado.

Pruebas finales de implementación (no son nuevo trabajo del agente de banners):
109ensayo sin omisiones,incluyendo6casos planta→binario real→CLIs dobles→DB;
668Python+38web,make check,Go gofmt/vet/suite PASS. No cuentas reales utilizadas.
Binario solo `.local/factory/executor-fallback/bin/scraft-ops`;logs *-final.log en
ese directorio padre. Los RED iniciales y de las dos guardias adicionales se conservan.

Etapa5 del piloto real **sigue sin completarse**:no relanzamiento tras cambio ni
instalación global/despliegue/runners. Risk-assess omitió3archivos Go untracked y
Efren Bot tiene delta previo mezclado;riesgo completo/revisión formal pendientes,
no aprobar por el medium parcial. Fuente canónica .odd/factory-executor-fallback.md.
Registro local del piloto opencode→claude preparado;registry principal vacío intacto.
