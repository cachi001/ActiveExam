## ADDED Requirements

### Requirement: El informe de devolución se expone al alumno SOLO cuando su nota fue anulada por fraude
El sistema SHALL exponer al alumno el **informe de devolución** de su propia sesión ÚNICAMENTE cuando la resolución de esa sesión es `anulado_por_fraude` (disclosure de debido proceso). El informe SHALL incluir: capturas de evidencia vía **URL firmada que expira en 15 minutos**, el análisis por señal (qué indicó cada detector, re-inferido **server-side**), la decisión y el **motivo**. Si la sesión fue `caso_descartado`, nunca se flaggeó, o terminó en `sin_hallazgos`/`aprobado`, el sistema SHALL NOT exponer el volcado de evidencia al alumno (**minimización**, Ley 25.326). La evidencia mostrada SHALL ser la autoritativa del backend, NUNCA el dato crudo del buffer del cliente (regla dura de dominio #6). El acceso SHALL estar acotado a la sesión del propio titular.

#### Scenario: Con nota anulada por fraude el alumno ve el informe de devolución
- **WHEN** la nota de un alumno fue resuelta como `anulado_por_fraude` y el alumno abre el informe de devolución de su sesión
- **THEN** ve las capturas (URL firmada 15 min), el análisis por cada señal, la decisión del revisor y el motivo

#### Scenario: Sin anulación por fraude no se expone evidencia (minimización)
- **WHEN** la sesión de un alumno fue `caso_descartado`, `sin_hallazgos`, `aprobado`, o nunca se flaggeó
- **THEN** el sistema no expone al alumno el volcado de evidencia de su sesión

#### Scenario: El alumno no ve la sesión de otro
- **WHEN** un alumno solicita el informe de devolución de una sesión que no es suya
- **THEN** el backend rechaza el acceso (403/404) sin exponer evidencia ajena

### Requirement: El acceso del titular al informe se registra como ejercicio del derecho de acceso
El sistema SHALL registrar en el audit log cada acceso del titular al informe de devolución de su sesión, como ejercicio del **derecho de acceso** del titular (Ley 25.326, RN-DSR-01), con actor y propósito.

#### Scenario: Cada acceso del alumno queda auditado
- **WHEN** un alumno abre el informe de devolución de su sesión anulada
- **THEN** el acceso queda registrado en el audit log con el titular como actor y el propósito de derecho de acceso
