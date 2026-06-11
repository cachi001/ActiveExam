# biometric-reference-renewal Specification

## Purpose
TBD - created by archiving change c-22-perfil-biometrico-enrollment. Update Purpose after archive.
## Requirements
### Requirement: La referencia biométrica tiene vigencia configurable
El sistema SHALL asignar a cada referencia biométrica capturada un período de vigencia configurable con valor por defecto de 24 meses, registrando la fecha de captura y la fecha de expiración; la vigencia SHALL NO estar hardcodeada.

#### Scenario: La referencia recibe vigencia al capturarse
- **WHEN** un estudiante completa la captura de referencia biométrica
- **THEN** el sistema registra la fecha de captura y calcula la fecha de expiración aplicando el período de vigencia configurado (por defecto 24 meses)

#### Scenario: El período de vigencia es configurable
- **WHEN** un administrador define un período de vigencia distinto del valor por defecto
- **THEN** el sistema aplica ese período a las nuevas capturas de referencia sin requerir cambios de código

### Requirement: La referencia caducada bloquea rendir hasta renovar
El sistema SHALL tratar como no vigente toda referencia biométrica cuya fecha de expiración fue superada; un estudiante con referencia caducada SHALL poder gestionar su perfil pero NO SHALL quedar habilitado para rendir hasta renovar la referencia.

#### Scenario: Referencia caducada marca el perfil para renovación
- **WHEN** la fecha de expiración de la referencia de un estudiante fue superada
- **THEN** el sistema marca la referencia como caducada y solicita su renovación al acceder al perfil

#### Scenario: Referencia caducada no habilita rendir
- **WHEN** un estudiante con referencia caducada intenta inscribirse o rendir
- **THEN** el sistema no lo habilita hasta que renueve la referencia

### Requirement: Renovación anticipada gatillada por deriva del embedding
El sistema SHALL permitir que la verificación silenciosa continua, al detectar deriva sostenida del embedding respecto de la referencia, marque la referencia para renovación anticipada; esa deriva SHALL NO sancionar ni invalidar por sí sola una rendición en curso (L2.5, decisión humana).

#### Scenario: Deriva sostenida gatilla renovación anticipada
- **WHEN** la verificación silenciosa continua detecta deriva sostenida del embedding sobre el umbral configurado
- **THEN** el sistema marca la referencia para renovación anticipada y la solicita en el próximo acceso al perfil

#### Scenario: La deriva no sanciona la rendición en curso
- **WHEN** se detecta deriva del embedding durante una rendición
- **THEN** el sistema genera el flag de renovación pero no sanciona ni invalida automáticamente la rendición

