# moodle-writeback-review-gate Specification

## Purpose
TBD - created by archiving change c-71-inscripcion-gate-y-cola-revision. Update Purpose after archive.

## Requirements
### Requirement: El write-back de nota a Moodle se gatea por el estado de revisión de la sesión
El sistema SHALL condicionar el envío de la nota a Moodle
(`moodle_writeback_estado`) al estado de revisión de la sesión (modelo de un
solo paso). Una sesión **sin flag** o decidida **`aprobado`** SHALL liberar el
write-back y enviarse. Una sesión **flaggeada sin decidir** (`en_cola_revision`
/ `pendiente`) SHALL **retener** (hold) el write-back: la nota NO se envía.
Una sesión decidida **`anulado`** SHALL NOT enviar nunca la nota (queda
retenida/invalidada). El gate SHALL evaluarse **al puntuar la sesión, antes
del envío**, de modo que una sesión flaggeada nunca alcance `estado =
'enviado'`.

#### Scenario: Sesión flaggeada sin decidir retiene el write-back
- **WHEN** una sesión termina con `score >= umbral` (`en_cola_revision`) y todavía no tiene decisión
- **THEN** el write-back de su nota a Moodle se retiene (no se envía) y su `estado` no pasa a `'enviado'`

#### Scenario: Sesión sin flag envía la nota
- **WHEN** una sesión termina sin flag (score bajo el umbral) o se decide `aprobado`
- **THEN** el write-back se libera y la nota se envía a Moodle

#### Scenario: Anulación no envía la nota
- **WHEN** una sesión retenida se decide `anulado`
- **THEN** la nota nunca se envía a Moodle (permanece retenida/invalidada)

#### Scenario: Decisión limpia libera un hold previo, en el mismo acto
- **WHEN** una sesión que estaba en hold (flaggeada) se decide `aprobado`
- **THEN** el write-back se libera y la nota se envía a Moodle, sin pasar por ningún estado intermedio

### Requirement: La des-escritura de una nota ya enviada a Moodle nunca es automática
El sistema SHALL NOT intentar des-escribir automáticamente en Moodle una nota que ya alcanzó `estado = 'enviado'`. Si por el orden de ejecución una sesión luego anulada llegó a `'enviado'`, la corrección hacia Moodle SHALL ser **manual** (nunca automatizada, regla dura de dominio #5). Con el gate evaluado antes del envío este caso no debería ocurrir.

#### Scenario: Nota ya enviada requiere corrección manual
- **WHEN** una nota alcanzó `estado = 'enviado'` y luego la sesión se decide `anulado`
- **THEN** el sistema no des-escribe la nota automáticamente en Moodle; la inconsistencia queda para corrección manual
