# profile-consent-persistence Specification

## Purpose
TBD - created by archiving change c-68-configuracion-sistema-funcional. Update Purpose after archive.
## Requirements
### Requirement: Consentimiento de perfil persistido server-side por usuario
El sistema SHALL persistir el consentimiento de perfil del usuario en una tabla `consentimiento_perfil` atada a `usuario_id`, con `version_texto`, `hash_texto`, `timestamp`, `estado` (`otorgado` | `revocado` | `via_alternativa`) y un hash de integridad del registro. El consentimiento SHALL NO depender de `localStorage` ni de ningún almacenamiento del cliente (RN-CO-01, cliente = sensor no confiable). La tabla SHALL existir tanto en el esquema **full** como en el **activeexam** (Railway prod).

#### Scenario: El consentimiento persiste atado al usuario
- **WHEN** un estudiante otorga el consentimiento de perfil
- **THEN** el sistema SHALL persistir una fila en `consentimiento_perfil` con su `usuario_id`, versión, hash y timestamp, recuperable en sesiones futuras desde el servidor

#### Scenario: Tabla presente en activeexam y full
- **WHEN** se inspecciona el esquema de producción (activeexam) y el full
- **THEN** la tabla `consentimiento_perfil` SHALL existir en ambos

### Requirement: Consentimiento versionado y demostrable
El consentimiento de perfil SHALL registrar la versión del texto consentido y un hash del texto, de modo que sea **demostrable** qué texto exacto consintió el usuario y cuándo (Ley 25.326, RN-CO-01).

#### Scenario: Se registra la versión exacta consentida
- **WHEN** un estudiante consiente la versión de texto vigente
- **THEN** el registro SHALL contener `version_texto` y `hash_texto` correspondientes al texto presentado

#### Scenario: Cambio de versión de texto requiere nuevo consentimiento
- **WHEN** la `consent_version_vigente` cambia y el usuario tiene un consentimiento de una versión anterior
- **THEN** el sistema SHALL tratar el consentimiento como desactualizado y requerir un nuevo otorgamiento

### Requirement: Consentimiento revocable preservando el histórico
El usuario SHALL poder revocar su consentimiento de perfil. La revocación SHALL registrarse como un nuevo estado (append-only) preservando el histórico; el estado vigente SHALL ser la fila más reciente por `usuario_id`.

#### Scenario: Revocar registra estado sin borrar histórico
- **WHEN** un estudiante revoca su consentimiento de perfil
- **THEN** el sistema SHALL insertar una fila con `estado='revocado'` y el histórico anterior SHALL permanecer intacto

#### Scenario: El estado vigente es el más reciente
- **WHEN** un usuario otorgó, revocó y volvió a otorgar el consentimiento
- **THEN** el estado vigente consultado SHALL ser `otorgado` (la fila más reciente)

### Requirement: Endpoints de consentimiento de perfil
El sistema SHALL exponer endpoints para otorgar (`POST /api/v1/consent/profile`), consultar el estado vigente (`GET /api/v1/consent/profile`) y revocar (`POST /api/v1/consent/profile/revoke`) el consentimiento de perfil. El otorgamiento SHALL exigir una marca de acción afirmativa explícita sin valor por defecto, y SHALL rechazar en backend cualquier registro sin ella (RN-CO-02). Los schemas SHALL declarar `extra='forbid'`.

#### Scenario: Otorgamiento sin acción afirmativa es rechazado
- **WHEN** se intenta otorgar el consentimiento de perfil sin la marca de acción afirmativa explícita
- **THEN** el sistema responde 422 y no persiste ningún consentimiento

#### Scenario: Consulta del estado vigente
- **WHEN** un usuario autenticado consulta `GET /api/v1/consent/profile`
- **THEN** el sistema SHALL retornar su estado de consentimiento vigente (otorgado/revocado/via_alternativa/inexistente)

### Requirement: Eliminación del consentimiento de perfil al egreso
El consentimiento de perfil de un estudiante SHALL eliminarse al egreso del estudiante de la institución, integrado con el motor de retención/DSR (RN-BIO-08, RN-DSR-03), difiriéndose ante holds por casos abiertos.

#### Scenario: Egreso elimina el consentimiento de perfil
- **WHEN** un estudiante egresa y no tiene casos abiertos (holds)
- **THEN** el sistema SHALL eliminar su consentimiento de perfil junto con los demás datos personales

#### Scenario: Hold difiere la eliminación
- **WHEN** un estudiante egresa pero tiene un caso abierto (hold)
- **THEN** la eliminación del consentimiento de perfil SHALL diferirse hasta que el hold se levante

