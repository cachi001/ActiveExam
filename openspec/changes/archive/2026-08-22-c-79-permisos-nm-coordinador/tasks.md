# Tasks — C-79 `permisos-nm-coordinador`

> Reconstruidas a partir del código ya implementado (commit `28b1ee8`). Todas se marcan
> cumplidas porque el trabajo está hecho y verificado por los tests que se listan.

## Bloque 1 — Modelo de datos N:M

- [x] 1.1 Modelo `comision_tutor` (`backend/app/infrastructure/persistence/models/comision_tutor.py`); Done: tabla con UNIQUE(comision_id, tutor_id) y FKs con ondelete
- [x] 1.2 Modelo `materia_coordinador` en el mismo módulo; Done: tabla con UNIQUE(materia_id, coordinador_id)
- [x] 1.3 Migración `0086_c79_comision_tutor_materia_coordinador.py`; Done: crea ambas tablas y migra los `docente_id` existentes a `comision_tutor`
- [x] 1.4 `comision.docente_id` se conserva sin uso; Done: NO se dropea en este change (ver Non-Goals)

## Bloque 2 — Autorización acotada por pertenencia

- [x] 2.1 `authorization.py` resuelve las comisiones y materias del principal contra las tablas N:M; Done: el TUTOR ve solo sus comisiones, el COORDINADOR solo sus materias
- [x] 2.2 El COORDINADOR deja de tener alcance global; Done: sin materias asignadas no ve nada
- [x] 2.3 `ver_estadisticas` sale de TUTOR en `capabilities.py`; Done: queda en COORDINADOR y ADMIN_SISTEMA, con el motivo escrito en el código
- [x] 2.4 Acotar el catálogo de exámenes (`catalog_router`, `taking_router`) por pertenencia; Done: el listado y el detalle filtran por comisión/materia del principal
- [x] 2.5 Acotar el registro de sesiones y el panel de proctoring; Done: `sessions/router.py` filtra por las comisiones permitidas
- [x] 2.6 Acotar las estadísticas (`stats/router.py`); Done: el resumen responde al alcance del rol
- [x] 2.7 Guarda contra `subject` no-UUID; Done: evita el 500 de asyncpg donde correspondía un 403

## Bloque 3 — UI de asignación

- [x] 3.1 `AsignarDocenteDialog.tsx` pasa a permitir varios tutores; Done: agrega y quita contra los endpoints N:M
- [x] 3.2 `AsignarCoordinadorDialog.tsx` nuevo; Done: asigna coordinadores a una materia
- [x] 3.3 `moodle.ts` expone `agregarTutorComision`, `quitarTutorComision`, `agregarCoordinadorMateria`, `quitarCoordinadorMateria`; Done: cuatro métodos contra la API
- [x] 3.4 `nav.ts` y `App.tsx` reflejan el alcance del rol; Done: el menú no ofrece destinos sin permiso

## Bloque 4 — Auditoría: entidad y actor reales

- [x] 4.1 `entidad_de_accion` en `application/audit/acciones.py`; Done: fallback del tipo de entidad a partir de la acción
- [x] 4.2 El actor de los pedidos DSR es el email o username real; Done: `dsr/router.py` deja de guardar `"{uuid}:dsr"`
- [x] 4.3 `verify_chain` resuelve la sesión dueña del evento; Done: "Ver detalle" linkea al detalle de proctoring
- [x] 4.4 Los routers que pasaban `entidad_id` sin `entidad` quedan cubiertos por el fallback; Done: `catalog_router`, `users`, `evidence`, `consent_perfil`, `biometrics`, `chat_pausa`

## Bloque 5 — Tests

- [x] 5.1 `test_c79_coordinador_materia.py`; Done: el coordinador sin materias no ve nada, con materias ve solo las suyas
- [x] 5.2 `test_c79_entidad_de_accion.py`; Done: puro, sin DB, cubre el fallback de entidad
- [x] 5.3 `test_pertenencia_lectura_panel_academico.py`; Done: lectura del panel acotada
- [x] 5.4 Actualizar los tests existentes al modelo N:M; Done: `test_c73_*`, `test_c74_*`, `test_c76_*`, `test_c20_stats_resumen`, `conftest`

## Deuda que deja abierta

- [ ] Dropear `comision.docente_id` cuando se confirme que ningún lector la usa → **T-04** del relevamiento
- [ ] Normalizar lo que Auditoría todavía muestra como `null` o hash crudo → **c-78** (`filtro-etiqueta-fiel`) y **T-18**
