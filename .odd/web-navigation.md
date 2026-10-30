# Navegación por intención, no por módulo

Usuario: «okay entonces ajustame la web, y deja documentado porque estas haciendo el cambio.»
Motivo: cinco pestañas mezclaban fuentes, detalles y controles. El usuario veía las mismas
MRs en Revisiones y Solicitudes; la unificación previamente acordada seguía pendiente.

Base23b6fe6. Cambios previos ajenos a esta unidad: docs/factory.md y documentos/reportes
locales de actualización; preservar. Solo web/docs/tests; sin API/DB/identidades/permisos
ni conexión de fábrica con soporte/MR. No Git, runners, nuevas fuentes ni efectos reales.

Tres entradas: Conversaciones (fuentes), Solicitudes (bandeja única soporte/MR), Fábrica
(ejecución avanzada independiente). Detalles existentes incrustados por UUID exacto,
sin listas paralelas ni selección alternativa silenciosa si falta un item. Volver conserva
selección/filtro e indicaciones; borradores MR/soporte viven en App durante navegación.
Controles globales existentes pasan a detalle avanzado, no se eliminan permisos/barreras.
Se conserva estética/tokens existentes: el cambio distintivo es jerarquía y orientación,
sin rediseño cosmético, nuevos colores ni dependencia corporativa.

Aceptación obligatoria AGENTS/Makefile: RED→GREEN navegación3, selección exacta, retorno,
borradores/errores y no mutaciones por abrir; checks globales y navegador desktop/mobile.
Desplegar solo web propia. Evaluación formal delta pendiente si docs/untracked previos
impiden aislamiento; no fabricar base ni confundir aceptación UX con revisión formal.

## Evidencia y resultado funcional

RED:3 pruebas nuevas fallaron,20 existentes pasaron (navigation-red.log).
GREEN:make check PASS;646Python(TESTDB separada),38web,1Node PASS, sin skips cross
con scraftba1d4b1 explícito. Logs navigation-{check,global,node,web-attempt-1}.log
en `.local/factory/validation/`. No cambios backend ni reparación para forzar pruebas.

Web local reconstruida/recreada con --no-deps; API/DB sin redeploy. Navegador observó
tres entradas, Solicitudes→MR!8594 exacta→chat→retorno; borrador no enviado sobrevivió
al reabrir y fue limpiado sin enviar. Mobile390 y desktop1440 observados. Soporte nuevo
solo sintético en tests: no hay casos reales en principal para acreditarlo en navegador.
32 tablas previas checksum/conteos intactos y esquema0011. Ningún runner arrancado.
Evidencia final navigation-acceptance.json; capturas `.openchamber/screenshots/`
navigation-mr-detail-desktop-2026-10-28T05-06-07-676.jpg,
navigation-unsent-draft-2026-10-28T05-06-52-656.jpg y
navigation-mobile-three-areas-2026-10-28T05-07-23-153.jpg.

Motivo/contrato explicados en docs/navigation.md, README y docs/human-control.md.
Delta revisado directamente (solo navegación/hooks/drafts/tests/docs), pero gate formal
de riesgo/revisión permanece pendiente: docs/factory.md y untracked de la actualización
anterior coexisten con esta unidad. No usar HEAD como aislamiento ficticio ni hacer
staging/commit/topología para satisfacerlo. Hace falta acordar aislamiento/enfoque de
entrega autorizado. Sin commits/push; no afirmar cierre formal.
