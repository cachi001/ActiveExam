# pausa-screenshot-capture Specification

## Purpose
TBD - created by archiving change c-76-panel-supervision-en-vivo. Update Purpose after archive.
## Requirements
### Requirement: Registro de screenshots del alumno durante la pausa
Durante una ventana de pausa en estado `aprobada`, el cliente SHALL capturar y subir **screenshots** del alumno, y el backend SHALL persistirlos vinculados a la sesión y a la ventana de pausa. Los screenshots son dato de cliente: el backend SHALL re-hashearlos/firmarlos server-side (regla dura #6, cadena de custodia). Las capturas NO SHALL sumar automáticamente al score (L2.5); son insumo de la revisión humana.

#### Scenario: Captura persistida y firmada durante la pausa
- **WHEN** una pausa está `aprobada` y el cliente sube un screenshot del alumno
- **THEN** el backend lo persiste firmado server-side, vinculado a la sesión y a la ventana de pausa, visible en el detalle para la revisión humana

#### Scenario: Ausencia de capturas queda como señal, no veredicto
- **WHEN** durante una ventana de pausa aprobada no llegan capturas del alumno
- **THEN** el hecho queda registrado como señal para la revisión humana, sin que el sistema emita ningún veredicto automático

#### Scenario: La captura no altera el score automáticamente
- **WHEN** se registra un screenshot durante la ventana de pausa
- **THEN** el cálculo de score no lo incorpora automáticamente; la evidencia queda para la decisión humana

