## ADDED Requirements

### Requirement: Módulo de constantes de roles con labels en español
El sistema SHALL proveer el módulo `frontend/src/lib/constants/roles.ts` que exporte `ROL_LABELS` como un `Record<string, string>` con los tres roles del MVP mapeados a sus nombres legibles en español.

#### Scenario: ROL_LABELS contiene los tres roles del MVP
- **WHEN** se importa `ROL_LABELS` desde `frontend/src/lib/constants/roles.ts`
- **THEN** `ROL_LABELS['estudiante']` SHALL ser `'Estudiante'`
- **THEN** `ROL_LABELS['proctor']` SHALL ser `'Proctor'`
- **THEN** `ROL_LABELS['admin_sistema']` SHALL ser `'Administrador del sistema'`

#### Scenario: Fallback para roles desconocidos
- **WHEN** se accede a `ROL_LABELS` con una clave no existente
- **THEN** el consumidor SHALL poder hacer fallback al identificador original sin error de runtime (el tipo `Record<string, string>` permite keys arbitrarias o se provee una función helper con fallback)
