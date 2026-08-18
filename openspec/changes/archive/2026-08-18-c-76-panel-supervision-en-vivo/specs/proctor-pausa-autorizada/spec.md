## MODIFIED Requirements

### Requirement: Aprobación o rechazo de la pausa por el proctor
El **tutor** (docente de la comisión de la sesión) SHALL poder aprobar o rechazar una pausa solicitada de una sesión que supervisa. Cada resolución se **registra en el audit log** (acción operativa, no veredicto disciplinario). El actor registrado es el tutor. El rol `proctor` **ya no existe** — esta capacidad la absorbió el rol `tutor`.

#### Scenario: Tutor aprueba la pausa
- **WHEN** el tutor aprueba una pausa en estado `solicitada` de su comisión y la sesión no alcanzó el límite de pausas
- **THEN** la pausa pasa a `aprobada`, se registra el actor (tutor) y el inicio de la ventana, y se escribe una entrada de audit log de la acción

#### Scenario: Tutor rechaza la pausa
- **WHEN** el tutor rechaza una pausa en estado `solicitada` de su comisión
- **THEN** la pausa pasa a `rechazada`, se registra el actor y el timestamp, y se escribe una entrada de audit log; la ventana NO se abre

#### Scenario: Proctor aprueba la pausa
- **SUPERSEDED**: el rol `proctor` fue eliminado. Reemplazado por "Tutor aprueba la pausa" (arriba).

#### Scenario: Proctor rechaza la pausa
- **SUPERSEDED**: el rol `proctor` fue eliminado. Reemplazado por "Tutor rechaza la pausa" (arriba).

## ADDED Requirements

### Requirement: Límite configurable de pausas por sesión
El sistema SHALL limitar la cantidad de pausas **aprobadas** por sesión a un umbral **configurable** desde la Configuración del Sistema (`pausas_max_por_sesion`), con valor **default 2**. El límite SHALL evaluarse al **aprobar** una pausa (no al solicitarla). Cuentan hacia el límite las pausas en estado `aprobada` o `finalizada`; NO cuentan las `rechazada`/`expirada`. El umbral SHALL leerse de la configuración efectiva, nunca de un valor hardcodeado.

#### Scenario: Aprobación rechazada por límite alcanzado
- **WHEN** el tutor intenta aprobar una pausa en una sesión que ya tiene un número de pausas `aprobada`+`finalizada` igual o mayor al límite configurado
- **THEN** la aprobación se rechaza con un estado/error claro y la pausa NO pasa a `aprobada`

#### Scenario: El estudiante siempre puede solicitar
- **WHEN** el estudiante solicita una pausa aunque la sesión haya alcanzado el límite
- **THEN** la solicitud se persiste en estado `solicitada` (queda el rastro del pedido), y solo la aprobación queda bloqueada por el límite

#### Scenario: Default 2 cuando no hay config explícita
- **WHEN** no existe un valor explícito de `pausas_max_por_sesion` en la Configuración del Sistema
- **THEN** el límite aplicado es 2

### Requirement: Captura de screenshots durante la pausa aprobada
Durante una ventana de pausa en estado `aprobada`, el sistema SHALL **registrar capturas (screenshots)** del alumno para verificar la ausencia real, sin confiar únicamente en el estado "pausa aprobada". Los screenshots son dato de cliente: SHALL hashearse/firmarse server-side (regla dura #6). Las capturas NO suman automáticamente al score (L2.5): son insumo de la revisión humana. La ausencia de capturas durante la ventana SHALL quedar registrada como señal, sin emitir veredicto automático.

#### Scenario: Screenshots persistidos durante la pausa
- **WHEN** una pausa está en estado `aprobada` y el cliente sube capturas del alumno
- **THEN** las capturas se persisten firmadas server-side, vinculadas a la sesión y a la ventana de pausa, disponibles para la revisión humana

#### Scenario: Las capturas no sancionan automáticamente
- **WHEN** se registran o faltan capturas durante una ventana de pausa aprobada
- **THEN** el sistema no emite ningún veredicto automático; el hecho queda como insumo para la decisión humana
