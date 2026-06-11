## MODIFIED Requirements

### Requirement: Login como portal del alumno
La pantalla `Login.tsx` SHALL presentarse como portal de acceso general del alumno. El headline SHALL ser "Portal del alumno" y el subtítulo SHALL describir las capacidades del portal. El botón de ingreso SHALL usar `size="lg"` del componente `Button` en lugar de `className="... h-14"` hardcodeado.

#### Scenario: Headline de portal del alumno
- **WHEN** el usuario accede a la ruta raíz (`/`) sin sesión activa
- **THEN** el `h1` visible dice "Portal del alumno"

#### Scenario: Subtítulo describe capacidades del portal
- **WHEN** el usuario ve la pantalla de login
- **THEN** el subtítulo comunica al menos dos capacidades del portal

#### Scenario: Ícono de portal estudiantil
- **WHEN** la pantalla de login se muestra
- **THEN** el ícono principal en el header del card es `school`

#### Scenario: Login button uses size lg prop
- **WHEN** se renderiza el botón de ingreso en Login
- **THEN** el botón usa `size="lg"` en lugar de `className` con `h-14` hardcodeado

### Requirement: Branding institucional intacto en login
El componente Login SHALL mantener sin cambios: el botón de login con `INSTITUTION.loginLabel`, el widget de institución, los links de navegación, el footer de privacidad con referencia a Ley 25.326, y el layout/colores existentes.

#### Scenario: Botón de login usa INSTITUTION.loginLabel
- **WHEN** se renderiza la pantalla de login
- **THEN** el botón de login muestra `Ingresar con ${INSTITUTION.loginLabel}` sin modificación

#### Scenario: Widget de institución no cambia
- **WHEN** se renderiza la pantalla de login
- **THEN** el widget de institución muestra `INSTITUTION.nombre — INSTITUTION.facultad` exactamente como antes

#### Scenario: Footer de privacidad intacto
- **WHEN** se renderiza la pantalla de login
- **THEN** el footer menciona "Ley 25.326" y la referencia a privacidad de datos
