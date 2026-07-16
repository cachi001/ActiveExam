## MODIFIED Requirements

### Requirement: El gate puedeRendir bloquea el inicio del examen si el perfil está incompleto
El sistema SHALL habilitar `puedeRendir()` para un examen concreto SOLO si se cumplen **AMBAS** condiciones, evaluadas server-side: (1) el alumno tiene perfil completo — consentimiento válido Y un registro `embedding_referencia` con `vigente = TRUE` en la base — y (2) el alumno está **inscripto** en la comisión a la que pertenece ese examen (`examen_contenido.comision_id`), es decir existe una fila en `inscripcion` para `(usuario_id, comision_id)`. Si falta cualquiera de las dos, `puedeRendir()` SHALL retornar `{ puede: false }` con la razón correspondiente. La verificación de inscripción SHALL ser server-side por `usuario_id` del principal (JWT), nunca por dato del cliente.

#### Scenario: Gate permite rendir con perfil completo E inscripción a la comisión
- **WHEN** el alumno tiene consentimiento válido Y referencia biométrica `vigente = TRUE` Y está inscripto en la comisión del examen
- **THEN** `api.puedeRendir()` retorna `{ puede: true }`
- **THEN** el flujo navega a `/requisitos` para iniciar el examen

#### Scenario: Gate bloquea el examen si falta referencia biométrica en backend
- **WHEN** el alumno tiene consentimiento válido PERO no tiene un registro `embedding_referencia` con `vigente = TRUE` en la DB
- **THEN** `api.puedeRendir()` retorna `{ puede: false, razon: "referencia_biometrica_pendiente" }`
- **THEN** el sistema no navega a `/requisitos`

#### Scenario: Gate bloquea el examen si el alumno NO está inscripto en la comisión
- **WHEN** el alumno tiene el perfil completo PERO no existe fila en `inscripcion` para `(usuario_id, comision_id_del_examen)`
- **THEN** `api.puedeRendir()` retorna `{ puede: false, razon: "no_inscripto" }`
- **THEN** el sistema no habilita la rendición de ese examen y ofrece matricularse por código

#### Scenario: Gate bloquea si la referencia existe en localStorage pero no en backend
- **WHEN** el store Zustand o localStorage contiene un `referencia_id` pero el backend no tiene un registro `vigente = TRUE` para ese `usuario_id`
- **THEN** `api.puedeRendir()` retorna `{ puede: false, razon: "referencia_biometrica_pendiente" }`
- **THEN** la verificación es server-side y no puede ser bypasseada por manipulación del store local
