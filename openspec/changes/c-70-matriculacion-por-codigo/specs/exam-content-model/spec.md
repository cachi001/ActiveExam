## MODIFIED Requirements

### Requirement: Modelo persistente de materia y comisión
El sistema SHALL persistir **materia** (con `codigo` único y `nombre`) y **comisión** (con `codigo`, `nombre`, una FK obligatoria a su materia, opcionalmente período/cuatrimestre y año, y un `codigo_matriculacion` **único** a nivel global). Una comisión SHALL pertenecer a **exactamente una** materia. La combinación (`materia_id`, `codigo`) de una comisión SHALL ser única. El `codigo_matriculacion` SHALL ser único entre todas las comisiones, SHALL autogenerarse a partir del `codigo` de la materia con un sufijo aleatorio corto cuando no se provee, y SHALL ser editable por el docente (ver capability `matriculacion-por-codigo`). Materia y comisión son un requisito real del producto (se modelan y persisten, NO se difieren a otro change), pero su asociación con un examen es **opcional en el MVP** (ver requisito siguiente). La migración que agrega `codigo_matriculacion` SHALL ser **aditiva** (rama slim, no toca tablas existentes) y **en dos pasos** para poder aplicar unicidad sobre filas existentes: agregar la columna nullable, backfillear un código único por comisión existente y luego aplicar la restricción `UNIQUE`.

#### Scenario: Persistir una materia con sus comisiones
- **WHEN** se crea una materia y una comisión que la referencia
- **THEN** la materia y la comisión quedan persistidas y recuperables, y la comisión queda ligada a exactamente esa materia

#### Scenario: La combinación materia + código de comisión es única
- **WHEN** se intenta persistir una segunda comisión con el mismo `codigo` dentro de la misma materia
- **THEN** el sistema rechaza la operación por violación de unicidad de (`materia_id`, `codigo`)

#### Scenario: Una comisión no puede existir sin materia
- **WHEN** se intenta persistir una comisión sin materia asociada
- **THEN** el sistema rechaza la operación: toda comisión pertenece a exactamente una materia

#### Scenario: La comisión persiste un código de matriculación único
- **WHEN** se crea una comisión (con o sin `codigo_matriculacion` provisto)
- **THEN** la comisión queda persistida con un `codigo_matriculacion` no nulo y único entre todas las comisiones

#### Scenario: Migración aditiva en dos pasos backfillea las comisiones existentes
- **WHEN** se aplica la migración que agrega `codigo_matriculacion` sobre una base con comisiones preexistentes
- **THEN** cada comisión existente recibe un `codigo_matriculacion` único generado durante el backfill
- **THEN** la restricción `UNIQUE` queda aplicada sin violar la unicidad de las filas backfilleadas
- **THEN** el `alembic downgrade` remueve la columna sin afectar otras tablas
