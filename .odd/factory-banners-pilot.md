# Piloto aislado del requisito de banners WC

## Autorización y propósito

Usuario: «probemoslo.» Opción elegida: «Copia aislada de konfio-app-web (Recommended)».
Requisito literal del hilo Slack C07SRBE0V1T/1792701231.534479:
«La página no espera a los banners: si `wc-banners` falla o tarda, la sección se pinta igual.»
Piloto derivado de requisito real; no encargo nuevo ni pendiente vigente confirmado.

Copia sandbox del código real; respuestas simuladas de banner correcto/lento/fallido,
agente real por unidad factory si hay base y entorno aptos, E2E/evidencia visual.
No modificar checkout original, publicar, consultar CMS/API de negocio ni usar sesiones
o credenciales de aplicación. No sustituir código real por demo inventada para pasar.
No iniciar workers generales, releer Slack u otras fuentes ni copiar .env/HOME/tokens.
Git local únicamente para copia sandbox/worktree propios necesarios; no push/MR/merge.
El agente no hace Git/publicación; unidad factory controla su Git aislado.

## Evidencia inicial y dependencias

Original `/Users/efren.herrera/workspace/konfio-app-web` en
feat/KNF-79240-cuadro-accionario, HEAD712b453e8; untracked .ath/.codegraph/.odd existentes.
No modificar ni mover esos archivos. main local785c443205ce06272eb74aad754ac8fc9e6e850a,
fecha2026-10-16. Árbol main no tiene wc-banners; working-capital-e2e solo dummy.cy.ts.
CodeGraph existente consultado: no localiza ese flujo; índice del checkout distinto de main.
No prometer equivalencia con main remoto ni MRs de Slack.

Stack real: Node22, pnpm10.3.0/monorepo, no npm de perfil frontend genérico.
Perfil genérico usa --if-present: root no tiene typecheck/test; pasar esos comandos no
acreditaría pruebas. No debilitar perfil ni inventar checks para verde. Preparación por
perfil y paquetes privados pueden bloquear; fallos se guardan, no se corrige producto.

Prerrequisitos obligatorios (AGENTS fuente + guion fábrica): base que contenga el flujo,
entorno Node/pnpm adecuado y mocks sin autenticación real, checks exactos del workspace,
evidencia reproducible E2E y luego agente real acotado. Si falta código o entorno: parar
antes de admisión/ejecución y pedir revisión/ruta explícita; conservar intentos.

Estado: preparación; ningún trabajo admitido/ejecutado todavía. Registry global vacío
permanece intacto; pruebas nuevas no van a DB principal por inferencia.

## Findings & adjustments — 2026-10-27

Usuario eligió «Main remoto actualizado (Recommended)» ante la falta del flujo en
main local. Autorización acotada: leer main remoto únicamente desde el sandbox, no
tomar otra MR ni actualizar el checkout original. Fetch y fast-forward completados:
base sandbox `cb35ae05dfe9629cd4ac56daa7fa0aac1c4ded05` (27/oct), árbol limpio en main,
sin remotos configurados. No se descargó !1351. La evidencia inicial de main local
se conserva como historia y no describe la base actual.

[deterministic] Comprobación estática obligatoria por prerrequisito del piloto:
`git grep -n -E 'useGetWcBanners|use-get-wc-banners' -- apps packages` en el sandbox
devuelve solo la declaración en
`apps/working-capital/src/application/hooks/queries/use-get-wc-banners.hook.ts:14`.
La búsqueda de banners en la UI working-capital y su workspace E2E no tiene resultados.
Lectura de `use-credit-home.hook.ts` y `credit-home.organism.tsx`: composición de
préstamos/balance/acciones/drawer sin consumo del hook ni montaje de banner.
Sí existen contrato, servicio, mocks y pruebas de capa de datos de wc-banners.
Conclusión limitada a esta revisión: no está la integración visual necesaria;
no es un diagnóstico de producción ni evidencia runtime del requisito.

Estado actual: **bloqueado antes de ejecución**. Un E2E que solo verificase Crédito
sin una solicitud de banners real podría dar un verde vacuo. No se inventa UI, no
se instala nada ni se admite/despacha agente para forzar aceptación. Checks runtime
y evidencia visual obligatorios permanecen pendientes, no PASS. Excepción test-first:
sin el flujo objetivo en la base autorizada; evidencia alternativa estática anterior.

Node22 instalado (22.22.3/22.23.1), pnpm10.3.0 disponible. Scripts reales WC:
`check-types`, `lint`, `test:unit`, `build`; E2E `test:e2e`. Entorno/mocks/red aislada
aún no acreditados. Perfil genérico npm sigue sin ser válido para el piloto.

Original comprobado sin cambios: rama feat/KNF-79240-cuadro-accionario,
HEAD `712b453e84d315b2995266a0f8dcf512b5882986`, mismos untracked .ath/.codegraph/.odd.
Sin instalaciones, servidor, JobSpec, datos del piloto en principal ni publicaciones.

Siguiente paso: solicitar autorización para usar la revisión de !1351 exclusivamente
en el sandbox, o una revisión indicada por el usuario que contenga el flujo. Esa MR
es candidata por el mensaje Slack; su contenido/estado no se ha comprobado todavía.

## Findings & adjustments — base !1351 autorizada

Ante el bloqueo, el usuario eligió «Usar MR !1351 (Recommended)»: leer/traer su revisión
solo al sandbox y continuar si el flujo puede probarse con mocks, sin publicación ni
cambios al original. `glab mr view 1351 --repo <konfio-app-web> --output json` devolvió
MR abierta hacia main, rama feat/KNF-78204-wc-banners-top,
SHA `5a8e44b8c8b37002d10f9e63434dca407d358590`. Se hizo fetch solo de
refs/merge-requests/1351/head, se comprobó SHA exacto y checkout detached en la copia
limpia. El main remoto previamente obtenido permanece como referencia; no merge/rebase.

[deterministic] Esta base sí contiene useCreditBanners → useGetWcBanners y
CreditHomeOrganism → CreditTopBanner, con suite existente `credito-banners.cy.ts`
para éxito/vacío/502/lentitud de 3000ms. Esto no acredita runtime ni la suficiencia
temporal de las aserciones; no se ha ejecutado agente ni se acepta el requisito aún.

Preparación obligatoria antes de agente: dependencias reproducibles Node22/pnpm10.3.0,
comprobar que CMS de servidor y red de navegador pueden aislarse. Página real
`app/(dashboard)/page.tsx` llama CmsService en servidor; intercepts Cypress existentes
no demuestran aislamiento de esa llamada. `.npmrc` requiere tokens para paquetes
privados; no se copiarán secretos ni configuración. Primer intento de dependencias
será offline, lock congelado y sin lifecycle scripts, usando solo caché de host.

### Resultado de preparación: dependencia privada ausente

Comprobación obligatoria (prerrequisito del piloto; guion5a/setup real del workspace):
Node22.23.1 + pnpm10.3.0, desde `source`, sin tokens heredados y con userconfig
`/dev/null`:

```sh
pnpm install --offline --frozen-lockfile --ignore-scripts \
  --filter @app/working-capital... --filter @e2e/working-capital-e2e...
```

**FAIL, exit1**, `ERR_PNPM_NO_OFFLINE_TARBALL`: falta
`@konfio/design-system@1.18.0` en la caché. Lockfile reconocido como actualizado;
descargados0. El error señala el tarball privado del proyecto GitLab69265473.
No se hizo fallback online, no se leyó/copió token, no se cambiaron versiones ni
fuentes para forzar PASS. Evidencia `.local/factory/pilot-banners/install-offline.log`
y `install-offline-result.json` (comando, versiones, cwd y exit). Sin medición de
tiempo completa; no se estima. `git status --short` del sandbox sigue vacío.

El bloqueo por falta de flujo quedó resuelto con la MR autorizada; **el bloqueo
vigente es la preparación de dependencias**. Agente real, checks WC, E2E y capturas
siguen sin ejecutar. No avanzar al perfil/JobSpec ni a la planta antes de resolverlo.
Después seguirá pendiente aislar el CMS de servidor y comprobar el cierre de red.

Para retomar: disponer de la dependencia exacta mediante caché/preparación oficial
del host con acceso autorizado al registro, sin pegar tokens en chat ni copiarlos al
repo/Docker/logs; no usar versiones sustitutivas ni un design-system inventado.

### Recuperación: instalación online autorizada

Usuario: «intenta instalarlo si no te deja tengo que actualizar el token».
Autorizó intentar acceso al registro con autenticación existente del host, sin copiar
ni mostrar secretos. Mismo sandbox/SHA, Node22.23.1/pnpm10.3.0 y comando anterior
sin `--offline`; lock congelado y scripts desactivados.

**PASS, exit0**, `Done in 30.4s` reportado por pnpm: 1404 paquetes añadidos,
1382 reutilizados y 1 descargado en la salida final. `git status --short` sigue vacío.
No fue necesario cambiar el token para esta instalación; no se concluye nada sobre
su fecha de expiración ni sobre permisos ajenos al acceso utilizado.
Evidencia sanitizada en `install-online-attempt-1.log` e
`install-online-attempt-1-result.json` bajo `.local/factory/pilot-banners/`.
El fallo offline previo se conserva; bloqueo de dependencias resuelto para esta copia.

No se ejecutaron lifecycle scripts, agente, servidor ni checks/E2E. Próximo paso del
piloto: acreditar aislamiento CMS/red y preparación de worktree/perfil antes del
despacho real. La instalación exitosa no acredita runtime ni aceptación del requisito.

## Pruebas solicitadas por el usuario

Usuario: «Ejecuta las pruebas del piloto y dime si quieres que revise los resultados.»
Base fuente sigue SHA5a8e44b8 limpia. Checks obligatorios anunciados antes de ejecutar:
unitarias,tipos,lint,E2E de éxito/fallo/lentitud; build pendiente por perfil frontend.
Node22.23.1/pnpm10.3.0, sin credenciales de aplicación ni conexiones reales.

- Guard de red nativo `sandbox-exec (deny network*)`: prueba de conexión devuelve
  EPERM, PASS. Unitarias ejecutadas bajo ese guard, no solo promesa de MSW.
- `pnpm --filter @app/working-capital run test:unit --runInBand --passWithNoTests=false`:
  PASS,11 suites/128 pruebas,0 snapshots;5.1s informado por Jest. Sin aceptar suite vacía.
- `pnpm --filter @app/working-capital run check-types`: PASS.
- `pnpm --filter @app/working-capital run lint`: PASS,0 errores/advertencias,102archivos.
- Precondición Cypress: package/bin15.13.0,Electron37.6.0,Node integrado22.19.0.
- Guard loopback para E2E: servidor/conexión localhost permitidos y conexión a
  dirección externa de prueba denegada EPERM; evidencia network-loopback-probe-1.log.

Logs/resultados con comandos,huellas,exit y tiempos en
`.local/factory/pilot-banners/{unit,types,lint}-attempt-1{.log,-result.json}`.

Preparación E2E separada en `.local/factory/pilot-banners/harness/`: mock solo de
fetch HTTP del story CMS exacto; datos de pruebas existentes (banner/drawer) y labels
sintéticos de navegación, no fallback en producto ni contenido real Storyblok.
Otras llamadas externas del servidor fallan explícitamente; sandbox nativo solo
permite loopback para servidor y navegador. No tocar lógica de banners.
Suite existente credito-banners.cy.ts sin cambios, desktop1200x800,Electron,
retries0 y capturas tras tests que pasen; grabación habilitada. Servidor propio en
127.0.0.1:3109, procesos propios detenidos al terminar. E2E aún pendiente de resultado.
Esto prueba la revisión de la MR, no un run de agente/fábrica (todavía sin JobSpec).

### Resultados observados y recuperación del montaje E2E

1. Intento1 bloqueado antes de Cypress: página HTTP500 porque el mock esperaba
   `/cdn/stories/...` y el cliente real construye `/cdn//stories/...`. El guard
   falló cerrado; no hubo lectura remota. Se ajustó solo la ruta exacta del mock
   externo, no el cliente ni la UI. Log next-server-attempt-1.log y resultado E2E1.
2. Intento2 página200, Cypress exit1 antes de casos: soporte TS externo de capturas
   sin tsconfig cercano. No es fallo del banner. Se retiró la sobreescritura de
   supportFile y se conservó el soporte original; no se cambió suite ni producto.
3. Intento3 PASS,5casos/0fallos/0omitidos, retries0, escritorio1200x800/Electron.
   Casos: sin banner,fecha de vencimiento,oferta$250000,falla502 y demora3000ms.
   Duración suite6s; proceso15.381s. Evidencia e2e-desktop-attempt-3.log/-result.json
   y vídeo `e2e-desktop-attempt-3/videos/credito-banners.cy.ts.mp4`.
4. `pnpm --filter @app/working-capital run build`: PASS exit0 con mismo mock CMS,
   guard loopback y Node22,10.391s de proceso. No es build con CMS/entorno reales.

Fuente en SHA5a8e44b8 sin cambios; original conserva rama/HEAD/untracked anteriores.
Puerto3109 sin listener al terminar; no servicios/runners generales iniciados.
Artefactos Next/node_modules solo sandbox. Auditoría guard: fallo CMS del intento1,
CMS mockeado en recuperación y bloqueo del sondeo de actualización de Next a npm.
Avisos no bloqueantes Cypress: allowCypressEnv y args de Chromium no aplicables a
Electron. En vídeo se ven404 locales de flags/sidebar: no hay aceptación integral
del shell ni se afirma que todos sus servicios estuvieran mockeados correctamente.

Revisión visual complementaria mediante frames extraídos con ffmpeg ya incluido en
Cypress (sin instalar herramientas): título/acciones visibles mientras getWcBanners
sigue pendiente; sidebar con skeleton. Logs/casos prueban éxito del banner; vídeo es
complemento, no sustituto de aserciones. Sin capturas nuevas de Cypress al pasar.
No afirmar medición exacta de latencia de render ni prueba móvil/interacción extensa.

Estado: checks existentes WC y suite desktop de banners PASS con mocks; **piloto
completo/fábrica no verificados**. Sin agente real,JobSpec,worktree de unidad,admisión,
efectos ni datos principal. Pendientes móvil,compuertas y despacho real. Se solicita
revisión humana del vídeo,especialmente del escenario lento,antes de ampliar el piloto.

## Continuación autorizada: planta y agente real

Usuario aclaró que desea probar pedido→fábrica→agente→resultados y autorizó:
«Ok, entonces podemos continuar con esa parte para probarlo.»
Se comunicó una corrida única con pedido manual derivado del requisito Slack ya leído,
TESTDB separada,perfil pnpm propio y todos los efectos prohibidos/pasarela recording.
No lecturas nuevas de Slack,principal,runners generales,publicaciones ni cambios al
checkout original. Unidad con worktree/commit locales solo en la copia aislada,
base SHA5a8e44b8;Git de la unidad,no del agente. Claude es default real del perfil.

Unidad de trabajo del agente: reforzar regresión E2E causal manteniendo pendiente
la respuesta wc-banners hasta comprobar Crédito visible;no rehacer UI ya existente.
Writable set acotado al spec nuevo y helpers E2E expresamente listados;sin producto,
manifiestos,fixtures de negocio,configuración,tracking ni delegación recursiva.
Baseline funcional ya PASS;no se exige fabricar RED de un bug inexistente.

Admisión usa FactoryService.ingest;ejecución FactoryService.process_one→
ScraftOpsExecutor→binario scraft-ops factory run→Claude Code,RunRecord de vuelta.
No worker tick porque drena hasta20jobs y ejecuta efectos/reclaims;solo process_one.
Schema aditivo propio en efren_bot_test:55433,solo cuatro tablas factory,UUID nativos
en DB y strings en JSON como contratos existentes;sin cambiar modelos/serialización.
No truncar datos de test compartidos ni usar principal55432.

Obligatorias antes/después de corrida (guion5 y contrato del piloto): identidad DB,
admisión+cola+un intento,worktree separado,check setup offline lock congelado sin
scripts,tipos,lint,unitarias no vacías,build y E2E bajo guard de red;mismo contenido
no duplica pedido;RunRecord y delta inspeccionables,cero efectos/gateway calls y
original conservado. Perfil de prueba sustituye comandos npm --if-present por los
reales pnpm, sin modificar perfil genérico ni producto. No reutilizar PASS del
checkout base para el worktree nuevo. Fallo/cancelación/timeout detienen, no reintentos
ni cambios de código de la fábrica para forzar PASS. Límite exterior900s por intento.

Preflight de routing conservado: al entregar al triage TODO el brief operativo,
su texto de seguridad («por qué»,«credenciales»,«secretos») lo clasificó research/inbox,
no desarrollo;assertion de rol falló antes de DB/agente. No se cambió política ni se
admitió un rol distinto. Se separó el pedido manual concreto en factory/request.md
de la evidencia y brief operativo:proveniencia original en attrs,scope completo en el
pedido. Segundo preflight admit/development PASS,scripts Python compilan y efectos
todos forbidden. No es reintento de agente:ninguno había arrancado aún. Limitación
de triage ante instrucciones incrustadas documentada,sin corrección del producto.

Primer intento real de unidad: pedido8ff98432-7190-4997-9d8b-1689f5ab24bb,
job4a85fa5d-50d0-4589-b996-841360847119,unidadfj-454b9bcfbf9d-a1. TESTDB schema
factory_banners_pilot_20261028a:admit,dedupe y queued PASS;prepare/worktree PASS.
Execute FAIL antes de modelo: `exec: "claude": executable file not found in $PATH`.
PATH reducido del driver excluyó ~/.local/bin,ubicación comprobada del CLI oficial.
Job terminal failed,1intento,0checks/0efectos,delta vacío;no retry automático ni
reescritura de ese resultado. Original/copia fuente conservados.

Ajuste mínimo del entorno de ensayo comunicado: incluir ubicación instalada del
CLI,sin instalar/cambiar agente ni producto. Un nuevo pedido de ensayo identificado
como recuperación del anterior,con artefactos en factory/attempt-2 y schema TESTDB
factory_banners_pilot_20261028b. No se simula capacidad retry del producto ni se
resetea job fallido;se preservan1erRunRecord/worktree/trace. Límite:un lanzamiento
real del modelo;si este falla,parar sin fallback ni más repeticiones.

### Resultado de la corrida por fábrica: bloqueo de cuota del ejecutor

Recuperación de entorno completada incluyendo ~/.local/bin existente,sin renovar
tokens ni instalar/cambiar Claude. Segunda solicitud de ensayo:
item0b00af8c-376a-48ce-aaf0-5eda20392e2e,
job3ec9bd2f-28ec-46bf-ac82-b51ee8b17b64,unidadfj-583f19e01b3a-a1.
TESTDB schema factory_banners_pilot_20261028b:1item,1admission,1job,0effects.

[runtime-observed] Admit/dedupe/queued/prepare(worktree) PASS. Invocación real CLI
Claude Code termina exit1 en execute;execute.log contiene únicamente:
`You've hit your individual spend limit · run /usage-credits to ask your admin for a higher limit`.
No inferir token vencido,modelo utilizado,herramientas cargadas ni trabajo del agente
a partir de ese error;no hubo respuesta de trabajo ni cambios. No se ejecutaron
checks,risk ni review,ni commit generado. RunRecord válido failed/requires_human
fue aceptado por ScraftOpsExecutor y persistido por FactoryService:retorno de error
de ejecución probado,no éxito end-to-end. Job terminal failed,attempt_count1.

Evidencia:factory/attempt-2/{trace.jsonl,queued-job-spec.json,unit-stdout.json,
unit-stderr.log,result.json,agent-delta.patch};record original adicional en
factory/state/runs/fj-583f19e01b3a-a1.json y execute.log en subdirectorio homónimo.
Worktree propio factory/state/worktrees/fj-583f19e01b3a-a1,branch factory/…a1.
Delta y untracked vacíos,0propuestas y0llamadas RecordingGateway. No acceso principal
ni fuentes nuevas,ningún worker general iniciado;puerto3110 sin listener al final.
Original712b453e8 misma rama/untracked y fuente5a8e44b8detached limpios conservados.

Estado: **bloqueado por cuota de Claude Code**,no piloto exitoso. Los checks128unit/
5E2E del sandbox previo siguen siendo historia independiente,no checks de estos jobs.
No reintentos/fallback ni sustitución por agente falso. Para retomar:resolver cuota
mediante interfaz oficial del host (`/usage-credits`,según error),o autorización
explícita de otro ejecutor;esa nueva corrida debe conservar ambos fallos y sus IDs.
No editar política/executor de producto para forzar resultado,sin borrar worktrees.

## Autorización posterior de fallback y cambio de principal

Usuario: «cambialo, y debe haber un cambio automatico de jecutor si uno no esta disponible.»
Eligió expresamente «Claude como respaldo» y «Sí, ambos repositorios» para ajustes
acotados de adaptador/configuración/pruebas en Efren Bot y scraft-ops,sin commits,
push ni cambios globales por extensión. Esta aprobación permite ahora OpenCode→Claude
en el piloto;reemplaza la prohibición anterior de fallback solo para esa cadena
autorizada y con guardias,no para proveedores nuevos o cuentas implícitas.

Implementación independiente documentada en .odd/factory-executor-fallback.md.
Registro local factory/projects.json y perfil piloto preparados con OpenCode principal,
Claude fallback explícito;registry principal intacto. Binario nuevo solo de prueba en
.local/factory/executor-fallback/bin/scraft-ops. No ejecutar drivers históricos que
fijabanClaude ni resetear sus locks,IDs o resultados. Aún no se ha relanzado el job
real,instalado global ni actualizado API/runners. Verificación de fallback con
CLIs dobles:109ensayo y668Python+38web PASS,Go vet/suite PASS,sin cuentas reales.
Riesgo completo/revisión formal/activación siguen pendientes,según documento nuevo.
