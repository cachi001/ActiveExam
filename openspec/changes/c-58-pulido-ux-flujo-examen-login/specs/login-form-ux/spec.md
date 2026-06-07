## ADDED Requirements

### Requirement: Toggle mostrar/ocultar contraseña en el login

El campo de contraseña del formulario de login propio (JWT) SHALL incluir un control para mostrar u ocultar la contraseña ingresada. El control MUST ser un botón accesible con `aria-label` descriptivo y MUST NOT interferir con el envío del formulario.

#### Scenario: Mostrar la contraseña

- **WHEN** el usuario pulsa el botón de ojo en el campo de contraseña mientras está oculta
- **THEN** el campo pasa a mostrar el texto de la contraseña en claro
- **AND** el ícono refleja el estado (ojo / ojo tachado)

#### Scenario: Ocultar la contraseña

- **WHEN** el usuario pulsa el botón de ojo mientras la contraseña está visible
- **THEN** el campo vuelve a enmascarar la contraseña
- **AND** el botón no dispara el envío del formulario

### Requirement: Inputs del login unificados al patrón del sistema

Los campos de usuario y contraseña del formulario de login propio (JWT) SHALL usar el patrón de formulario del sistema (componente `FormField` y clase global `.input`) en lugar de inputs con clases hardcodeadas inline. Los atributos de accesibilidad (`label`/`htmlFor`, `autoComplete`, `required`, estado `disabled` durante el login) MUST preservarse.

#### Scenario: Render de los campos del login

- **WHEN** se muestra el formulario de login propio
- **THEN** los campos usuario y contraseña se renderizan con `FormField` y la clase `.input` del sistema
- **AND** conservan sus labels asociados, `autoComplete` (`username` / `current-password`) y el estado deshabilitado durante el envío
