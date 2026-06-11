# domain-entities Specification

## Purpose
TBD - created by archiving change c-05-core-models. Update Purpose after archive.
## Requirements
### Requirement: Entidades transaccionales con cardinalidades del modelo
El modelo SHALL definir las entidades Usuario, Examen, Sesión, Asignación (proctor↔examen), Consentimiento, Embedding, Evidencia y Caso disciplinario con las cardinalidades de `04` (Usuario 1—* Sesión; Examen 1—* Sesión; Usuario 1—* Embedding; Sesión 1—* Evento; Evidencia 1—* Audit log; Evidencia 1—1 Caso disciplinario opcional; Examen *—* Usuario(proctor) vía Asignación; Usuario 1—* Consentimiento).

#### Scenario: Tablas y relaciones creadas por la migración 002
- **WHEN** se aplica la migración 002
- **THEN** existen las tablas de las 8 entidades con sus claves foráneas y la tabla de unión Asignación que materializa la relación *—* proctor↔examen

#### Scenario: Usuario provisionado just-in-time desde el IdP
- **WHEN** se modela la entidad Usuario
- **THEN** soporta provisionamiento JIT desde el IdP (sin seed masivo de usuarios), con identificador institucional, roles, email y atributos federados (`04` §Usuario)

### Requirement: Embedding cifrado y Consentimiento inmutable
El Embedding SHALL almacenar su vector **cifrado at-rest** (con `versión` y fecha, eliminable al egreso del estudiante) y el Consentimiento SHALL ser un registro **inmutable** (`versión_texto`, `timestamp`, `hash`), conforme a DD-13, SU-08 y la Ley 25.326.

#### Scenario: Vector de embedding no se almacena en claro
- **WHEN** se persiste un Embedding
- **THEN** el vector queda cifrado at-rest (no en texto plano), tratado como dato sensible por defecto (SU-08)

#### Scenario: Consentimiento sin path de modificación
- **WHEN** se registra un Consentimiento
- **THEN** queda como acuse inmutable con su hash, sin operación de update expuesta por el repositorio

