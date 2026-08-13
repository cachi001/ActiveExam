## ADDED Requirements

### Requirement: Segundo camino de alta — provisioning JIT vía LTI

Además del auto-registro público (`POST /api/v1/auth/register`, rol siempre `estudiante`/local) y el alta manual por admin (`POST /users`, rol elegido por el admin), el sistema SHALL soportar un tercer camino de alta de usuario: JIT provisioning a partir de un launch LTI 1.3 validado (ver capability `lti-jit-provisioning`). Este camino SHALL producir cuentas con `auth_provider="lti"` y rol fijo `["alumno"]` — nunca un rol elegido por el flujo LTI.

#### Scenario: Los tres caminos de alta coexisten sin conflicto

- **WHEN** existen usuarios creados por auto-registro (`local`), por admin (`local`), y por LTI (`lti`)
- **THEN** todos son usuarios válidos en `usuario`, distinguibles por `auth_provider`, y ninguno de los tres caminos puede asignarse un rol distinto al que su flujo permite (`estudiante` para auto-registro, cualquiera elegido por el admin para alta manual, `alumno` fijo para LTI)
