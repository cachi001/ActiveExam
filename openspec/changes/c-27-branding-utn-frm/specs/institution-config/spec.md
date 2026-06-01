## ADDED Requirements

### Requirement: Módulo central de configuración institucional
El sistema SHALL proveer un módulo TypeScript en `frontend/src/config/institution.ts` que exporte un objeto `INSTITUTION` tipado con la identidad institucional canónica de UTN FRM. Los valores default SHALL corresponder a UTN Regional Mendoza. Cada campo SHALL ser overrideable mediante la variable de entorno Vite correspondiente (`VITE_INSTITUTION_<CAMPO>`), evaluada en build-time.

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

### Requirement: Variables de entorno Vite declaradas en tipos
El proyecto SHALL declarar las variables de entorno `VITE_INSTITUTION_*` en `frontend/src/vite-env.d.ts` bajo la interfaz `ImportMetaEnv`, de modo que TypeScript infiera el tipo `string | undefined` sin errores de compilación.

#### Scenario: Ausencia de error de tipo al acceder a VITE_INSTITUTION_NOMBRE
- **WHEN** el módulo `institution.ts` accede a `import.meta.env.VITE_INSTITUTION_NOMBRE`
- **THEN** TypeScript no emite error de tipo en la expresión

### Requirement: Footer y soporte de la shell institucional
La shell de la aplicación SHALL mostrar la identidad institucional correcta leyendo del módulo `INSTITUTION`, no de strings hardcodeados. El footer SHALL mostrar "Self-hosted · {INSTITUTION.nombreCorto}" y el link de soporte SHALL mostrar "{INSTITUTION.soporteLabel}".

#### Scenario: Footer muestra UTN FRM por defecto
- **WHEN** la aplicación carga sin override de env vars
- **THEN** el footer de la shell muestra "Self-hosted · UTN FRM"

#### Scenario: Link de soporte muestra institución correcta
- **WHEN** la aplicación carga sin override de env vars
- **THEN** el texto del link de soporte en la shell muestra "Soporte UTN FRM"

### Requirement: Pantalla de login con identidad institucional correcta
La pantalla de login SHALL mostrar el nombre completo de la institución y el label del botón de ingreso leyendo del módulo `INSTITUTION`.

#### Scenario: Título de login muestra nombre completo
- **WHEN** el usuario accede a la pantalla de login sin override de env vars
- **THEN** el título muestra "Universidad Tecnológica Nacional — Facultad Regional Mendoza" (o equivalente usando `INSTITUTION.nombre` + `INSTITUTION.facultad`)

#### Scenario: Botón de login muestra label institucional
- **WHEN** el usuario accede a la pantalla de login sin override de env vars
- **THEN** el botón de ingreso muestra "Ingresar con UTN FRM ID" (usando `INSTITUTION.loginLabel`)

### Requirement: Panel de revisor con jurisdicción institucional correcta
La pantalla de revisor SHALL mostrar la sigla institucional correcta en la cabecera de jurisdicción, leyendo del módulo `INSTITUTION`.

#### Scenario: Header del revisor muestra sigla UTN FRM
- **WHEN** un revisor accede a su panel sin override de env vars
- **THEN** la jurisdicción mostrada en el header del revisor incluye "UTN FRM" (usando `INSTITUTION.nombreCorto`)

### Requirement: IDs de exámenes mock con prefijo institucional
Los datos mock de exámenes en `frontend/src/lib/api.ts` SHALL usar el prefijo `INSTITUTION.idPrefix` para construir sus IDs, eliminando el prefijo "UBA" hardcodeado. Las materias SHALL corresponder al Ciclo Básico Unificado de carreras de Ingeniería UTN.

#### Scenario: IDs de exámenes mock usan prefijo FRM
- **WHEN** `api.ts` genera los datos mock de exámenes
- **THEN** todos los IDs de examen tienen la forma `EX-FRM-<CÓDIGO>` (ej. `EX-FRM-AMAT-I`)

#### Scenario: Materias mock son coherentes con Ingeniería UTN
- **WHEN** `api.ts` genera los datos mock de exámenes
- **THEN** los nombres de materias incluyen materias del CBU de Ingeniería (ej. "Análisis Matemático I", "Física I", "Algoritmos y Estructuras de Datos I", "Sistemas de Representación")

### Requirement: Datos mock de staff con dominio e IDs institucionales correctos
Los datos mock de staff docente en `frontend/src/lib/api.ts` SHALL usar `INSTITUTION.dominioEmail` para los emails y `INSTITUTION.idPrefix` para los `id_institucional`, eliminando referencias a "@uba.ar" y "UBA-DOC-*" hardcodeadas.

#### Scenario: Emails de staff mock usan dominio frm.utn.edu.ar
- **WHEN** `api.ts` genera los datos mock de staff
- **THEN** todos los emails del staff tienen el formato `usuario@frm.utn.edu.ar`

#### Scenario: IDs de staff mock usan prefijo FRM
- **WHEN** `api.ts` genera los datos mock de staff
- **THEN** los `id_institucional` del staff tienen el formato `FRM-DOC-<número>`
