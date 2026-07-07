## Context

La inscripción alumno↔comisión ya existe (change C-69): tabla `inscripcion` (slim `0035`), modelo `InscripcionModel`, repositorio `InscripcionSqlRepository`, servicio `InscripcionService` y endpoints **admin-only** en `create_exam_content_router` (`POST /comisiones/{comision_id}/inscripciones`). El alta de comisión vive en `MateriaComisionService.crear_comision` + `ComisionSqlRepository`, con el modelo `ComisionModel` en `backend/app/infrastructure/persistence/models/exam_content.py` (único por `(materia_id, codigo)`).

Hoy la única forma de inscribir es manual (el admin/docente elige alumnos). Este change agrega el modelo **enrolment key** de Moodle: cada comisión lleva un `codigo_matriculacion` único y el alumno se auto-matricula posteando ese código. La arquitectura es limpia y por capas: `domain` → `application` → `infrastructure/persistence` → `presentation/api`; Pydantic con `extra='forbid'` inline por schema (no hay Base compartida); migraciones slim aditivas en `backend/migrations/versions/` (head actual: **`0037`**).

Matiz importante del dominio: **hoy la inscripción NO es un gate de rendición**. La elegibilidad para rendir (`puede_rendir`) se resuelve por consentimiento vigente + referencia biométrica vigente (server-side). Este change **no** convierte la inscripción en un requisito nuevo para rendir — solo agrega una vía de auto-inscripción. Preservar ese comportamiento evita un cambio de alcance/breaking.

## Goals / Non-Goals

**Goals:**
- Agregar `codigo_matriculacion` único a `comision` (autogenerado a partir del código de materia + sufijo aleatorio, editable por el docente, colisión resuelta por reintento).
- Endpoint **estudiante** de auto-matriculación por código: valida el código → crea la inscripción, idempotente ante ya-inscripto.
- Endpoint **docente** para consultar/rotar el código de una comisión.
- Frontend: campo de código editable + copiar en el form de comisión (docente); acción "Unirme con un código" (alumno).
- Migración slim aditiva en dos pasos con backfill de comisiones existentes; seed de demo con código.

**Non-Goals:**
- NO remover ni alterar la inscripción manual (`create_exam_content_router` queda intacto).
- NO convertir la inscripción en un requisito nuevo para rendir (no se toca el gate `puede_rendir`).
- NO manejar expiración/uso limitado del código, ni cupos, ni auto-desmatriculación (fuera de alcance del MVP).
- NO federar el código con Keycloak/Moodle.

## Decisions

### D1 — El código vive en `comision`, único a nivel global
`codigo_matriculacion` es columna de `ComisionModel` con restricción `UNIQUE` global (no por materia). El alumno se une a **una** comisión concreta (la tabla `inscripcion` ya es alumno↔comisión). Alternativa descartada: código por materia (ambiguo, el alumno debe caer en una comisión específica) o tabla aparte de códigos (over-engineering para un 1:1 con la comisión).

### D2 — Autogeneración `MATERIA-SUFIJO` con reintento ante colisión
El código se genera como `{materia.codigo}-{sufijo}` donde el sufijo es aleatorio corto (p. ej. 4 chars alfanuméricos sin caracteres ambiguos). La generación vive en la capa `application` (`MateriaComisionService.crear_comision`, y un helper reutilizable para la rotación). Ante colisión de unicidad, se reintenta con otro sufijo hasta N intentos. Si el docente provee un código, se usa ese (previa validación de unicidad → error de duplicado). Alternativa descartada: UUID puro (no legible/no compartible verbalmente).

### D3 — Endpoint estudiante en el router de rendición (auth-only), NO en el admin
El endpoint de auto-matriculación debe ser invocable por `Rol.ESTUDIANTE`. El `create_exam_content_router` está protegido admin-only (`require_roles(ADMIN_EXAMENES, ADMIN_SISTEMA)`), así que NO sirve. Se agrega la ruta al router de rendición del alumno (`create_exam_taking_router`, auth-only) como `POST /api/v1/exam-content/inscribirme` con body `{ codigo_matriculacion }`. El `usuario_id` sale del principal autenticado, nunca del body (el cliente no es confiable). Alternativa descartada: exponer en el admin router (rol incorrecto) o endpoint sin auth (inseguro).

### D4 — Nuevo caso de uso reutilizando repos existentes
Se agrega `InscripcionService.inscribir_por_codigo(codigo, usuario_id)` (o `AutoenrolamientoService` análogo) que: (1) `ComisionSqlRepository.obtener_por_codigo_matriculacion(codigo)` → si no existe, error de código inválido; (2) `InscripcionSqlRepository.inscribir(usuario_id, comision_id)` reutilizando la ruta existente que ya mapea unique-violation `23505` → `InscripcionDuplicadaError`. La idempotencia se resuelve capturando `InscripcionDuplicadaError` y respondiendo amistoso (no-op / 409 informado), no como error interno. No se duplica la lógica de elegibilidad — se deja gobernada por el gate existente.

### D5 — Gestión del código por el docente (consultar/rotar) en el admin router
`GET`/acción de rotación del `codigo_matriculacion` de una comisión van en `create_exam_content_router` (admin-only), reutilizando el helper de generación de D2 y `ComisionSqlRepository`. Rotar reemplaza el código; las inscripciones existentes quedan intactas (no se toca `inscripcion`).

### D6 — Migración slim aditiva en dos pasos (backfill + UNIQUE)
Nueva migración `0038_c69_comision_codigo_matriculacion_slim.py` con `down_revision = "0037"`, en tres movimientos dentro del upgrade: (1) `add_column("comision", "codigo_matriculacion", String(80), nullable=True)`; (2) backfill: para cada comisión existente, generar un código único (SQL o loop en Python dentro de la migración) — típicamente `{materia.codigo}-{sufijo}`; (3) aplicar `UNIQUE` (índice/constraint nombrado) y, si el backfill garantiza no-nulos, `NOT NULL`. `downgrade` dropea el constraint y la columna. Es la variante "destructive-in-two-steps" aplicada a unicidad: no se puede poner `UNIQUE NOT NULL` de una sobre filas existentes sin backfillear primero. Se respeta el patrón slim (no reescribe otras tablas).

### D7 — Schemas Pydantic nuevos con `extra='forbid'` inline
`InscribirPorCodigoRequest { codigo_matriculacion: str }` y su response (comisión/materia a la que se matriculó, y flag de ya-inscripto). El alta/edición de comisión suma `codigo_matriculacion: str | None` opcional. Todos declaran `model_config = ConfigDict(extra="forbid")` (no hay Base compartida — convención inline del repo).

### D8 — Frontend fetch-based (sin axios)
Docente: agregar el campo `codigo_matriculacion` a `FormComision`/tipos en `materiasComisionesTypes.ts` y al form en `ComisionesAccordionBody.tsx`, mostrando el código con botón "Copiar"; wiring en `examContentAdmin.ts`. Alumno: input + botón "Unirme con un código" en `AlumnoMaterias.tsx`, nueva función en `api.ts`/`examContentBrowse.ts` que postea a `/inscribirme` y refetchea materias/comisiones. Componentes/archivos React en PascalCase.

## Risks / Trade-offs

- **Colisión persistente en backfill/generación** → Mitigación: sufijo con suficiente entropía + reintento acotado; el `UNIQUE` de DB es la red de seguridad final (la generación reintenta ante `23505`).
- **Unicidad global vs. legibilidad del código** → prefijar con `materia.codigo` mantiene legibilidad; el sufijo garantiza unicidad global. Trade-off aceptado: códigos algo más largos.
- **Confusión de expectativas: "matricularme me habilita a rendir"** → Mitigación: la matriculación es solo set-membership; el gate de rendición (consentimiento + biometría) sigue igual. Documentado en spec y copy del frontend.
- **Migración en dos pasos sobre prod con muchas comisiones** → el backfill recorre filas; en el stack slim/demo el volumen es bajo. Mitigación: backfill idempotente y `downgrade` limpio.
- **Endpoint estudiante mal ubicado (rol)** → Mitigación explícita (D3): va en el router auth-only del alumno; `usuario_id` del principal, nunca del body.

## Migration Plan

1. Agregar `codigo_matriculacion` a `ComisionModel`.
2. Crear `0038_c69_comision_codigo_matriculacion_slim.py` (add column nullable → backfill único → UNIQUE [+ NOT NULL]).
3. Aplicar `alembic upgrade head`; verificar que las comisiones existentes quedaron con código único.
4. Implementar generación/rotación (application), lookup por código (repo), casos de uso y endpoints.
5. Actualizar seed `_seed_contenido()` con `codigo_matriculacion` de demo (p. ej. `PROG1-C1`).
6. Frontend docente + alumno.
7. **Rollback**: `alembic downgrade 0037` dropea el constraint y la columna; el código de app tolera su ausencia solo hasta revertir el deploy (la columna es requerida por el modelo tras el merge, así que el rollback de schema va acompañado del rollback de código).

## Open Questions

- Longitud/alfabeto exactos del sufijo (propuesta: 4 chars de `ABCDEFGHJKMNPQRSTUVWXYZ23456789`, sin ambiguos). Decidible en implementación sin afectar specs.
- ¿La rotación del código debe invalidar algo más? En el MVP: no (solo reemplaza el string; inscripciones intactas).
- ¿Mostrar el código al alumno una vez matriculado? Fuera de alcance; el alumno solo lo usa para unirse.
