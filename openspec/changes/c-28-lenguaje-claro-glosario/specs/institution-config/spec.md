## MODIFIED Requirements

### Requirement: Módulo central de configuración institucional
El sistema SHALL proveer un módulo TypeScript en `frontend/src/config/institution.ts` que exporte un objeto `INSTITUTION` tipado con la identidad institucional canónica de UTN FRM. Los valores default SHALL corresponder a UTN Regional Mendoza. Cada campo SHALL ser overrideable mediante la variable de entorno Vite correspondiente (`VITE_INSTITUTION_<CAMPO>`), evaluada en build-time.

La carpeta `frontend/src/config/` SHALL ser reconocida como el punto de extensión canónico para módulos de configuración estática del frontend. Nuevos módulos de configuración (como `glossary.ts`) SHALL seguir el mismo patrón: módulo TypeScript puro, export named, sin hooks ni context providers, importable directamente por cualquier componente.

#### Scenario: Lectura del nombre institucional completo
- **WHEN** un componente importa `INSTITUTION` desde `config/institution`
- **THEN** `INSTITUTION.nombre` retorna "Universidad Tecnológica Nacional" (o el valor de `VITE_INSTITUTION_NOMBRE` si está definida en el entorno de build)

#### Scenario: Lectura del nombre corto
- **WHEN** un componente importa `INSTITUTION` desde `config/institution`
- **THEN** `INSTITUTION.nombreCorto` retorna "UTN FRM" (o el valor de `VITE_INSTITUTION_NOMBRE_CORTO` si está definida)

#### Scenario: Lectura del dominio de email
- **WHEN** un componente o módulo de datos importa `INSTITUTION` desde `config/institution`
- **THEN** `INSTITUTION.dominioEmail` retorna "frm.utn.edu.ar" (o el valor de `VITE_INSTITUTION_DOMINIO` si está definida)

#### Scenario: Lectura del prefijo de ID institucional
- **WHEN** un módulo de datos mock importa `INSTITUTION` desde `config/institution`
- **THEN** `INSTITUTION.idPrefix` retorna "FRM" (o el valor de `VITE_INSTITUTION_ID_PREFIX` si está definida)

#### Scenario: Nuevos módulos de config siguen el mismo patrón
- **WHEN** se agrega un nuevo módulo en `frontend/src/config/` (ej. `glossary.ts`)
- **THEN** el módulo es un archivo TypeScript puro con export named, sin reactividad, sin hooks, importable directamente por cualquier componente sin necesidad de un provider
