# Spec — proctor-contextual-access

> MFA obligatorio para el rol proctor (RN-AU-05). DIFERIDO de C-15: el activeexam no emite
> segundo factor (ver fix C-68); entra cuando el provider JWT propio emita MFA.
>
> NOTA: el acceso contextual "solo exámenes asignados" (RN-AU-07) fue **superseded**
> por decisión del dueño (el proctor ve TODAS las revisiones, RBAC por rol). Lo
> entregado vive en la capability `proctor-contextual-access` archivada con C-15.
> Este delta cubre SOLO el segundo factor pendiente.

## ADDED Requirements

### Requirement: MFA obligatorio para el proctor
El acceso del proctor al panel SHALL requerir **MFA** (RN-AU-05); sin MFA satisfecho, el acceso al panel SHALL ser denegado.

#### Scenario: Sin MFA no hay panel
- **WHEN** un proctor intenta acceder al panel sin haber satisfecho MFA
- **THEN** el acceso es denegado hasta completar el segundo factor
