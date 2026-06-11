# informed-consent-presentation Specification

## Purpose
TBD - created by archiving change c-08-consentimiento. Update Purpose after archive.
## Requirements
### Requirement: Pantalla de consentimiento con lenguaje claro y texto versionado
El sistema SHALL presentar al estudiante, dentro del flujo de Perfil (enrollment), una pantalla dedicada de consentimiento informado, en lenguaje claro, que explique qué datos se recolectan, cómo, dónde se almacenan, por cuánto tiempo y cuáles son los derechos del titular; el texto mostrado SHALL estar versionado. La pantalla SHALL presentarse en el perfil, NO como paso del pre-examen (RN-CO-01, US-003 CA-1).

#### Scenario: El estudiante ve la pantalla de consentimiento en el perfil
- **WHEN** un estudiante autenticado realiza el enrollment en su Perfil y llega al paso de consentimiento
- **THEN** el sistema muestra una pantalla dedicada con qué/cómo/dónde/cuánto/derechos en lenguaje claro y la versión del texto vigente

#### Scenario: El acuse referencia la versión del texto mostrado
- **WHEN** el estudiante consiente la versión de texto que se le mostró en el perfil
- **THEN** el sistema asocia el acuse a esa versión exacta del texto

#### Scenario: Un cambio de versión del texto re-dispara el consentimiento
- **WHEN** la versión del texto de consentimiento vigente cambia respecto de la que consintió el estudiante
- **THEN** el sistema vuelve a presentar la pantalla de consentimiento en el perfil con la nueva versión antes de mantener el perfil completo

