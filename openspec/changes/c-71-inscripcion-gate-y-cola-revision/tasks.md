## 1. Consulta base: resolución de identidad e inscripción (TDD)

- [x] 1.1 RED: test que, dado `id_institucional` y `comision_id`, resuelve `usuario.id` y responde si existe fila en `inscripcion` — contra DB real, sin mocks
- [x] 1.2 GREEN: `InscripcionSqlRepository.esta_inscripto_institucional(id_institucional, comision_id)` (JOIN usuario ↔ inscripcion); triangular: inscripto → True, no inscripto → False, id inexistente → False
- [x] 1.3 RED/GREEN: `comision_ids_inscriptas(id_institucional)` → ids de comisiones inscriptas; vacía si no hay inscripciones

## 2. Catálogo filtrado por inscripción (TDD)

- [x] 2.1 SAFETY NET: correr los tests existentes de `listar_examenes_contenido` y capturar baseline
- [x] 2.2 RED: test HTTP `GET /exam-content` como ESTUDIANTE inscripto en C1 → devuelve solo exámenes de C1; como estudiante SIN inscripción → lista vacía
- [x] 2.3 GREEN: filtrar en `ExamenContenidoSqlRepository.listar_paginado` por comisiones inscriptas cuando el rol es estudiante (JOIN inscripcion por usuario_id)
- [x] 2.4 TRIANGULATE: test que como ADMIN el catálogo sigue completo (sin filtro por inscripción)

## 3. "Mis materias" derivado de inscripción (TDD)

- [x] 3.1 RED: test del endpoint/consulta de "mis materias" → solo comisiones inscriptas del principal; vacío sin inscripción
- [x] 3.2 GREEN: implementar la fuente de "mis materias" desde `inscripcion` (materia + comisión por usuario_id)

## 4. Gate puede_rendir con inscripción (TDD)

- [x] 4.1 RED: test que `puede_rendir(examen)` con perfil completo pero SIN inscripción → `{ puede: false, razon: "no_inscripto" }`
- [x] 4.2 GREEN: sumar la condición `esta_inscripto(usuario, examen.comision_id)` al gate (además de perfil)
- [x] 4.3 TRIANGULATE: perfil completo + inscripto → `{ puede: true }`; perfil incompleto (con o sin inscripción) → razón de perfil

## 5. Backstop server-side en crear_sesion (TDD)

- [x] 5.1 SAFETY NET: baseline verde de los tests de `crear_sesion`/enforcement
- [x] 5.2 RED: test `POST /sessions` con `examen_contenido_id` de una comisión donde el alumno NO está inscripto → 403 `no_inscripto`, sin crear sesión
- [x] 5.3 GREEN: verificación de inscripción junto a `verificar_enforcement` en `crear_sesion` (403 `no_inscripto`)
- [x] 5.4 TRIANGULATE: inscripto + perfil OK → sesión creada (201); modo 'test' sin `examen_contenido_id` → no exige inscripción

## 6. Frontend (consumir lo filtrado + estados vacíos)

- [x] 6.1 Mis Materias: mostrar solo lo que devuelve el backend; estado vacío con CTA "Matricularme con un código" cuando no hay inscripciones
- [x] 6.2 Mis Exámenes: idem catálogo filtrado; card con razón `no_inscripto` → CTA matricularse (si aplicara)
- [x] 6.3 Verificar que no queda ningún filtrado ni catálogo hardcodeado en el frontend; typecheck verde

## 7. Cierre

- [x] 7.1 Suite backend afectada (exam-content + sessions + gate) verde, sin mocks de DB
- [x] 7.2 Decidir datos demo: matricular EST-00x a C1 en el seed, o dejar que se auto-matriculen con `PROG1-C1` (resolver Open Question)
- [x] 7.3 Registrar C-71 en CHANGES.md (agregado en la sección "Examen en plataforma", sucesor de c-70; corregido c-70 a archivado)
