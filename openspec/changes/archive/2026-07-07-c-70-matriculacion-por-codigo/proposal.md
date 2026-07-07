## Why

Hoy el docente tiene que inscribir a mano a cada alumno en una comisión: no escala y es la tarea más tediosa del alta de una cursada. Moodle resuelve esto con la "clave de matriculación" (enrolment key): el docente comparte un código y cada alumno se auto-matricula. Este change trae ese modelo a ActiveExam para que el alumno se inscriba solo a UNA comisión con un código, sin sacar la inscripción manual que ya existe.

## What Changes

- Cada **comisión** gana un `codigo_matriculacion` **único** (a nivel global): al crear la comisión el sistema propone un código aleatorio derivado del código de la materia (p. ej. `PROG1-7K2Q`) y el docente lo puede editar. Colisión al generar → se reintenta.
- **Backend — alta de comisión**: el endpoint de creación acepta un `codigo_matriculacion` opcional; si no viene, lo autogenera garantizando unicidad.
- **Backend — nuevo endpoint de auto-matriculación**: un alumno postea un código y el sistema valida que mapee a una comisión, crea la `inscripcion` (idempotente: ya-inscripto = no-op amistoso / 409) y respeta la elegibilidad/`puede_rendir` existente.
- **Backend — gestión del código por el docente**: endpoint para leer/rotar el `codigo_matriculacion` de una comisión.
- **Frontend — docente**: el formulario de crear/editar comisión muestra el código autogenerado en un campo editable con botón de copiar.
- **Frontend — alumno**: acción "Unirme con un código" que postea el código y se une a la comisión.
- **La inscripción manual coexiste**: no se toca ni se remueve el camino de inscripción manual del docente. Los dos caminos conviven sobre la misma tabla `inscripcion`.
- **DB**: migración slim aditiva (dos pasos, unicidad con backfill) que agrega `codigo_matriculacion` único a `comision` y backfillea las comisiones existentes con códigos generados. El seed de demo (materia PROG1 → Comisión C1) recibe un `codigo_matriculacion` de ejemplo.

Sin BREAKING: la columna nace opcional/backfilleada y todos los caminos previos siguen funcionando.

## Capabilities

### New Capabilities
- `matriculacion-por-codigo`: auto-matriculación del alumno a una comisión mediante un código único (modelo enrolment key de Moodle): validación del código, creación idempotente de la inscripción respetando elegibilidad, y gestión (generación/edición/rotación/copiado) del código por el docente. Convive con la inscripción manual.

### Modified Capabilities
- `exam-content-model`: la **comisión** se extiende con `codigo_matriculacion` único (autogenerado a partir del código de materia, editable, con manejo de colisión). El requisito "Modelo persistente de materia y comisión" incorpora el nuevo atributo y su unicidad.

## Impact

- **DB / migraciones**: nueva migración slim `0038` (chain desde head `0037`) — aditiva en dos pasos: agrega columna nullable, backfillea códigos únicos, luego aplica `UNIQUE` (+ `NOT NULL`). Backfill de comisiones existentes.
- **Modelo ORM**: `ComisionModel` en `backend/app/infrastructure/persistence/models/exam_content.py` (nuevo atributo `codigo_matriculacion`).
- **Backend API**: alta de comisión (acepta/autogenera código), nuevo endpoint de auto-matriculación por código, endpoint de lectura/rotación del código. Schemas Pydantic nuevos con `extra='forbid'`.
- **Lógica de dominio**: nuevo caso de uso "matricularse por código"; reutiliza el repositorio de inscripción y la lógica de elegibilidad/`puede_rendir` existente sin duplicarla.
- **Frontend**: formulario de comisión del docente (campo código + copiar) y acción "Unirme con un código" del alumno (React, PascalCase).
- **Seed**: `backend/scripts/seed_users.py` `_seed_contenido()` setea un `codigo_matriculacion` de demo en la Comisión C1.
- **Tests**: cobertura backend contra DB real/efímera (sin mocks de DB): unicidad de generación, happy path de matriculación, código inválido, ya-inscripto, y coexistencia con inscripción manual.
