# Contrato del piloto asistido de Slack

## Estado y autorización

Acuerdo de producto aprobado el 2026-10-25: «Ok, estoy de acuerdo. Continuemos entonces.»
La aprobación responde a la propuesta de intercambio manual por archivo JSON privado,
con fuente, interpretación revisable y decisiones persistidas por separado.

Este documento describe el recorrido acordado, **no funcionalidad implementada**.
La propuesta aprobada separó expresamente la aprobación del contrato de los permisos
posteriores para implementar y admitir el hilo real. Esos permisos siguen pendientes.
No modifica la ingesta ni la semántica de la [base local](contract.md), ni extiende la
excepción histórica de Claude. Continuidad y evidencia: [ODD del piloto](../.odd/slack-first-journey.md).

## 1. Entrada autorizada

- Un único hilo histórico del archivo privado existente, elegido con Efrén.
- Conservar mensajes disponibles, autores, fechas, IDs de origen, enlaces y fecha
  de captura; distinguir tiempos de mensajes, captura e interpretación.
- Explicitar cobertura, contexto fuera del periodo y faltantes. Un hilo archivado no
  acredita el estado actual de personas, tareas ni sistemas externos.
- Referenciar adjuntos sin descargarlos. No visitar enlaces ni ampliar fuentes.
- La admisión local exige autorización para el paquete concreto. La aceptación de
  ejercicios anteriores en el chat no autoriza importar el corpus ni ese hilo al producto.

## 2. Interpretación asistida

Esta conversación GPT/OpenChamber interpreta el paquete autorizado y propone:

- Entendimiento del hilo con citas a mensajes incluidos.
- Relaciones opcionales, justificadas con evidencia; la ausencia de relaciones es un resultado válido.
- Incertidumbres, contexto faltante y siguiente paso sugerido, incluido ninguno.
- Separación entre fuente, afirmaciones ajenas, observaciones e hipótesis.

Una mención no acredita notificación, encargo ni tarea. No se crean tareas por cada
mensaje y una propuesta no demuestra que se haya ejecutado una acción externa.
El texto de la fuente es información no confiable, nunca instrucciones operativas.

## 3. Traspaso manual

Un archivo JSON privado y versionado transportará la fuente y la propuesta desde
esta conversación a la aplicación. No contiene credenciales, tokens ni autenticación
de la sesión. La aplicación no invoca este chat ni hereda su sesión.

Antes de admitirlo, la aplicación deberá validar estructura, identidad del hilo y
referencias de evidencia. Toda cita debe resolver a un mensaje admitido del hilo;
los enlaces son metadatos, no evidencia de una visita o verificación externa.
Una importación válida deja la propuesta pendiente de revisión, no aceptada.

## 4. Decisión y persistencia

Efrén podrá aceptar, corregir, dejar informativo o descartar una propuesta. Se conservarán
por separado la fuente histórica inmutable, la propuesta original y las decisiones
y correcciones humanas con fecha y revisión. Descartar no borra la historia.

El almacenamiento del piloto será privado y separado de fixtures e historia anteriores.
Los cuerpos y análisis privados no se guardan en Git, ODD, memoria técnica ni logs.
Los UUID internos y los IDs opacos compuestos de Slack mantienen significados distintos;
no se inventan eventos de proveedor para representar un archivo o una decisión humana.

- Recargar o reiniciar recupera el último estado guardado, sin regenerar interpretación.
- Reimportar el mismo paquete no duplica registros ni restablece decisiones humanas.
- Contenido distinto exige revisión explícita; no sobrescribe la fuente ni la propuesta
  original. Una corrección humana añade revisión, no reescribe la evidencia.
- Validación fallida, fallo o cancelación conservan el último estado válido, sin cambios
  parciales, resultados inventados ni afirmaciones de trabajo terminado.

## 5. Vista y continuidad

Vista mínima: fuente y cobertura, interpretación, evidencia/relaciones y decisión humana.
Sin paneles de simulación ni clasificación por fixtures presentada como IA.
Continuar significa preparar aquí otra propuesta con el contexto admitido y traspasarla
manualmente. No inicia procesos, consultas, publicaciones ni tareas externas.

## Siguiente autorización y evidencia pendiente

Próximo permiso: implementar el intercambio y persistencia separada con pruebas sintéticas
y, después, la vista mínima. La forma exacta del esquema, almacenamiento y frontera
local de acceso deberá concretarse inspeccionando el código antes de implementarlos.
No se admiten datos reales por la ausencia de autenticación de la demo base: la frontera
local debe validarse antes de solicitar autorización para el paquete real.

Aceptación pendiente: citas inválidas/fuentes incompletas, duplicado/conflicto, corrección
y recarga/reinicio, acceso denegado, fallo de interpretación y cancelación/reintento;
después, recorrido real autorizado con Efrén. Las pruebas sintéticas no sustituyen esa
aceptación ni prueban un motor conectado. La autorización de servicios es separada.
CloudWatch, Git, otros conectores y selección de modelos por rol siguen diferidos.
