# login-portal-reframe

## Purpose

Define el reframe de la pantalla de login del alumno como portal general (acceso a materias, inscripción a exámenes, gestión de perfil) en lugar de presentarse como acceso exclusivo a un examen en curso. Cambia headline, subtítulo e ícono principal, manteniendo intacto el branding institucional (label de login, widget de institución, links de soporte y footer de privacidad con Ley 25.326).

## Requirements

### Requirement: Login como portal del alumno
La pantalla `Login.tsx` SHALL presentarse como un portal de acceso general del alumno, no como acceso exclusivo a un examen en curso. El headline SHALL ser "Portal del alumno" y el subtítulo SHALL describir las capacidades del portal (ver materias, inscribirse a exámenes, gestionar perfil académico). El ícono principal SHALL ser `school` en lugar de `verified_user`.

#### Scenario: Headline de portal del alumno
- **WHEN** el usuario accede a la ruta raíz (`/`) sin sesión activa
- **THEN** el `h1` visible dice "Portal del alumno"

#### Scenario: Subtítulo describe capacidades del portal
- **WHEN** el usuario ve la pantalla de login
- **THEN** el subtítulo comunica al menos dos capacidades del portal (ej. inscribirse a exámenes y gestionar perfil)

#### Scenario: Ícono de portal estudiantil
- **WHEN** la pantalla de login se muestra
- **THEN** el ícono principal en el header del card es `school`

### Requirement: Branding institucional intacto en login
El componente Login SHALL mantener sin cambios: el botón de login con `INSTITUTION.loginLabel`, el widget de institución con `INSTITUTION.nombre` y `INSTITUTION.facultad`, los links de navegación (Requisitos técnicos, Necesito ayuda), el footer de privacidad con referencia a Ley 25.326, y el layout/colores existentes.

#### Scenario: Botón de login usa INSTITUTION.loginLabel
- **WHEN** se renderiza la pantalla de login
- **THEN** el botón de login muestra `Ingresar con ${INSTITUTION.loginLabel}` sin modificación

#### Scenario: Widget de institución no cambia
- **WHEN** se renderiza la pantalla de login
- **THEN** el widget de institución muestra `INSTITUTION.nombre — INSTITUTION.facultad` exactamente como antes

#### Scenario: Footer de privacidad intacto
- **WHEN** se renderiza la pantalla de login
- **THEN** el footer menciona "Ley 25.326" y la referencia a privacidad de datos
