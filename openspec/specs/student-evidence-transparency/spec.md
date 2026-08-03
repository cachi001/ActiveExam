# student-evidence-transparency Specification

## Purpose
TBD - created by archiving change c-71-inscripcion-gate-y-cola-revision. Update Purpose after archive.

## Requirements
### Requirement: El informe de devolución se expone al alumno SOLO cuando su nota fue anulada, y SOLO con la evidencia elegida
El sistema SHALL exponer al alumno el **informe de devolución** de su propia
sesión ÚNICAMENTE cuando la decisión de esa sesión es `anulado` (disclosure de
debido proceso). El informe SHALL incluir: capturas de evidencia vía **URL
firmada que expira en 15 minutos** — restringidas a los `event_id` que el
revisor eligió ESTRUCTURADAMENTE al decidir, NO todos los eventos de la
sesión —, el análisis por señal (qué indicó cada detector, re-inferido
**server-side**, sobre TODOS los tipos de evento de la sesión), la decisión
y el **motivo**. Si la sesión fue `aprobado` o nunca se flaggeó, el sistema
SHALL NOT exponer el volcado de evidencia al alumno (**minimización**, Ley
25.326). La evidencia mostrada SHALL ser la autoritativa del backend, NUNCA
el dato crudo del buffer del cliente (regla dura de dominio #6). El acceso
SHALL estar acotado a la sesión del propio titular.

#### Scenario: Con nota anulada el alumno ve el informe de devolución, filtrado a la evidencia elegida
- **WHEN** la nota de un alumno fue decidida como `anulado` con una evidencia estructurada de N `event_id`, y el alumno abre el informe de devolución de su sesión
- **THEN** ve SOLO las capturas de esos N eventos (URL firmada 15 min), el análisis por cada señal de la sesión, la decisión del revisor y el motivo

#### Scenario: Sin anulación no se expone evidencia (minimización)
- **WHEN** la sesión de un alumno fue `aprobado`, o nunca se flaggeó, o está `pendiente`
- **THEN** el sistema no expone al alumno el volcado de evidencia de su sesión

#### Scenario: El alumno no ve la sesión de otro
- **WHEN** un alumno solicita el informe de devolución de una sesión que no es suya
- **THEN** el backend rechaza el acceso (403/404) sin exponer evidencia ajena

### Requirement: El acceso del titular al informe se registra como ejercicio del derecho de acceso
El sistema SHALL registrar en el audit log cada acceso del titular al informe de devolución de su sesión, como ejercicio del **derecho de acceso** del titular (Ley 25.326, RN-DSR-01), con actor y propósito.

#### Scenario: Cada acceso del alumno queda auditado
- **WHEN** un alumno abre el informe de devolución de su sesión anulada
- **THEN** el acceso queda registrado en el audit log con el titular como actor y el propósito de derecho de acceso
