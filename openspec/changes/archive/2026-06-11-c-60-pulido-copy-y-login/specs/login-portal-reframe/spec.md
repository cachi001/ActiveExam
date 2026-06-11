## MODIFIED Requirements

### Requirement: Branding institucional intacto en login
El componente Login SHALL mantener sin cambios: el botón de login con `INSTITUTION.loginLabel`, el widget de institución con `INSTITUTION.nombre` y `INSTITUTION.facultad`, los links de navegación (Requisitos técnicos, Necesito ayuda), el footer de privacidad con referencia a Ley 25.326, y el layout/colores existentes. El texto del aside desktop SHALL pasar de `Self-hosted · Ley 25.326 · DPIA aprobado` a `Self-hosted · DPIA aprobado` en las tres variantes (JWT, Demo, Keycloak), reduciendo densidad legal sin eliminar el anchor del footer. El footer de privacidad con "Ley 25.326" se conserva en todas las variantes.

#### Scenario: Botón de login usa INSTITUTION.loginLabel
- **WHEN** se renderiza la pantalla de login
- **THEN** el botón de login muestra `Ingresar con ${INSTITUTION.loginLabel}` sin modificación

#### Scenario: Widget de institución no cambia
- **WHEN** se renderiza la pantalla de login
- **THEN** el widget de institución muestra `INSTITUTION.nombre — INSTITUTION.facultad` exactamente como antes

#### Scenario: Footer de privacidad intacto
- **WHEN** se renderiza la pantalla de login (cualquier variante: JWT, Demo o Keycloak)
- **THEN** el footer menciona "Ley 25.326" y la referencia a privacidad de datos

#### Scenario: Aside desktop simplificado
- **WHEN** se renderiza la pantalla de login en viewport desktop
- **THEN** el aside muestra `Self-hosted · DPIA aprobado` sin la coletilla `· Ley 25.326`, en las tres variantes
