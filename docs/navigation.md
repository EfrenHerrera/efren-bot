# Por qué la web tiene tres entradas

## Motivo del cambio

El usuario señaló: «tengo una duda, no se como funcione exactamente porque tenmos varias
secciones [...] me queda muy confuso para que cada seccion.» Después autorizó:
«okay entonces ajustame la web, y deja documentado porque estas haciendo el cambio.»

Las cinco pestañas anteriores reflejaban módulos de implementación, no intenciones de
uso. Revisiones y Solicitudes mostraban las mismas MRs, aunque una ofrecía análisis y
chat y la otra decisiones de seguimiento. No eran trabajos duplicados en la base, pero
sí entradas de navegación redundantes. Fábrica añadió otra capa sin resolver esa confusión.

## Organización vigente

- **Conversaciones:** mensajes guardados, contexto original, menciones y asuntos humanos.
- **Solicitudes:** única lista de casos de soporte y MRs, sus conclusiones y decisiones.
  El botón de cada ficha abre la investigación o revisión exacta con evidencia/chat.
  «Volver a solicitudes» conserva filtro, selección e indicación no enviada.
- **Fábrica:** circuito separado de admisión y ejecución. No recibe automáticamente los
  casos/MRs de Solicitudes; tampoco es un paso obligatorio después de leer una conversación.

Soporte y revisiones dejan de ser pestañas principales, pero sus detalles, evidencia,
chat y edición de comentarios siguen disponibles dentro de Solicitudes. Los controles
globales de novedades están bajo «Ejecutores y capacidades», incluso sin casos. Los
detalles conservan configuración avanzada explícita. Ningún botón de navegación arranca
ejecutores, reanaliza un caso o encola una publicación.

Los detalles se abren por UUID interno exacto. Si el item no aparece entre los100 recientes,
se pide su detalle igualmente; ante error no se selecciona otra MR/caso silenciosamente.
Los borradores de decisiones, chat soporte y comentarios/chat MR viven en memoria de App
por identidad: se conservan al volver/cambiar de área, no tras recargar/cerrar el navegador.

## Lo que no cambia

No migraciones ni cambios de API/DB, identidades, informes, disposiciones o permisos.
Las guardias humanas de backend siguen vigentes. Fábrica mantiene proyectos/cola propios.
Una navegación más simple no habilita fuentes, agentes ni efectos reales. Las demos no
publican y los runners detenidos no se reanudan durante el despliegue de la web.

## Comprobación

Pruebas de navegación principal de tres entradas, apertura por UUID (incluido fuera de
lista reciente), retorno y borradores soporte/MR, sin mutaciones por consultar; regresión
global del proyecto y navegador desktop/móvil. Evidencia de esta unidad en
`.odd/web-navigation.md` y `.local/factory/validation/navigation-*.log`.
