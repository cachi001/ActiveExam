# student-exam-cards-responsive Specification

## Purpose
TBD - created by archiving change c-58-pulido-ux-flujo-examen-login. Update Purpose after archive.
## Requirements
### Requirement: Tarjeta de inscripción responsive

La tarjeta de inscripción del alumno (`InscripcionCard`) SHALL adaptarse a pantallas chicas sin desbordar texto ni controles. Los nombres largos MUST truncarse, y el badge de estado y la fila de acción MUST acomodarse mediante breakpoints (por ejemplo `flex-col` en mobile, `flex-row` desde `sm`) usando los tokens de espaciado y color del sistema.

#### Scenario: Inscripción con nombre largo en mobile

- **WHEN** la tarjeta de inscripción se muestra a 360px de ancho con un nombre de examen largo
- **THEN** el nombre y la materia truncan con elipsis y no se salen del contenedor
- **AND** el badge de estado y el botón/razón de acción quedan dentro de la tarjeta sin desbordarse

#### Scenario: Tarjeta de inscripción en desktop

- **WHEN** la tarjeta se muestra en pantallas anchas (`sm` o mayor)
- **THEN** el layout en fila se conserva como antes, sin regresiones visuales

### Requirement: Tarjeta de examen responsive

La tarjeta de examen del catálogo (`ExamenCard`) SHALL adaptarse a pantallas chicas sin desbordar. El nombre del examen MUST truncar, y el cluster de badge(s) y botón MUST acomodarse mediante breakpoints y `min-w-0`/`shrink-0` según corresponda, usando los tokens del sistema.

#### Scenario: Examen con nombre largo en mobile

- **WHEN** la tarjeta de examen se muestra a 360px de ancho con un nombre largo
- **THEN** el nombre trunca con elipsis y el badge y el botón quedan dentro de la tarjeta sin desbordarse

#### Scenario: Tarjeta de examen en desktop

- **WHEN** la tarjeta se muestra en pantallas anchas (`sm` o mayor)
- **THEN** el layout en fila se conserva sin regresiones

