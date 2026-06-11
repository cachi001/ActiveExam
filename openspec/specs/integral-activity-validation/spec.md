# integral-activity-validation

## Purpose

Define la página de testeo integral que permite al operador validar end-to-end, con su propia cámara y navegador, que cada tipo de actividad sospechosa del catálogo (visión + navegador) se capturó y registró al menos una vez. Se apoya en el sink local air-gapped del harness — NUNCA emite eventos al backend de producción ni abre una sesión de alumno real. Aporta un checklist de cobertura en tiempo real y reglas para distinguir lo "no testeable en este navegador" de lo "faltante".

## Requirements

### Requirement: Checklist de cobertura de actividad sospechosa
La página de testeo SHALL mostrar un checklist con cada tipo de actividad sospechosa del catálogo (visión y navegador) e indicar, en tiempo real, cuáles fueron capturados y registrados al menos una vez durante la sesión de prueba, marcándose a partir del log de eventos del harness.

#### Scenario: Un tipo de actividad es capturado por primera vez
- **WHEN** durante la sesión de prueba se registra en el log un evento de un tipo del catálogo que aún no estaba marcado
- **THEN** el checklist marca ese tipo como "capturado y registrado", indicando severidad y momento de la primera captura

#### Scenario: Cobertura completa alcanzada
- **WHEN** todos los tipos del catálogo testeables en el navegador actual aparecieron al menos una vez en el log
- **THEN** el checklist indica cobertura integral completa para esta sesión de prueba

### Requirement: Validación integral de visión y navegador en una sola sesión
La página de testeo SHALL permitir al operador ejercitar en una misma sesión, con su propia cámara y navegador, tanto las señales de visión (rostro, mirada, pose/gestos, múltiples rostros) como las acciones de navegador (cambio/apertura de pestaña, pérdida de foco, salida de pantalla completa, copiar/pegar, monitores múltiples), confirmando para cada una que el evento se capturó y se registró vía el `EventSink`.

#### Scenario: El operador provoca una acción de navegador
- **WHEN** el operador, con la sesión de prueba activa, cambia de pestaña, pierde el foco, sale de pantalla completa o pega contenido
- **THEN** la página registra el evento correspondiente en el log, confirma que el `EventSink` lo emitió y marca el tipo en el checklist de cobertura

#### Scenario: El operador provoca una señal de visión
- **WHEN** el operador se retira del encuadre, desvía la mirada de forma sostenida o aparece un segundo rostro
- **THEN** la página registra el evento de visión correspondiente, confirma su emisión por el `EventSink` y lo marca en el checklist

### Requirement: Aislamiento de la validación respecto del backend de producción
La validación integral SHALL ejecutarse sobre el `EventSink` local air-gapped del harness; NUNCA SHALL emitir eventos al backend de producción, abrir una sesión de alumno ni iniciar un examen real (L2.5; reuso de la restricción de aislamiento D-4 de C-23).

#### Scenario: Eventos generados durante la validación
- **WHEN** se capturan y registran eventos durante la validación integral
- **THEN** los eventos permanecen en el sink local y en el log del harness, sin enviarse al backend de producción ni asociarse a una sesión real

### Requirement: Indicación de actividad no testeable en el navegador actual
Cuando un tipo de actividad del catálogo depende de una API no disponible en el navegador actual (por ejemplo, monitores múltiples vía la API de pantallas), la página SHALL indicarlo como "no testeable en este navegador" en lugar de marcarlo como faltante o fallido.

#### Scenario: API de pantallas no disponible
- **WHEN** la API de detección de pantallas no está disponible o el permiso es denegado
- **THEN** el checklist marca "monitor adicional" como "no testeable en este navegador" sin invalidar la cobertura del resto de los tipos
