# Spec — optional-dni-scan

> Escaneo de DNI opcional y flaggeado para fase posterior: no bloquea el enrollment ni la habilitación para rendir, con resguardo legal del DNI como dato sensible (Ley 25.326).

## ADDED Requirements

### Requirement: El escaneo de DNI es opcional y no bloqueante
El sistema SHALL ofrecer el escaneo de DNI como un paso opcional del perfil controlado por un flag de funcionalidad; cuando el flag esté inactivo el paso SHALL presentarse como opcional/próximamente y su ausencia SHALL NO bloquear el enrollment ni la habilitación para inscribirse o rendir.

#### Scenario: La ausencia de DNI no bloquea el perfil
- **WHEN** un estudiante completa consentimiento y referencia biométrica pero no escanea el DNI
- **THEN** el sistema considera el perfil completo y lo habilita para inscribirse y rendir

#### Scenario: El flag inactivo presenta el DNI como opcional
- **WHEN** el flag de escaneo de DNI está inactivo
- **THEN** el sistema presenta el paso de DNI como opcional o próximamente, sin exigirlo

### Requirement: El DNI capturado se trata como dato sensible bajo custodia
El sistema SHALL tratar todo DNI capturado como dato sensible (Ley 25.326): persistido cifrado at-rest, con finalidad acotada a la verificación de identidad, marcado para eliminación al egreso del estudiante y con holds legales que difieren esa eliminación.

#### Scenario: El DNI capturado se persiste cifrado y con finalidad acotada
- **WHEN** un estudiante escanea su DNI con el flag activo
- **THEN** el sistema persiste el DNI cifrado at-rest, restringe su uso a la verificación de identidad y lo marca para eliminación al egreso

#### Scenario: Un hold legal difiere la eliminación del DNI
- **WHEN** existe un hold legal vigente sobre el estudiante al momento de su egreso
- **THEN** el sistema difiere la eliminación del DNI hasta que el hold se levante
