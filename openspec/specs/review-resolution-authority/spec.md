# review-resolution-authority Specification

## Purpose
TBD - created by archiving change c-71-inscripcion-gate-y-cola-revision. Update Purpose after archive.

Actualizado: no existe una "autoridad de resolución" separada de quien
revisa. El modelo de dos fases (revisión + resolución, con `caso_abierto`
como puente) fue rechazado explícitamente por el owner del proyecto. La
capacidad `revisar_sesion` cubre TODO el acto — aprobar y anular — porque no
hay segunda instancia que gatear aparte.

## Requirements
### Requirement: El veredicto sobre la nota se emite en el mismo acto que la revisión
El sistema SHALL modelar la decisión de revisión en **un solo acto**,
habilitado por la capacidad `revisar_sesion`: el revisor emite directamente
`aprobado` o `anulado`. NO SHALL existir un estado intermedio `caso_abierto`
ni un endpoint/comando separado de "resolución": anular la nota NO requiere
un segundo acto sobre un caso previamente derivado.

#### Scenario: Anular la nota no exige un acto separado
- **WHEN** un revisor decide `anulado` sobre una sesión flaggeada
- **THEN** la anulación se registra en el mismo acto de decisión, sin pasar por un estado `caso_abierto` intermedio

#### Scenario: No existe un estado "caso no abierto" que rechazar
- **WHEN** se busca la precondición "el caso debe estar abierto para resolverlo"
- **THEN** no existe: `decide` acepta `aprobado` o `anulado` directamente sobre cualquier sesión con decisión pendiente

### Requirement: La decisión que anula la nota está gateada por la capacidad `revisar_sesion` server-side
El sistema SHALL exigir la capacidad `revisar_sesion` para ejecutar `decide`
con `decision=anulado`, verificada **server-side** en cada request (backstop;
el cliente es sensor no confiable). Las capacidades SHALL resolverse desde un
mapa `capacidad → roles` de configuración, NO desde una lista de roles
hardcodeada por endpoint. `revisar_sesion` SHALL mapear a revisor,
coordinador y admin_sistema; el mapa SHALL permitir reasignarla **solo por
config, sin refactor** de endpoints ni lógica.

#### Scenario: Sin la capacidad revisar_sesion no se anula la nota
- **WHEN** un principal sin la capacidad `revisar_sesion` invoca directamente la API para anular la nota
- **THEN** el backend responde 403 y la nota no cambia, aunque el botón estuviera oculto o visible en el front

#### Scenario: La reasignación de la autoridad es solo config
- **WHEN** se reasigna `revisar_sesion` a otro conjunto de roles en el mapa de capacidades
- **THEN** el gating del endpoint de decisión cambia sin modificar el código del endpoint

### Requirement: Barandas para anular la nota
El sistema SHALL exigir, para `decision=anulado`: (a) que sea un acto humano
explícito, distinto de cualquier automatismo de flaggeo; (b) un **motivo
obligatorio no vacío** más **evidencia estructurada** (lista de `event_id`,
no texto libre) obligatoria y no vacía, registrados en el audit log
**inmutable** existente (hash-chain + trigger de inmutabilidad); (c) que la
decisión, el motivo y un **informe de devolución** —filtrado a la evidencia
elegida— queden **disponibles al alumno** (transparencia, SOLO en
`anulado`); (d) que el efecto sea **reversible** mediante un acto
compensatorio append-only. La nota SHALL invalidarse, NUNCA borrarse.
`aprobado` NO SHALL exigir evidencia ni motivo obligatorio.

#### Scenario: Anular sin motivo o sin evidencia es rechazado
- **WHEN** se intenta `decision=anulado` sin motivo o sin al menos un `event_id` de evidencia
- **THEN** el backend rechaza el acto (400) y la nota no cambia

#### Scenario: El acto de anulación queda en el audit log inmutable
- **WHEN** se anula la nota con motivo y evidencia
- **THEN** el acto queda registrado en el audit log de forma inmutable, con actor, propósito, motivo y los `event_id` de evidencia

### Requirement: Inmutabilidad del registro con reversibilidad del efecto por acto compensatorio
El sistema SHALL registrar cada acto (decisión, reversión) de forma
**append-only e inmutable** en el **audit log existente** (RN-RV-06/07): un
acto previo NUNCA se muta ni se borra. El estado actual de la nota SHALL
derivarse del **último acto**. Revertir una anulación SHALL realizarse
mediante un **nuevo acto compensatorio** (`nota_restituida`) que restituye
la nota, también inmutable y auditado. El sistema SHALL exponer el veredicto
de anulación al alumno por **pull** (proyectado en `MiNota` / `GET
/mis-notas`), sin canal push.

#### Scenario: Revertir no muta el acto de anulación
- **WHEN** se restituye una nota previamente anulada
- **THEN** se registra un nuevo acto compensatorio append-only y el acto de anulación original permanece inmutable en el audit log

#### Scenario: El alumno ve el veredicto por pull
- **WHEN** se anula la nota de un alumno y el alumno consulta `MiNota`
- **THEN** `MiNota` expone el veredicto de anulación y el acceso al informe de devolución, sin que el sistema emita ninguna notificación push

### Requirement: La anulación de la nota NUNCA es automática
El sistema SHALL NOT transicionar una nota a `anulado` por efecto del score,
de un umbral, o de cualquier automatismo. La única forma de anular la nota
SHALL ser un acto humano explícito de quien tiene `revisar_sesion`. El score
SHALL únicamente priorizar la cola (RN-RV-07, RN-SC, regla dura de dominio #5).

#### Scenario: Un score alto no anula la nota
- **WHEN** una sesión tiene un score muy alto
- **THEN** el sistema la prioriza en la cola pero NO anula la nota; solo un acto humano con `revisar_sesion` puede anularla
