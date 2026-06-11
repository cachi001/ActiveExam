# liveness-detection Specification

## Purpose
TBD - created by archiving change c-09-biometria-liveness. Update Purpose after archive.
## Requirements
### Requirement: Liveness híbrido como prerrequisito obligatorio
El sistema SHALL ejecutar en el cliente un liveness híbrido que combine análisis pasivo (parpadeo natural involuntario, micro-movimientos faciales, profundidad 3D estimada por la geometría de los landmarks de Face Mesh) con 1–2 retos activos aleatorios; el liveness SHALL ser prerrequisito obligatorio: sin un liveness exitoso, la comparación 1:1 SHALL NO ejecutarse (RN-BIO-05, DD-18, US-004 CA-2).

#### Scenario: Liveness pasivo y reto activo superados
- **WHEN** el estudiante captura el video y supera el análisis pasivo y el reto activo aleatorio
- **THEN** el sistema considera el liveness exitoso y permite continuar a la comparación 1:1

#### Scenario: Captura sin persona viva no supera el liveness
- **WHEN** se presenta una foto o video pregrabado en lugar de una persona viva
- **THEN** el liveness no se considera exitoso y el sistema no ejecuta la comparación 1:1

#### Scenario: Los retos activos son aleatorios
- **WHEN** se inicia un intento de verificación
- **THEN** el sistema selecciona el reto o retos activos de forma aleatoria para elevar el costo de un ataque ensayado

