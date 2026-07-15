# Slice 1 — Gate de inscripción (HECHO y commiteado, `cd076f8`)

> Todas las tasks del slice 1 (secciones 1–7) están completas y en `main`. Se conservan como registro; no se re-implementan.

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

---

# Slice 2 — Cola de Revisión + transparencia al alumno (EN PLANIFICACIÓN)

> Gobernanza ALTO/CRÍTICO (notas + disciplina + audit): implementar en pasos, con checkpoints al owner en decisiones no obvias. TDD estricto: RED → GREEN → TRIANGULATE → REFACTOR; tests sin mocks de DB (DB real/testcontainer); Pydantic `extra='forbid'`, snake_case, PascalCase en React.

## 8. Capa de capacidades config-driven (D8) (TDD)

- [x] 8.1 RED: test que `tiene_capacidad(rol, "resolver_caso")` resuelve desde el mapa `capacidad → roles` (revisor sí; estudiante no) — puro, sin infra
- [x] 8.2 GREEN: módulo de dominio `capabilities` con `CAPABILITY_ROLES` (`revisar_sesion` → {revisor, coordinador, admin_sistema}; `resolver_caso` → {revisor}) + `require_capability(...)` dependency
- [x] 8.3 TRIANGULATE: reasignar `resolver_caso` a otro rol en el mapa cambia el gating sin tocar el endpoint (test); rol sin capacidad → deniega

## 9. Modelo de decisión de dos fases unificado (D6/D7) (TDD)

- [x] 9.1 SAFETY NET: baseline verde de `test_c16_review_decision_*` antes de tocar el enum/servicio
- [x] 9.2 RED: test del modelo de dos fases — fase revisión emite `sin_hallazgos|aprobado|caso_abierto`; resolución solo válida si `caso_abierto`
- [x] 9.3 GREEN: evolucionar `DecisionTerminal` (`domain/review/decision.py:9`) al modelo unificado + estado de caso; **dropear `escalada`**; mapear valores viejos (`descartada→sin_hallazgos`, `derivada→caso_abierto`, `escalada→caso_abierto`)
- [x] 9.4 TRIANGULATE: `caso_abierto` NO valida ni anula la nota; `sin_hallazgos`/`aprobado` validan; resolver un caso no-abierto → 409 (409 case cubierto en 10.4, service-level 9.4 ya cubre valida_la_nota)
- [x] 9.5 Migración Alembic (dos pasos): **estado de resolución sobre `proctoring_session`** (`anulado_por_fraude`/`caso_descartado`, junto a `decision` de 0013) + mapeo del enum viejo. SIN tabla nueva de actos (reversibilidad usa `audit_log` existente); NO tocar `moodle_writeback_estado`

## 10. Acto de resolución `resolver_caso` con barandas (D9/D11) (TDD)

- [x] 10.1 RED: test del endpoint/servicio de resolución (`POST /review/session/{id}/resolve`) separado del `decide`; requiere capacidad `resolver_caso` (gate cubierto por `test_c71_require_capability_pure` + wiring `_require_resolver`; lógica por `test_c71_review_resolution_*`)
- [x] 10.2 GREEN: endpoint + servicio de resolución (`anulado_por_fraude`/`caso_descartado`), gateado por `require_capability("resolver_caso")` server-side
- [x] 10.3 RED/GREEN: motivo obligatorio no vacío en TODA decisión; `anulado_por_fraude` exige además evidencia adjunta (400 si falta)
- [x] 10.4 TRIANGULATE: sin capacidad → 403 y nota sin cambios; resolver caso no-abierto → 409; anulación válida → nota anulada + acto en audit inmutable distinguible del acto de revisar (DB real)

## 11. Inmutabilidad + reversibilidad por acto compensatorio append-only (D10b) (TDD)

- [x] 11.1 RED: test que el estado de la nota se deriva del último acto y que revertir NO muta el acto de anulación (append-only en el `audit_log` existente, `audit_log.py:20`)
- [x] 11.2 GREEN: acto compensatorio de reversión (`nota_restituida`) como nueva entrada append-only vía `SqlReviewAuditor.log_decision` (`review.py:80`) + derivación del estado desde el último acto (cero infra nueva)
- [x] 11.3 GREEN: proyección del veredicto de anulación en `MiNota` (`resultados_query.py:232`, `router.py:1460`) — el alumno lo ve por **pull** en `GET /mis-notas`; sin canal push. Hook para c-18
- [x] 11.4 TRIANGULATE: test explícito de que NO existe transición automática score/umbral → `anulado_por_fraude` (regla #5)

## 12. Informe de devolución al alumno, gated por `anulado_por_fraude` (D12) (TDD)

- [x] 12.1 RED: test HTTP — con resolución `anulado_por_fraude`, el alumno ve capturas (URL firmada 15 min) + análisis por señal + decisión + motivo de SU sesión; sesión ajena → 403/404
- [x] 12.2 GREEN: endpoint scoped al titular que devuelve la evidencia autoritativa server-side (nunca el buffer del cliente, regla #6), solo si la resolución es `anulado_por_fraude`
- [x] 12.3 TRIANGULATE (minimización): `caso_descartado`/`sin_hallazgos`/`aprobado`/sin flag → el alumno NO ve el volcado de evidencia (Ley 25.326)
- [x] 12.4 RED/GREEN: cada acceso del titular al informe se registra en audit log como derecho de acceso (Ley 25.326, RN-DSR-01) con actor + propósito

## 13. Gate del write-back a Moodle por estado de revisión (D15) (TDD)

- [x] 13.1 SAFETY NET: baseline verde de los tests de write-back (`test_c69_mis_notas`, moodle writeback) y **verificar el trigger/timing actual del envío**. HALLAZGO: el envío es en dos etapas y YA manual — al finalizar la nota se persiste `estado='pendiente'` (`finalizar_con_writeback.py`), NUNCA se auto-envía; el paso a `'enviado'` ocurre SOLO en el sync manual del admin (`router.py:1205` → `listar_estados_sincronizables` que toma 'pendiente'/'fallido' → `ejecutar_writeback`). Ese es el punto de intercepción del hold.
- [x] 13.2 RED: test — sesión flaggeada (`en_cola_revision`/`caso_abierto`) → write-back en hold, no llega a `'enviado'`; sesión sin flag → se envía
- [x] 13.3 GREEN: gatear el envío por estado de revisión, evaluado al puntuar (antes del envío); hold si flaggeada/`caso_abierto`/`anulado_por_fraude`, release si resuelta limpia (`sin_hallazgos`/`aprobado`/`caso_descartado`) — `writeback_en_hold()` + filtro en `listar_estados_sincronizables`
- [x] 13.4 TRIANGULATE: hold previo + resolución limpia → se libera y envía; `anulado_por_fraude` → nunca se envía; edge (ya `'enviado'` antes de anular) → corrección manual, sin des-escritura automática (regla #5 — `persistir_nota_pendiente` es idempotente sobre 'enviado', no des-escribe)

## 14. Frontend: cola mejorada + informe de devolución (D6/D9/D11/D12)

- [x] 14.1 `lib/types.ts`: modelo `DecisionRevisor` unificado (dos fases, **sin `escalada`**); labels derivados de los valores del back (cerrar el gap). `SesionRevision.decision` y `ReviewDecisionPanel` (legacy) también migrados al modelo nuevo.
- [x] 14.2 `ColaPanelDecision.tsx`: detalle organizado y legible (drill-down); motivo obligatorio en cada decisión (textarea, submit deshabilitado sin motivo); botón de anulación destacado y diferenciado (danger + ring), habilitado SOLO con capacidad `resolver_caso` (prop `puedeResolver` desde `tieneCapacidad`)
- [x] 14.3 Nueva pantalla React (PascalCase) `InformeDevolucionAlumno.tsx`, ruta `/alumno/informe/:sessionId`, alcanzable desde `MiNota`/`NotaCard` solo con `informe_disponible` (veredicto `anulado_por_fraude`); consume `api.informeDevolucion` (endpoint scoped)
- [x] 14.4 Verificar que la capacidad se refuerza server-side (el front oculta con `tieneCapacidad`, el back deniega con `require_capability`); typecheck verde (tsc --noEmit exit 0); 691 tests frontend verdes

## 15. Cierre (Slice 2)

- [x] 15.1 Suite backend afectada (review + capabilities + informe + write-back gate + migración) verde, sin mocks de DB: 60 tests c71/review/scoring verdes contra Postgres real; c69 review/writeback/sync 45 verdes (2 fallas pre-existentes conocidas en test_c69_mis_notas::aprobado, confirmadas por stash, ajenas a c71); auth 22 verdes. Frontend: 691 tests verdes + typecheck limpio.
- [x] 15.2 Confirmar fronteras: apelación formal queda para c-18 (solo hook acá — `revertir_anulacion` acto compensatorio append-only + veredicto reversible expuesto por pull en MiNota); Sesiones Grabadas = slice 3 (no tocado); `caso_disciplinario` NO cableada (solo aparece en comentarios de dsr/retention; slim no tiene la tabla)
