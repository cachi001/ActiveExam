## 1. Modelo y migración (DB)

- [x] 1.1 Agregar el atributo `codigo_matriculacion` (`String(80)`, único) a `ComisionModel` en `backend/app/infrastructure/persistence/models/exam_content.py`, con su restricción de unicidad global nombrada (p. ej. `uq_comision_codigo_matriculacion`).
- [x] 1.2 Crear la migración slim `backend/migrations/versions/0038_c69_comision_codigo_matriculacion_slim.py` con `revision = "0038"`, `down_revision = "0037"`, aditiva en dos pasos: (a) `add_column` nullable, (b) backfill de las comisiones existentes con un código único `{materia.codigo}-{sufijo}`, (c) aplicar `UNIQUE` (+ `NOT NULL` si el backfill garantiza no-nulos). `downgrade` dropea el constraint y la columna, sin tocar otras tablas.
- [x] 1.3 Verificar el ciclo `alembic upgrade head` → `alembic downgrade 0037` → `upgrade head` sobre una base con comisiones preexistentes (backfill deja todas con código único).

## 2. Generación de código (dominio/aplicación)

- [x] 2.1 Implementar un helper de generación de `codigo_matriculacion` en la capa `application/exam_content` (formato `{materia.codigo}-{sufijo}`, sufijo aleatorio de alfabeto sin caracteres ambiguos), reutilizable por alta y rotación.
- [x] 2.2 (RED) Test del helper: genera con el prefijo de materia, sufijo del largo esperado, y reintenta ante colisión de unicidad hasta obtener un código libre (contra DB real/efímera, sin mocks de DB).
- [x] 2.3 (GREEN) Implementar el reintento ante colisión (`23505`) apoyándose en la unicidad de DB; triangular con un segundo caso (colisión forzada → segundo intento libre).
- [x] 2.4 Agregar `ComisionSqlRepository.obtener_por_codigo_matriculacion(codigo)` en `backend/app/infrastructure/persistence/repositories/exam_content.py` (lookup global por código).

## 3. Alta/edición de comisión con código (backend)

- [x] 3.1 Extender `ComisionCrearRequest` (y el request de edición) en `backend/app/presentation/api/v1/exam_content/schemas.py` con `codigo_matriculacion: str | None` opcional, manteniendo `model_config = ConfigDict(extra="forbid")`.
- [x] 3.2 Extender `MateriaComisionService.crear_comision` (y la edición) en `backend/app/application/exam_content/materia_comision_service.py`: si no viene código, autogenerar con el helper (2.1); si viene, validarlo por unicidad.
- [x] 3.3 Incluir `codigo_matriculacion` en `ComisionResponse` para que el docente lo vea tras crear/editar.
- [x] 3.4 (RED→GREEN) Tests contra DB real: alta sin código autogenera uno único; alta con código provisto lo usa; alta con código duplicado → error de duplicado.

## 4. Auto-matriculación por código — endpoint estudiante (backend)

- [x] 4.1 Definir errores de aplicación necesarios en `backend/app/application/exam_content/errors.py` (p. ej. `CodigoMatriculacionInvalidoError`) y reutilizar `InscripcionDuplicadaError` del dominio.
- [x] 4.2 Implementar el caso de uso `InscripcionService.inscribir_por_codigo(codigo, usuario_id)` en `backend/app/application/exam_content/inscripcion_service.py`: lookup por código (4→404 si no existe) y `InscripcionSqlRepository.inscribir(...)`; capturar `InscripcionDuplicadaError` para respuesta idempotente amistosa.
- [x] 4.3 Agregar el schema `InscribirPorCodigoRequest { codigo_matriculacion: str }` y su response (comisión/materia matriculada + flag `ya_inscripto`) en `schemas.py`, ambos con `extra='forbid'`.
- [x] 4.4 Agregar la ruta `POST /api/v1/exam-content/inscribirme` al **router de rendición auth-only** (`create_exam_taking_router`), tomando el `usuario_id` del principal autenticado (NUNCA del body). Mapear `CodigoMatriculacionInvalidoError`→404/422 y `InscripcionDuplicadaError`→respuesta idempotente (200 no-op o 409 informado).
- [x] 4.5 (RED→GREEN→TRIANGULATE) Tests de endpoint contra DB real: happy path (código válido → inscripción creada); código inválido/inexistente → rechazo sin crear inscripción; código vacío/malformado → 422; ya-inscripto → idempotente sin duplicar.
- [x] 4.6 (Test) La matriculación por código NO altera el gate `puede_rendir` (sigue gobernado por consentimiento + biometría vigente).

## 5. Gestión del código por el docente (backend)

- [x] 5.1 Agregar en `create_exam_content_router` (admin-only) el endpoint de consulta del `codigo_matriculacion` de una comisión (o incluirlo en la respuesta existente de la comisión).
- [x] 5.2 Agregar el endpoint de rotación del código (regenera uno único con el helper de 2.1, reemplaza el anterior; las inscripciones existentes quedan intactas).
- [x] 5.3 (Test) Rotación genera un código nuevo y único y no desmatricula a nadie (las filas de `inscripcion` de esa comisión permanecen).

## 6. Coexistencia con inscripción manual (backend)

- [x] 6.1 (Test) La inscripción manual (`POST /comisiones/{comision_id}/inscripciones`) sigue funcionando sin cambios tras el feature.
- [x] 6.2 (Test) Un alumno inscripto manualmente que luego envía el `codigo_matriculacion` de esa comisión no se duplica (idempotente).

## 7. Seed de demo

- [x] 7.1 En `backend/scripts/seed_users.py` `_seed_contenido()`, setear un `codigo_matriculacion` de demo (p. ej. `PROG1-C1`) en la Comisión C1, manteniendo la idempotencia del seed.

## 8. Frontend — docente (crear/editar comisión)

- [x] 8.1 Agregar `codigo_matriculacion` a `FormComision`/tipos en `frontend/src/screens/admin/components/materiasComisionesTypes.ts` (y `FORM_COMISION_VACIO`).
- [x] 8.2 Mostrar en el form de `frontend/src/screens/admin/components/ComisionesAccordionBody.tsx` el código autogenerado en un campo editable + botón "Copiar".
- [x] 8.3 Cablear el envío/lectura del código en `frontend/src/lib/examContentAdmin.ts` (crear/actualizar comisión).

## 9. Frontend — alumno (unirse con un código)

- [x] 9.1 Agregar la función de auto-matriculación (POST a `/api/v1/exam-content/inscribirme` con `{ codigo_matriculacion }`) en `frontend/src/lib/api.ts` / `frontend/src/lib/examContentBrowse.ts` (fetch + authProvider, sin axios).
- [x] 9.2 Agregar en `frontend/src/screens/AlumnoMaterias.tsx` la acción "Unirme con un código" (input + botón) que postea el código, maneja éxito / código inválido / ya-inscripto, y refetchea materias/comisiones. Componentes React en PascalCase.

## 10. Validación final

- [x] 10.1 Correr la suite de tests backend (DB real/efímera, sin mocks) y verificar que todos los escenarios de las specs `matriculacion-por-codigo` y `exam-content-model` quedan cubiertos.
- [x] 10.2 `openspec validate c-70-matriculacion-por-codigo --strict` sin errores.
