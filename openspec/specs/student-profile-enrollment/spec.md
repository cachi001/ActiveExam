# student-profile-enrollment Specification

## Purpose
TBD - created by archiving change c-22-perfil-biometrico-enrollment. Update Purpose after archive.
## Requirements
### Requirement: Perfil del alumno como hogar del enrollment único
El sistema SHALL ofrecer una pantalla de Perfil del alumno donde el estudiante realiza, una sola vez, el enrollment compuesto por consentimiento informado y captura de referencia biométrica; este enrollment SHALL ser reutilizable y NO SHALL repetirse por examen ni justo antes de rendir.

#### Scenario: El alumno accede al perfil para enrollarse
- **WHEN** un estudiante autenticado abre su Perfil sin enrollment previo
- **THEN** el sistema presenta el flujo de enrollment con los pasos de consentimiento y captura de referencia biométrica

#### Scenario: El enrollment no se repite por examen
- **WHEN** un estudiante con enrollment vigente se inscribe o inicia el pre-examen de cualquier examen
- **THEN** el sistema no le solicita repetir el consentimiento ni la captura de referencia, y usa el enrollment existente

### Requirement: Gate de perfil completo habilita inscribirse y rendir
El sistema SHALL considerar el perfil completo cuando exista un consentimiento válido vigente (o la vía alternativa sin biometría elegida) y una referencia biométrica vigente; solo con el perfil completo el estudiante SHALL poder inscribirse o rendir, alimentando la condición `puedeRendir`.

#### Scenario: Perfil completo habilita rendir
- **WHEN** un estudiante tiene consentimiento válido vigente y referencia biométrica vigente
- **THEN** el sistema marca su perfil como completo y lo habilita para inscribirse y rendir

#### Scenario: Perfil incompleto bloquea rendir
- **WHEN** un estudiante no tiene consentimiento válido o no tiene referencia biométrica vigente
- **THEN** el sistema marca su perfil como incompleto y no lo habilita para inscribirse ni rendir

#### Scenario: Vía alternativa completa el perfil sin biometría
- **WHEN** un estudiante eligió la vía alternativa sin biometría y tiene consentimiento válido vigente
- **THEN** el sistema marca su perfil como completo y deriva la verificación de identidad al proctor humano

