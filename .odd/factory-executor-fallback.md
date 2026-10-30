# Fallback autorizado de ejecutores de fábrica

## Objetivo y autorización

Usuario: «cambialo, y debe haber un cambio automatico de jecutor si uno no esta disponible.»
Decisiones explícitas posteriores: «Claude como respaldo» (autoriza consumir esa
cuenta solo como respaldo de OpenCode) y «Sí, ambos repositorios» (Efren Bot y
`/Users/efren.herrera/Downloads/scraft-ops`,solo adaptador/configuración/pruebas,
sin commits,push ni cambios globales por extensión).

OpenCode principal para frontend y piloto;Claude respaldo explícito por JobSpec/
configuración,no cuenta implícita para instalaciones nuevas. Fallback solo ante
indisponibilidad reconocible previa al trabajo y worktree aún idéntico al inicial.
Nunca ante tests/código inválido,timeout,cancelación,error desconocido,log truncado
o cambios parciales. No reiniciar trabajos/efectos inciertos ni repetir ejecutores.
Sin debilitar checks,riesgo,revisión,worktree,compuertas humanas o permiso de efectos.
No modificar UI,datos remotos,otros repos,fixtures WC ni runners generales.

## Evidencia y decisiones

Efren Bot en main23b6fe6 con cambios previos UI/docs ajenos;factory/src/tests
inicialmente sin delta. Scraft-ops mainba1d4b1 limpio,sin CodeGraph/AGENTS local,
reglas .ath/rules.md leídas (Go:gofmt/vet/suite completos obligatorios).
No limpiar cambios existentes ni fabricar un base-ref que incluya UI ajena.

Lanzador real en scraft-ops/internal/factory:CommandExecutor invoca CLI y Run
prepara worktree,ejecuta,verifica,evalúa/revisa/commitea y devuelve RunRecord.
Opciones OpenCode V2 consultadas en docs oficiales y help local:cwd por cmd.Dir,
run --standalone --agent --format json y modelo provider/model#variant;no --dir
ni --variant. Mantener suscripción host,sin copiar credenciales ni configurar global.

Contrato aditivo:policy.fallback_executors (allowlist ordenada,solo reales,acotada,
sin duplicados ni fake);RunRecord.execution_attempts con ejecutor,fase,estado,
motivo,log y timestamps. Misma identidad JobSpec/RunRecord y worktree de unidad,
UUID de DB intactos y JSON conforme a frontera actual. Ambos contratos fuente,
modelos factory vecinos y persistencia/HTTP revisados antes de editar.

Fallback inicial build únicamente;revisión que no termina sigue requiriendo humano.
Tiempo total build compartido entre candidatos,un intento por ejecutor. Opciones
model/effort fijadas no se copian entre proveedores:cadena rechazada si no puede
representar ambas configuraciones de forma inequívoca. Sin fallback real desde fake.
Disponibilidad se clasifica conservadoramente en el adaptador,sin buscar substrings
de cuota dentro de una respuesta normal del modelo. Errores no reconocidos paran.

## Unidades y aceptación

- [x] Contratos y pruebas RED:preferencia OpenCode,allowlist,clasificación,seguridad.
- [x] Go:CLI V2,relevo acotado,sin trabajo parcial,recibos y comprobaciones preservadas.
- [x] Python:configuración por proyecto/host,JobSpec y persistencia de recibos,docs.
- [ ] Verificación cruzada/global y revisión aplicable,sin cobros de modelo en tests.

Pruebas obligatorias por criterio:ausente/cuota→respaldo,agotamiento de ambos,
sin autorización no relevo,fallos ordinarios/log parcial/timeout/cancelación/cambios
parciales nunca relevo;no llamadas adicionales tras éxito;ni fake fallback real ni
mezcla de modelos. CLI V2 con cwd ysin flags antiguos. Recibos preservados Go→Python
→DB;perfiles espejo iguales;tests por proyecto en base separada;controles de parada
y política de efectos se mantienen. Usar CLIs dobles en pruebas,no invocar cuentas.

Obligatorios de proyecto:Go gofmt,go vet ./...,go test ./...;Python make check/test
y rehearsal con binario local nuevo y TESTDB según Makefile. Fallos/reintentos se
conservan. No sustituir suite global por focal. Riskgate final de Efren Bot pendiente
si delta mixto no permite base exacta;no llamarlo verified/done por ese motivo.

Estado:inspección completada,diseño mínimo anterior;próximo escribir y observar RED.
Continuidad del piloto previo en .odd/factory-banners-pilot.md;no borrar sus fallos
de PATH/cuota ni reanudarlos automáticamente. Binario de prueba solo en .local,no
go install/scraft-ops install ni cambio al ejecutable global.

## Evidencia y estado de verificación

RED observado en ambos repositorios:Go rechazó expectativas CLI V2/defaultfrontend;
Python3fallos/7passes al faltar defaultopencode,config y contratosaditivos. Logs
`.local/factory/executor-fallback/{go,python}-red.log`. No se declaró RED de un
bug de banners ya resuelto. GREEN focalGo factory/cli y56Pythonunit PASS.

Ensayo obligatorio actualizado para incluir todos test_factory_*.py:108PASS,
sin skips,en TESTDB;6casos reales planta→binario nuevo→CLIs dobles→RunRecord→DB
cubren recuperación,éxito primario,sin autorización,cambios parciales,error ordinario
y agotamiento de ambos. Cero uso de suscripciones/publicaciones. Go vet ./... y
go test ./... PASS (varios paquetes informaron caché;factory/cli se ejecutaron).
Logs rehearsal-1.log,go-vet-1.log,go-global-1.log. Binario local compilado en
`.local/factory/executor-fallback/bin/scraft-ops`;no global install.

Configuración del piloto preparada en `.local/factory/pilot-banners/factory/projects.json`
y perfil local:OpenCode→Claude autorizado;registry principal sigue vacío,intacto.
Drivers históricos del piloto están bloqueados por sus locks;no reescribir sus
resultados ni lanzar el driver antiguo que fijabaClaude. No se reanudó ningún job.
Próximo:checks globales de Efren Bot,risk-assess con delta exacto de scraft-ops y
revisión aplicable. Efren Bot conserva deltaUI/docs anterior ajeno:gate de riesgo
global pendiente,ningún base-ref engañoso. No afirmar verificación final/deploy.

### Cierre funcional local y límites de entrega

Revisión propia añadió dos regresiones RED→GREEN:
1. `build_executor` ya no impone el override global a un JobSpec previamente
   encolado;la selección global solo se fija al admitir trabajos nuevos. Evita
   cambiar de cuenta o duplicar fallback por una configuración posterior.
   Log queued-policy-red.log;corregido solo wiring,contrato persistido intacto.
2. OpenCode usa JSON en build,pero conserva texto en revisión independiente para
   no buscar veredictos dentro de eventos JSON de herramientas. Log
   review-format-red.log;guard de CLI V2 cubre ambas fases por separado.

Resultados finales tras esas correcciones:
- make check PASS (Compose,Ruff/formato,npm ci,tipos/buildweb).
- make factory-rehearsal con binario local nuevo:109PASS,sin skips,TESTDB.
- make test:668Python (475unit/nointegration+193integration),38web PASS.
- gofmt sin salidas,go vet ./... y go test ./... PASS;factory/cli ejecutados,
  varios paquetes Go con caché normal del framework. Sin modelos/cuentas reales.
- Logs *-final.log en .local/factory/executor-fallback;los RED/primeros GREEN
  permanecen como historial,no se presentan como pruebas actuales de código distinto.

Riskgate **pendiente en ambos repos**,no aprobación:
`scraft-risk-1.json` informó medium/single con148líneas/6archivos,pero omitió
los3archivos Go nuevos sin seguimiento (incluye fallback.go). Por tanto su
evaluable=true no cubre el target y NO se acepta ese tier como gate final.
Ayuda --help del comando también falla,no es una evaluación de esta feature.
Efren Bot además mezcla UI/docs anteriores con este incremento. No se hizo staging,
rama/worktree/commit alternativo ni se corrigió la herramienta de riesgo por extensión.
La revisión reglada por el tier exacto sigue pendiente;revisión propia no la sustituye.
Se requiere aislamiento/acuerdo de entrega para evaluar delta completo antes de
declarar verified/done o instalar/desplegar. No se usó una revisión genérica para
simular aprobación de scraft-judge.

Estado entregable actual:implementación y configuración local preparadas,checks
funcionales/globales PASS. NO instalación global,reinicio de runners/servicios,
reintento del piloto real ni gasto adicional de suscripciones. Binario nuevo solo
en .local;el ejecutable global y la API desplegada conservan su versión anterior.
La preferencia del piloto está en su registro local opencode→claude autorizado;
el registro principal de proyectos sigue vacío. Conservar trabajos fallidos previos.
