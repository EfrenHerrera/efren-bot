# Actualización local de la fábrica

## Autorización y límites

Usuario: «okay con esto podemos proceder con la acutlizacion.» y «okay ya con esto,
puedes comenzar?» tras actualizar scraft-ops explícitamente. Base efren-bot23b6fe6;
dependencia instalada scraft-opsba1d4b1. Informe de intentos previo conservado en
`docs/factory-test-report.md`; guion `docs/factory-test-plan.md`.

Ensayo simulado con agente falso, pasarela recording y TESTDB separada; si pasa,
migración aditiva0011 y actualización solo API/web propias. No instalar agentes otra
vez, reanudar recolector/soporte/MR/factory host ni activar fuentes o efectos reales.
Sin corregir producto/política para forzar pruebas verdes; ante fallo guardar y parar.
Sin nuevos commits/push/ramas para esta operación. El informe previo es untracked propio.

## Dependencias y aceptación

- [x] scraft-ops actualizado/reinstalado, Go suite/vet/formato y doctor PASS, perfiles3.
- [x] Ensayo factory-rehearsal con binario explícito y sin omisiones cross; checks globales.
- [x] Preservación de tablas/controles, migración principal0011 y API/web locales.
- [x] Health/UI escritorio-móvil; evidencia y límites documentados, sin runners iniciados.

Precondiciones observadas: Python3.14.6/uv0.11.28/Node26/Go1.26.5/Docker activo.
API/web/db/test-db propios activos; ningún runner collection/support/review/factory visto.
Autenticación de agentes/conectores no se prueba para simulación y sigue pendiente real.
No ejecutar recetas make up que arranquen workers ni configurar repos corporativos como
proyectos de prueba por inferencia. Si se requiere registro, vacío/sandbox explícito.

Comprobaciones obligatorias: guion etapas0–2 pertinentes a simulación y reglas AGENTS /
Makefile. Go pruebas previas referenciadas, no se inventa otra ejecución. Evidencia bajo
`.local/factory/validation/`; conservar intentos fallidos. Etapas3–8 reales fuera de esta
actualización, salvo lo cubierto por tests automáticos con dobles.

## Resultado local observado

Ensayo87 PASS sin skips. Global646Python(463+183TESTDB),33web,1Node PASS; make check
PASS. Ningún fallo nuevo ni corrección de producto para aceptación. El fallo inicial de
scraft desconocido permanece en informe histórico con su recuperación explícita.
Principal0011, API/web con overridefactory;32 tablas previas no Alembic intactas según
conteo/checksum. Cuatro tablas factory vacías. API200, list autenticada200/vacía y401
sin token; registro vacío readonly. No proyectos reales, datos sintéticos en principal,
workers ni fuentes/efectos reales activados. No nuevos commits/push.

Evidencia: `.local/factory/validation/{inputs,baseline-before,deployed-acceptance}.json`
y logs de intentos1. Informe `docs/factory-test-report.md`; tabla factory.md actualizada
solo para lo observado. Capturas desktop/mobile citadas allí. Tiempos solo observados
en herramientas y logs, sin medición integral ni estimación de duración total.

Desviación guion2: registry vacío, no repos sandbox aún; acciones UI solo en tests con
dobles, navegador vacío. Etapas3–8 reales pendientes y sin permiso implícito. Mensaje UI
absoluto de aprobación vs perfiles auto documentado como observación sin corregir.
Actualización local aceptada, no certificación de operación real o revisión formal del
código recibido. Siguiente paso requiere elegir alcance/sandbox/agente y sus límites.
