## MODIFIED Requirements

### Requirement: El resumen de DNI en el perfil muestra frente y dorso completados
Cuando `enrollment.dni?.captura_completada` es `true`, la sección de DNI en la vista principal del perfil SHALL indicar el estado del escaneo. Si `enrollment.dni?.analisis` existe, SHALL mostrar el estado del análisis indicativo (badge de estado + fecha de análisis + nota de revisión humana) en lugar del texto estático. Si `enrollment.dni?.analisis` es `undefined`, muestra "Frente y dorso registrados" con la fecha de captura. Si `ENABLE_DNI_SCAN` es `false`, la sección SHALL mostrar "Próximamente" sin acceso al flujo.

#### Scenario: Sección DNI muestra estado del análisis cuando existe
- **WHEN** `enrollment.dni?.captura_completada` es `true` y `enrollment.dni?.analisis?.estado` es `'preliminar_ok'`
- **THEN** la tarjeta de la sección DNI en el perfil principal muestra badge "Análisis preliminar OK" (tone: success) con texto "Pendiente de revisión humana"

#### Scenario: Sección DNI muestra requiere revisión cuando análisis lo indica
- **WHEN** `enrollment.dni?.captura_completada` es `true` y `enrollment.dni?.analisis?.estado` es `'requiere_revision'`
- **THEN** la tarjeta muestra badge "Análisis — Requiere revisión" (tone: warning) con texto "Pendiente de revisión humana"

#### Scenario: Sección DNI muestra fallback básico cuando capturado sin análisis
- **WHEN** `enrollment.dni?.captura_completada` es `true` y `enrollment.dni?.analisis` es `undefined`
- **THEN** la tarjeta muestra "Frente y dorso registrados" y la fecha de captura en formato `es-AR`

#### Scenario: Sección DNI muestra estado pendiente cuando no completado y DNI activo
- **WHEN** `ENABLE_DNI_SCAN` es `true` y `enrollment.dni` es `null`
- **THEN** la tarjeta de DNI muestra estado pendiente con botón para iniciar el escaneo

## ADDED Requirements

### Requirement: Nota de revisión humana en sección DNI del perfil
Cuando se muestra el estado del análisis en la sección DNI del perfil, SHALL incluirse una nota corta que indique que el análisis es preliminar y está sujeto a revisión humana, coherente con el principio L2.5.

#### Scenario: Nota de revisión visible en ambos estados de análisis
- **WHEN** el análisis existe (estado 'preliminar_ok' o 'requiere_revision')
- **THEN** SHALL mostrarse junto al badge el texto "· Pendiente de revisión humana" o equivalente que comunique que el sistema no aprueba ni rechaza automáticamente
