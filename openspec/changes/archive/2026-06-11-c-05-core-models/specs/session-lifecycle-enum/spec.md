# Spec — session-lifecycle-enum

> Capacidad de **ciclo de vida de la Sesión** restringido a nivel de motor. El `estado` solo admite los valores del enum del dominio. Su Done es: la base rechaza estados fuera del enum.

## ADDED Requirements

### Requirement: Estado de Sesión restringido al enum del ciclo de vida
La Sesión SHALL restringir su campo `estado` a los valores `iniciada`, `activa`, `finalizada`, `flaggeada`, `cerrada` mediante constraint a nivel de base de datos (enum/CHECK), no solo por validación de aplicación (`04` §Sesión).

#### Scenario: Estado válido aceptado
- **WHEN** se inserta una Sesión con `estado` en {iniciada, activa, finalizada, flaggeada, cerrada}
- **THEN** la inserción es aceptada por la base

#### Scenario: Estado inválido rechazado por la base
- **WHEN** se intenta insertar o actualizar una Sesión con un `estado` fuera del enum (por ejemplo `pausada`)
- **THEN** la base rechaza la operación con error de constraint, incluso si se hace por fuera de la capa de aplicación
