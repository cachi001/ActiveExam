# Spec — retry-and-escalation

> Hasta 2 reintentos; al 3.º fallo → evento crítico + escalación a proctor, nunca abort ni sanción automática (RN-BIO-04, RN-GLB-02, L2.5).

## ADDED Requirements

### Requirement: Reintentos acotados y escalación a proctor sin sanción automática
El sistema SHALL permitir hasta 2 reintentos de verificación de identidad; al 3.º fallo SHALL generar un evento crítico y escalar a un proctor humano; SHALL NO abortar el examen ni declarar automáticamente un veredicto de impostor (RN-BIO-04, RN-GLB-02, US-004 CA-5, L2.5).

#### Scenario: Reintentos disponibles tras un fallo
- **WHEN** un intento de verificación falla y aún quedan reintentos
- **THEN** el sistema ofrece un nuevo intento al estudiante

#### Scenario: Tercer fallo genera evento crítico y escala a proctor
- **WHEN** el estudiante falla el tercer intento de verificación
- **THEN** el sistema genera un evento crítico y escala la verificación a un proctor humano

#### Scenario: El fallo nunca aborta ni sanciona automáticamente
- **WHEN** se agotan los reintentos de verificación
- **THEN** el sistema no aborta abruptamente el examen ni emite ninguna sanción automática; la decisión queda en manos del proctor humano
