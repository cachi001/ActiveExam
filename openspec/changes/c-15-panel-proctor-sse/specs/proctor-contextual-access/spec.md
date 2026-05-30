# Spec — proctor-contextual-access

> Control de acceso contextual (solo exámenes asignados) con MFA obligatorio para el rol proctor (RN-AU-07, RN-AU-05).

## ADDED Requirements

### Requirement: Acceso contextual solo a exámenes asignados
El proctor SHALL acceder **únicamente** a las sesiones de los exámenes que tiene **asignados** (RN-AU-07), validado contra la entidad `Asignación`; el acceso a sesiones de exámenes no asignados SHALL ser rechazado.

#### Scenario: Proctor ve solo sus exámenes
- **WHEN** el proctor abre el panel
- **THEN** solo ve y recibe eventos de las sesiones de exámenes asignados a él

#### Scenario: Acceso a examen no asignado rechazado
- **WHEN** el proctor intenta acceder a una sesión de un examen que no tiene asignado
- **THEN** el acceso es rechazado

### Requirement: MFA obligatorio para el proctor
El acceso del proctor al panel SHALL requerir **MFA** (RN-AU-05); sin MFA satisfecho, el acceso al panel SHALL ser denegado.

#### Scenario: Sin MFA no hay panel
- **WHEN** un proctor intenta acceder al panel sin haber satisfecho MFA
- **THEN** el acceso es denegado hasta completar el segundo factor
