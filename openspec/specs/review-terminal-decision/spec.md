# review-terminal-decision Specification

## Purpose
TBD - created by archiving change c-16-cola-revision-humana. Update Purpose after archive.

Actualizado: el modelo de decisión de DOS FASES (c-71 slice 2, con `caso_abierto`
como derivación a una segunda instancia de resolución) fue rechazado
explícitamente por el owner del proyecto ("no existe el caso abierto, nunca
dije que era un estado y no lo va a ser"; confirmado: "sí, un solo paso: quien
revisa decide", sin segunda instancia). El modelo vigente es de UN SOLO PASO.

## Requirements
### Requirement: Decisión terminal de exactamente una de dos opciones, en un solo acto
El sistema SHALL modelar la decisión de revisión en **un solo paso** (capacidad
`revisar_sesion`). El revisor SHALL emitir exactamente una de: **`aprobado`**
(las señales son falso positivo o no ameritan sanción; valida la nota) o
**`anulado`** (fraude determinado en el mismo acto; anula la nota). NO SHALL
existir un estado intermedio `caso_abierto` ni una segunda instancia de
resolución: quien revisa decide, en el mismo acto.

#### Scenario: La revisión emite una de dos decisiones, en un solo acto
- **WHEN** el revisor decide sobre una sesión flaggeada
- **THEN** registra exactamente una de: `aprobado` o `anulado`, sin pasar por un estado intermedio

#### Scenario: No existe una segunda instancia de resolución
- **WHEN** se busca un endpoint o capacidad de "resolver un caso abierto"
- **THEN** no existe: `revisar_sesion` cubre todo el acto, incluida la anulación

### Requirement: Decisión persistida inmutable vinculada a la evidencia
La decisión y su **fundamento** (motivo **obligatorio no vacío** cuando la
decisión es `anulado`) SHALL persistirse **inmutables** y vinculados a
evidencia **estructurada** (lista de `event_id` elegidos por el revisor, no
texto libre) cuando la decisión es `anulado` (RN-RV-06). Los actos SHALL ser
**append-only**: ningún acto previo se muta ni se borra. El efecto sobre la
nota SHALL derivarse del **último acto**, de modo que una reversión se
realice por un **nuevo acto compensatorio** (`revertir_anulacion` /
"restituir") sin alterar el registro anulatorio original.

#### Scenario: Decisión inmutable y trazable con motivo y evidencia obligatorios al anular
- **WHEN** el revisor registra una decisión `anulado`
- **THEN** se exige motivo no vacío y al menos un `event_id` de evidencia; ambos se persisten de forma inmutable, sin posibilidad de edición posterior del acto

#### Scenario: Aprobar no exige evidencia
- **WHEN** el revisor registra una decisión `aprobado`
- **THEN** el motivo es opcional y no se exige evidencia estructurada

#### Scenario: Revertir el efecto no edita el acto previo
- **WHEN** se restituye una nota previamente anulada
- **THEN** se agrega un acto compensatorio inmutable y el acto de anulación original permanece intacto

### Requirement: El sistema NUNCA sanciona automáticamente
El sistema SHALL NOT emitir ninguna sanción ni anulación de nota automática;
la decisión `anulado` SHALL ser **siempre** un acto humano explícito
(RN-RV-07, RN-DSR-04, DD-01). El score SHALL únicamente priorizar la cola. NO
SHALL existir ningún path automático desde un score/umbral hacia `anulado`.

#### Scenario: Ningún path automático sanciona ni anula la nota
- **WHEN** se recorre cualquier camino del sistema relacionado con la revisión
- **THEN** ningún path emite una sanción ni anula la nota; la única forma de un veredicto es un acto humano explícito con la capacidad `revisar_sesion`

#### Scenario: El score no decide por sí solo
- **WHEN** una sesión tiene score muy alto
- **THEN** el sistema la prioriza en la cola pero NO la anula automáticamente; un humano debe abrirla y decidir
