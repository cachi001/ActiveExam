## MODIFIED Requirements

### Requirement: El contador de pasos del perfil refleja 4 pasos cuando ENABLE_DNI_SCAN es true
El sistema SHALL mostrar "Paso N de 4" en el encabezado de cada paso del enrollment cuando `ENABLE_DNI_SCAN` es `true` (foto_perfil=2, biometria=3, dni=4). Cuando `ENABLE_DNI_SCAN` es `false`, el total SHALL ser 3 (foto_perfil=2, biometria=3; el paso dni no se cuenta). El total de pasos SHALL ser consistente entre todos los encabezados de paso.

#### Scenario: Encabezado del paso 'foto_perfil' muestra 2 de 4 con DNI activo
- **WHEN** `ENABLE_DNI_SCAN` es `true` y el paso activo es `foto_perfil`
- **THEN** el subtítulo muestra "Paso 2 de 4"

#### Scenario: Encabezado del paso 'biometria' muestra 3 de 4 con DNI activo
- **WHEN** `ENABLE_DNI_SCAN` es `true` y el paso activo es `biometria`
- **THEN** el subtítulo muestra "Paso 3 de 4"

#### Scenario: Encabezado del paso 'dni' muestra 4 de 4 con DNI activo
- **WHEN** `ENABLE_DNI_SCAN` es `true` y el paso activo es `dni`
- **THEN** el subtítulo muestra "Paso 4 de 4"

#### Scenario: Totales consistentes con DNI inactivo
- **WHEN** `ENABLE_DNI_SCAN` es `false` y el paso activo es `biometria`
- **THEN** el subtítulo muestra "Paso 3 de 3" (sin cambio respecto a C-37)

## ADDED Requirements

### Requirement: El resumen de DNI en el perfil muestra frente y dorso completados
Cuando `enrollment.dni.captura_completada` es `true`, la sección de DNI en la vista principal del perfil SHALL indicar "Frente y dorso registrados" con la fecha de captura. Si `ENABLE_DNI_SCAN` es `false`, la sección SHALL mostrar "Próximamente" sin acceso al flujo.

#### Scenario: Sección DNI muestra frente y dorso cuando completado
- **WHEN** `enrollment.dni.captura_completada` es `true`
- **THEN** la tarjeta de la sección DNI en el perfil principal muestra "Frente y dorso registrados" y la fecha en formato `es-AR`

#### Scenario: Sección DNI muestra estado pendiente cuando no completado y DNI activo
- **WHEN** `ENABLE_DNI_SCAN` es `true` y `enrollment.dni` es `null`
- **THEN** la tarjeta de DNI muestra estado pendiente con botón para iniciar el escaneo
