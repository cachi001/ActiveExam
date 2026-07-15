# review-resolution-authority Specification

## Purpose
TBD - created by archiving change c-71-inscripcion-gate-y-cola-revision. Update Purpose after archive.
## Requirements
### Requirement: El veredicto sobre la nota es un acto separado del hallazgo de revisión
El sistema SHALL modelar la decisión de revisión en **dos fases separadas**: (1) **revisión** (producir el hallazgo: `sin_hallazgos`, `aprobado`, o `caso_abierto` derivando el caso), habilitada por la capacidad `revisar_sesion`; y (2) **resolución** (el veredicto: `anulado_por_fraude` o `caso_descartado`), habilitada por la capacidad `resolver_caso`. La resolución SHALL requerir que el caso esté en estado `caso_abierto`. El acto de resolver SHALL ser explícito y distinto del acto de revisar (endpoint/comando separado), NO un modo o flag del acto de revisión.

#### Scenario: Anular la nota exige un acto de resolución separado
- **WHEN** un revisor deja una sesión en `caso_abierto` y luego se anula la nota
- **THEN** la anulación se registra mediante un acto de resolución `anulado_por_fraude` distinto del acto de revisión que dejó el caso abierto

#### Scenario: No se puede resolver un caso que no está abierto
- **WHEN** se intenta `anulado_por_fraude` o `caso_descartado` sobre una sesión cuya revisión terminó en `sin_hallazgos` o `aprobado` (caso no abierto)
- **THEN** el sistema rechaza el acto (409) sin cambiar la nota

### Requirement: La resolución que anula la nota está gateada por la capacidad `resolver_caso` server-side
El sistema SHALL exigir la capacidad `resolver_caso` para ejecutar `anulado_por_fraude` o `caso_descartado`, verificada **server-side** en cada request (backstop; el cliente es sensor no confiable). Las capacidades SHALL resolverse desde un mapa `capacidad → roles` de configuración, NO desde una lista de roles hardcodeada por endpoint. Hoy `resolver_caso` SHALL mapear al rol revisor; el mapa SHALL permitir reasignar `resolver_caso` a otra autoridad (p. ej. dirección académica) **solo por config, sin refactor** de endpoints ni lógica.

#### Scenario: Sin la capacidad resolver_caso no se anula la nota
- **WHEN** un principal sin la capacidad `resolver_caso` invoca directamente la API para anular la nota
- **THEN** el backend responde 403 y la nota no cambia, aunque el botón estuviera oculto o visible en el front

#### Scenario: La reasignación de la autoridad es solo config
- **WHEN** se reasigna `resolver_caso` del rol revisor a otra autoridad en el mapa de capacidades
- **THEN** el gating del endpoint de resolución cambia sin modificar el código del endpoint

### Requirement: Cuatro barandas para anular la nota
El sistema SHALL exigir, para `anulado_por_fraude`: (a) que sea un acto separado y explícito, distinto del flaggeo/revisión; (b) un **motivo obligatorio no vacío** más **evidencia adjunta**, registrados en el audit log **inmutable** existente (hash-chain + trigger de inmutabilidad); (c) que la decisión, el motivo y un **informe de devolución** queden **disponibles al alumno** (transparencia, SOLO en `anulado_por_fraude`); (d) que el efecto sea **reversible** mediante un acto compensatorio append-only. La nota SHALL invalidarse, NUNCA borrarse. Toda decisión (fase 1 y fase 2) SHALL requerir motivo no vacío; solo `anulado_por_fraude` exige además evidencia adjunta.

#### Scenario: Anular sin motivo o sin evidencia es rechazado
- **WHEN** se intenta `anulado_por_fraude` sin motivo o sin evidencia adjunta
- **THEN** el backend rechaza el acto (400) y la nota no cambia

#### Scenario: El acto de anulación queda en el audit log inmutable
- **WHEN** se anula la nota con motivo y evidencia
- **THEN** el acto queda registrado en el audit log de forma inmutable, distinguible del acto de revisar, con actor, propósito, motivo y referencia a la evidencia

### Requirement: Inmutabilidad del registro con reversibilidad del efecto por acto compensatorio
El sistema SHALL registrar cada acto (revisión, resolución, reversión) de forma **append-only e inmutable** en el **audit log existente** (RN-RV-06/07): un acto previo NUNCA se muta ni se borra. El estado actual de la nota SHALL derivarse del **último acto**. Revertir una anulación SHALL realizarse mediante un **nuevo acto compensatorio** (`nota_restituida`) que restituye la nota, también inmutable y auditado. El sistema SHALL exponer el veredicto de anulación al alumno por **pull** (proyectado en `MiNota` / `GET /mis-notas`), sin canal push. (El flujo de apelación que dispara la reversión pertenece a `c-18`; este change deja solo el hook: efecto derivado + veredicto expuesto por pull.)

#### Scenario: Revertir no muta el acto de anulación
- **WHEN** se restituye una nota previamente anulada
- **THEN** se registra un nuevo acto compensatorio append-only y el acto de anulación original permanece inmutable en el audit log

#### Scenario: El alumno ve el veredicto por pull
- **WHEN** se anula la nota de un alumno y el alumno consulta `MiNota`
- **THEN** `MiNota` expone el veredicto de anulación y el acceso al informe de devolución, sin que el sistema emita ninguna notificación push

### Requirement: La anulación de la nota NUNCA es automática
El sistema SHALL NOT transicionar una nota a `anulado_por_fraude` por efecto del score, de un umbral, o de cualquier automatismo. La única forma de anular la nota SHALL ser un acto humano explícito de quien tiene `resolver_caso`. El score SHALL únicamente priorizar la cola (RN-RV-07, RN-SC, regla dura de dominio #5).

#### Scenario: Un score alto no anula la nota
- **WHEN** una sesión tiene un score muy alto
- **THEN** el sistema la prioriza en la cola pero NO anula la nota; solo un acto humano con `resolver_caso` puede anularla

