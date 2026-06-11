# Spec — informed-consent-presentation

> Pantalla dedicada de consentimiento con lenguaje claro y texto versionado, mostrada antes de la verificación biométrica (RN-CO-01, US-003 CA-1).

## ADDED Requirements

### Requirement: Pantalla de consentimiento con lenguaje claro y texto versionado
El sistema SHALL presentar al estudiante una pantalla dedicada de consentimiento informado, en lenguaje claro, que explique qué datos se recolectan, cómo, dónde se almacenan, por cuánto tiempo y cuáles son los derechos del titular; el texto mostrado SHALL estar versionado (RN-CO-01, US-003 CA-1).

#### Scenario: El estudiante ve la pantalla de consentimiento antes de la biometría
- **WHEN** un estudiante autenticado y habilitado para un examen llega al paso de consentimiento
- **THEN** el sistema muestra una pantalla dedicada con qué/cómo/dónde/cuánto/derechos en lenguaje claro y la versión del texto vigente

#### Scenario: El acuse referencia la versión del texto mostrado
- **WHEN** el estudiante consiente la versión de texto que se le mostró
- **THEN** el sistema asocia el acuse a esa versión exacta del texto
