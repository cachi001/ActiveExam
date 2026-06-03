## ADDED Requirements

### Requirement: `joinExamInfo` — función pura de join con catálogo local

El sistema SHALL agregar en `frontend/src/screens/proctoring/helpers.ts` la interfaz `ExamInfo { examNombre: string; materiaNombre: string; comisionNombre: string; docente: string }` y la función `export function joinExamInfo(examId: string | null | undefined): ExamInfo | null`.

La función SHALL buscar en `EXAMENES → COMISIONES → MATERIAS` (arrays del catálogo local importados de `'../../lib/api'`) y retornar el objeto enriquecido o `null` si cualquier lookup falla. La función SHALL ser pura: sin efectos secundarios, sin llamadas HTTP, sin acceso al store, sin hooks React. SHALL retornar `null` inmediatamente si `examId` es falsy. SHALL envolver su lógica en try/catch y retornar `null` en lugar de propagar cualquier excepción.

#### Scenario: Join exitoso con exam_id válido
- **WHEN** se llama `joinExamInfo('EXAM-AMAT-2025-01')`
- **THEN** retorna objeto con `examNombre`, `materiaNombre`, `comisionNombre` y `docente` no vacíos (datos del catálogo local)

#### Scenario: Join con exam_id null retorna null
- **WHEN** se llama `joinExamInfo(null)` o `joinExamInfo(undefined)` o `joinExamInfo('')`
- **THEN** retorna `null` sin lanzar excepción

#### Scenario: Join con exam_id inexistente retorna null
- **WHEN** se llama `joinExamInfo('ID-QUE-NO-EXISTE')`
- **THEN** retorna `null` sin lanzar excepción

### Requirement: Props opcionales `examInfo` en `SesionCard` y `SesionVivoCard`

`SesionCard` y `SesionVivoCard` SHALL aceptar prop opcional `examInfo?: ExamInfo | null`. Cuando `examInfo` es no-null, SHALL renderizar una línea adicional con nombre de materia y comisión. Cuando `examInfo` es null o undefined, el componente SHALL mantener el comportamiento existente sin cambios visibles. Los callers existentes que no pasan `examInfo` SHALL seguir compilando sin modificaciones.

#### Scenario: `SesionCard` con examInfo muestra contexto académico
- **WHEN** `SesionCard` recibe `examInfo` no-null
- **THEN** renderiza `{examInfo.materiaNombre} · {examInfo.comisionNombre}` en una línea de texto secundario

#### Scenario: `SesionCard` sin examInfo mantiene apariencia actual
- **WHEN** `SesionCard` no recibe prop `examInfo` (o recibe null)
- **THEN** el componente renderiza igual que antes, sin línea adicional

#### Scenario: Callers existentes compilan sin cambios
- **WHEN** se ejecuta `tsc --noEmit` sobre el frontend
- **THEN** los callers previos de `SesionCard` y `SesionVivoCard` no muestran errores de TypeScript por la nueva prop
