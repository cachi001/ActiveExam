## 1. Deadline efectivo — dominio puro

- [x] 1.1 Test puro: `deadline_efectivo(creada_en, tiempo_limite_min, cierre)` devuelve `creada_en + limite` cuando el límite vence antes que la ventana
- [x] 1.2 Test puro: devuelve `cierre` cuando la ventana cierra antes que el límite individual (arranque tardío)
- [x] 1.3 Test puro: devuelve `cierre` cuando `tiempo_limite_min is None`
- [x] 1.4 Implementar `deadline_efectivo` puro en `app/domain/exam_content/` (sin DB, sin I/O)
- [x] 1.5 Test puro: `vencido(deadline, ahora, gracia_seg)` — False antes del deadline, False dentro de la gracia, True pasada la gracia
- [x] 1.6 Test puro: bordes exactos de `vencido` (justo en el deadline, justo en el fin de la gracia)
- [x] 1.7 Implementar `vencido` puro con la gracia como parámetro explícito (nunca leída del cliente)
- [x] 1.8 Constante de gracia configurable por env con default 60s; documentar que es tolerancia a latencia, NO tiempo de examen

## 2. Enforcement en el envío de respuestas (H-1 / H-2)

- [x] 2.1 Test integración (DB real): `POST /sessions/{id}/respuestas` con límite vencido → `409 tiempo_agotado`, nada persistido
- [x] 2.2 Test integración: `POST /respuestas` con la ventana del examen cerrada → `409 tiempo_agotado`, nada persistido
- [x] 2.3 Test integración: `POST /respuestas` dentro del plazo → 201 y respuesta persistida (no romper el camino feliz)
- [x] 2.4 Test integración: respuesta que llega dentro de la gracia → 201 y persistida
- [x] 2.5 Test integración: lote fuera de plazo con varias respuestas → ninguna se persiste (rechazo atómico)
- [x] 2.6 Test integración: el error distingue `tiempo_agotado` de `sesion_finalizada`
- [x] 2.7 Implementar la validación de plazo en `submit_respuestas` (`sessions/router.py`), cargando config del examen + `creada_en`
- [x] 2.8 Test integración: la hora declarada por el cliente no altera el rechazo (se usa hora del servidor)

## 3. Enforcement en la finalización

> Reencuadre (owner): al vencer el deadline la sesión se cierra sola (§4 auto-finalización). El alumno NO puede "finalizar tarde", así que finalizar manual NO se bloquea por vencimiento (es el cierre) y NO se marca "fuera de plazo" — se descartó ese marcador por no aportar (nota idéntica, mismo camino downstream). La nota siempre sale sobre respuestas en plazo (garantizado por §2). Esta sección es verificación de que finalizar ya se comporta bien + idempotencia.

- [x] 3.1 Test integración: finalizar en plazo → 200, nota sobre las respuestas persistidas
- [x] 3.2 Test integración: tras un intento de respuesta tardío (rechazado por §2), finalizar computa la nota solo sobre las respuestas en plazo (llegar tarde no da ventaja)
- [x] 3.3 Confirmar que finalizar NO se bloquea por vencimiento (es el cierre "lapiceras abajo"): sin chequeo de plazo nuevo en `finalizar`; el plazo lo cubren §2 (respuestas) y §4 (auto-cierre) — verificado, finalizar ya se comporta bien sin cambios
- [x] 3.4 Test integración: finalizar dos veces sigue siendo idempotente (la nota no se recalcula)

## 4. Auto-finalización lazy (H-3)

- [x] 4.1 Test integración: alumno vuelve pasado el deadline → su sesión queda finalizada y no puede seguir respondiendo
- [x] 4.2 Test integración: sesión auto-finalizada se puntúa con las respuestas persistidas (14 de 20 → nota sobre 14, NO cero)
- [x] 4.3 Test integración: sesión auto-finalizada sin ninguna respuesta → cierre consistente, nota sobre cero respuestas
- [x] 4.4 Test integración: el write-back de una auto-finalizada sigue el mismo camino (y el mismo gate de revisión) que la manual
- [x] 4.5 Implementar el cierre lazy al tocar una sesión vencida (reanudar / responder / consultar)
- [x] 4.6 Test integración: doble cierre lazy es idempotente — no muta `finalizada_en` ni duplica write-back
- [x] 4.7 Test integración: carrera cierre lazy vs. finalización manual → un único cierre, una única nota

## 5. Evento de reanudación server-side (H-4)

- [x] 5.1 Registrar `recarga_pagina` (baja) y `reanudacion_tardia` (media) como `TipoEvento` del dominio con descripción y etiqueta
- [x] 5.2 Migración Alembic: sembrar ambos tipos en `evento_score_config` con peso CONSERVADOR y `activo=true`
- [x] 5.3 Test puro: la clasificación por duración de ausencia elige `recarga_pagina` bajo el umbral y `reanudacion_tardia` por encima
- [x] 5.4 Test integración: reanudar una sesión activa emite el evento server-side, sin que el cliente reporte nada
- [x] 5.5 Test integración: crear una sesión nueva (sin activa previa) NO emite evento de reanudación
- [x] 5.6 Test integración: el evento registra la duración de ausencia medida server-side
- [x] 5.7 Implementar la emisión en la rama de resume de `crear_o_reanudar_sesion` (`session_service.py:46`)
- [x] 5.8 Test integración: reanudar conserva `creada_en` y el deadline efectivo (no extiende ni pausa)
- [x] 5.9 Test integración: reanudar dentro del plazo restaura las respuestas ya persistidas
- [x] 5.10 Test: el peso sembrado por sí solo NO empuja una sesión sobre el umbral de encolado a revisión

## 6. Candado direccional de configuración (H-5)

- [x] 6.1 Test puro: los campos del grupo congelado duro se rechazan siempre en examen ya rendido
- [x] 6.2 Test puro: `cierre` posterior al vigente se permite; anterior se rechaza
- [x] 6.3 Test puro: `intentos_permitidos` mayor al vigente se permite; menor se rechaza
- [x] 6.4 Test puro: `mostrar_nota` y `revision_habilitada` se permiten siempre
- [x] 6.5 Test puro: examen sin intentos finalizados admite cualquier cambio
- [x] 6.6 Reemplazar `CAMPOS_CONGELADOS_POST_RENDICION` por el modelo de tres grupos en `app/domain/exam_content/config.py` (modelo nuevo en uso; binario queda como shim deprecado hasta el rewire del router §6.10)
- [x] 6.7 Test integración: `PATCH /config` extendiendo `cierre` en examen rendido → 200 y persistido
- [x] 6.8 Test integración: `PATCH /config` acortando `cierre` en examen rendido → `409 config_congelada`
- [x] 6.9 Test integración: PATCH mixto (congelado + libre) → 409 y el campo libre NO se persiste (atómico)
- [x] 6.10 Implementar la regla direccional en `PATCH /config` (`exam_content/router.py`), comparando contra el valor vigente
- [x] 6.11 `GET /config` expone qué campos están congelados y cuáles admiten solo ampliación
- [x] 6.12 Test integración: examen sin rendiciones reporta que ningún campo está congelado

## 7. Frontend

- [x] 7.1 Test: manejo de `409 tiempo_agotado` al guardar respuestas — mensaje claro, sin pérdida silenciosa
- [x] 7.2 Test: `409 sesion_finalizada` muestra un mensaje distinto de `tiempo_agotado`
- [x] 7.3 Implementar el manejo de ambos 409 en el flujo de rendición
- [x] 7.4 Test: el timer muestra el límite nominal y la gracia NO se expone ni se deriva de la API
- [x] 7.5 Etiquetas y descripciones de UI para `recarga_pagina` y `reanudacion_tardia`
- [x] 7.6 La duración de ausencia (`payload.ausencia_seg`) es visible y legible en la revisión: label "Duración de ausencia" + formateo de segundos (75 s → "1 min 15 s"); `origen` interno oculto. Test `EventoCard.ausencia.test.tsx` (3). Fix real: `ausencia_seg` renderizaba sin unidad ni etiqueta
- [x] 7.7 Config direccional en la UI: congelado-duro (tiempo/apertura/notas/mezclar) sigue `disabled`; `cierre` (solo extender, `min`=vigente) e `intentos_permitidos` (solo aumentar, `min`=vigente) quedan EDITABLES con hint; banner reescrito; `formToPatch` envía los ampliables solo si cambiaron (evita falso 409 por truncamiento). Test actualizado (5)

## 8. Verificación y cierre

- [x] 8.1 Reproducir el repro original: sesión envejecida 3h en examen de 40' → `POST /respuestas` ahora devuelve 409 (antes 201)
- [x] 8.2 Reproducir: examen cerrado hace 1 día → `POST /respuestas` devuelve 409 (antes 201)
- [x] 8.3 Reproducir: `PATCH /finalizar` fuera de plazo ya no certifica nota con respuestas tardías (antes 200)
- [x] 8.4 Verificar que `POST /sessions` con examen cerrado sigue devolviendo 403 (no romper lo que ya andaba)
- [x] 8.5 Correr los tests de integración POR ARCHIVO con DB fresca (no juntos — teardowns con `DROP TABLE CASCADE` dan falsos negativos)
- [x] 8.6 Suite de frontend completa en verde (67+ archivos)
- [x] 8.7 Gate operativo documentado: query de medición de sesiones activas vencidas antes de un cierre masivo (`ops-cierre-masivo.md`). No aplica a la DB dev slim (tablas de sesión efímeras); es gate de producción
- [x] 8.8 `openspec validate` del change en verde

---

# Ampliación (scope del owner) — tasks explícitas

## 9. Bloque de conteo de rostros: mostrar solo con discrepancia Y captura

> Contexto: los 9 `TipoEvento` son anomalías (el evento ES la evidencia) → **NO se oculta ningún evento**. El ruido real es el bloque "Navegador: N / Servidor: N" (`EventoCard.tsx:119-124`), que hoy se muestra aunque cliente y servidor coincidan y aunque no haya captura. Regla: mostrarlo SOLO con discrepancia (`cliente ≠ servidor`) **Y** captura asociada.

- [x] 9.1 Test: el bloque de conteo cliente/servidor NO se muestra cuando `fcCliente === fcServidor` (coinciden)
- [x] 9.2 Test: el bloque NO se muestra cuando hay discrepancia pero NO hay captura asociada (nada que inspeccionar)
- [x] 9.3 Test: el bloque SÍ se muestra cuando hay discrepancia (`fcCliente !== fcServidor`) Y hay captura
- [x] 9.4 Test: TODOS los eventos se siguen listando — ningún evento se oculta por el conteo (`copiar_pegar`, `cambio_pestana`, `perdida_de_foco`, etc. siempre visibles: el evento es la evidencia)
- [x] 9.5 Implementar la condición en `EventoCard.tsx` (combinar `discrepanciaFC` `:46` con el indicador de captura) — reemplaza `hayFaceCount` como condición de render del bloque de conteo
- [x] 9.6 Verificar el comportamiento en ambos expedientes (`SessionDetail.tsx`, `ProctoringSessionDetail.tsx`); la verificación del servidor (`veredicto_reinferencia`) se sigue mostrando aparte cuando flaggea (no se toca)
- [x] 9.7 Test: es cambio de VISTA — el dato crudo (`face_count_cliente`/`face_count_servidor`, evidencia) se conserva íntegro server-side

## 10. Registro de sesión (ex "Sesiones Grabadas") — tie-off + renombre

- [x] 10.1 Renombrado a "Registro de sesiones" en nav + BACK_LABELS + Proctor (commit bfed7c0); solo queda un comentario de código con el nombre viejo, no user-facing
- [x] 10.2 Test estructural: el expediente de EXAMEN (`ProctoringSessionDetail`) compone EventoCard (screenshots) + ChatBox (chat) + ObservacionesProctor (anotaciones) + BiometriaCard (`expediente.guardrail.test.ts`)
- [x] 10.3 Test estructural: el expediente de TEST/revisión (`SessionDetail`) compone StatCard + eventos; no exige chat/anotaciones (no aplican)
- [x] 10.4 Tie-off documentado: ambos detalles llevan doc explícita "NO HAY VIDEO (RN-CC-01/RN-CO-03)"; cubren examen (rico) y test/revisión (evidencia + cadena de custodia)
- [x] 10.5 Guardrail: ningún archivo del expediente referencia `MediaRecorder`/`captureStream`/`video_library` (`expediente.guardrail.test.ts`, 10 archivos escaneados)
- [x] 10.6 Suite de frontend en verde (67 archivos / 722 tests) tras el trabajo del expediente

## 11. StatCards — consistencia + layout

- [x] 11.1 Inventario hecho: divergían Eventos (label "Eventos totales"/"Eventos"/"Incidencias", icon+tono), Discrepancias (sub+tono en DetalleHeader), Sesiones (icon `video_library`, tono, sub)
- [x] 11.2 Test: `statCatalog.test.ts` (5 tests) — mismo key → mismo label/icon/tono; override de sub no altera el vocabulario canónico
- [x] 11.3 Vocabulario normalizado: fuente única `statCatalog.ts` (`statProps(key,value,subOverride?)`) cableada en ResumenVivo, ResumenSesiones, DetalleHeader, ExamenPersonasGrid, SessionDetail, AdminDashboard
- [x] 11.4 Layout consistente: mismas métricas → mismo icon/tono en todas las filas; tono `success` para Sesiones evita choque con Exámenes/Sesiones activas (primary)
- [x] 11.5 Typecheck verde + suite frontend verde (722 tests) tras el refactor

## 12. Timeout del pedido de pausa

- [x] 12.1 Test integración (DB real): una pausa `'solicitada'` más vieja que el umbral pasa a `'expirada'` y sale de `listar_pausas_pendientes`
- [x] 12.2 Test integración: una pausa `'solicitada'` dentro del umbral sigue pendiente (no expira antes de tiempo)
- [x] 12.3 Test integración: al finalizar (manual) una sesión con una pausa `'solicitada'`, esa pausa queda `'expirada'`
- [x] 12.4 Test integración: al auto-finalizar (§4) una sesión con pausa `'solicitada'`, esa pausa queda `'expirada'`
- [x] 12.5 Test: la expiración NO aprueba ni rechaza (no abre ventana, no setea `inicio_en`); es acto del sistema (L2.5)
- [x] 12.6 Constante de timeout del pedido configurable por env (default conservador); documentar que es distinto de `pausa_max_min`
- [x] 12.7 Implementar la expiración por antigüedad en `chat_pausa_service.py` (lazy al listar pendientes y/o al tocar la sesión)
- [x] 12.8 Implementar la cancelación de pendientes en el camino de finalización de sesión (manual y auto)
- [x] 12.9 Test integración: doble expiración es idempotente (no re-muta una pausa ya `'expirada'`)
- [x] 12.10 Frontend: el panel en vivo no muestra pausas expiradas (backend las excluye de `/pausas/pendientes`); historial renderiza `'expirada'` con etiqueta propia sin crashear (`PausasHistorial.test.tsx`, 3 tests). Bug arreglado: `ESTADO['expirada']` era `undefined` → crash del historial

## 13. Cierre de la ampliación

- [x] 13.1 `openspec validate c-72-integridad-rendicion-serverside` = valid
- [x] 13.2 Backend C-72 verde con DB real (candado/deadline/reanudación/pausa-timeout/finalización 42, catálogo CRUD 39, enforcement) + frontend 742 verde, sin mocks de DB. Además: arreglados 7 fallos que eran PRE-EXISTENTES de C-69/C-70 (`test_c69_repo_materia_comision.py`/`test_c69_integridad_materia_comision.py`) — los helpers construían Comisión sin `codigo_matriculacion` (NOT NULL desde 0038); ahora lo resuelven con el generador real (`componer_codigo`, único/determinístico)
- [x] 13.3 Fronteras confirmadas: expediente = evidencia discreta revisable, NO video (guardrail test); el filtro de eventos de la sección 9 es de VISTA (oculta el bloque de conteo sin discrepancia), no borra eventos

## 14. Migración: columna `materia.activa`

- [x] 14.1 Migración Alembic aditiva `0041`: `ADD COLUMN activa BOOLEAN NOT NULL DEFAULT true` en `materia` (reversible con `DROP COLUMN`)
- [x] 14.2 `activa` en `MateriaModel` (ORM, server_default "true") + entidad `Materia` (default `True`) + plumbing en el repo (todas las lecturas traen `activa`)
- [x] 14.3 Verificado contra Postgres real: materia seed `activa=t`; roundtrip downgrade 0040 ↔ upgrade 0041 OK

## 15. Materias/Comisiones — editar código (unicidad)

- [x] 15.1 Test (RED): `actualizar_materia` con código nuevo libre → persiste; con código en uso → `MateriaDuplicadaError` (front `examContentAdmin.test.ts` verde; back `test_c69` actualizado — corre con DB)
- [x] 15.2 Extender `MateriaComisionService.actualizar_materia` para aceptar y normalizar `codigo`, mapeando la violación de unicidad (23505) a `MateriaDuplicadaError`
- [x] 15.3 Endpoint `PATCH /materias/{id}` acepta `codigo` + `nombre`; 409 en duplicado (schema Pydantic `extra='forbid'`)
- [x] 15.4 Frontend `MateriaFormPanel`: mostrar el campo Código también en modo editar, con manejo del 409

## 16. Materias/Comisiones — eliminar solo si 100% vacío

- [x] 16.1 Test: borrar materia/comisión vacía → OK; con inscriptos/exámenes → 409 (front `examContentAdmin.test.ts` verde; back `test_c69` +8 tests de integración con fixture extendida — corre con DB)
- [x] 16.2 Repo: `contar_inscriptos_y_examenes` bajo una materia (join comisiones) y bajo una comisión + `eliminar`
- [x] 16.3 `MateriaComisionService.eliminar_materia`/`eliminar_comision` con el guard; cascade de comisiones vacías vía FK (smoke test 6/6 casos)
- [x] 16.4 Endpoints `DELETE /materias/{id}` y `DELETE /comisiones/{id}` → 204 borra, 409 con motivo si bloquea, 404 si no existe
- [x] 16.5 Frontend: menú Eliminar (materia + comisión) con `ConfirmModal` (sin `window.confirm`), toast del 409 que sugiere desactivar

## 17. Materias — activar/desactivar + enforcement del freeze

- [x] 17.1 Test: toggle `activa` (200/404/extra_forbid) + rendir examen de materia inactiva → 409 `materia_inactiva` (test_c69, 4 tests, verde con DB)
- [x] 17.2 `MateriaComisionService.set_activa` + repo `set_activa` + endpoint `PATCH /materias/{id}/activa` (MateriaResponse ahora trae `activa`)
- [x] 17.3 Enforcement en `inscripcion_service.inscribir_por_codigo`: rechaza si materia `activa=false` → `MateriaInactivaError` (409 `materia_inactiva`)
- [x] 17.4 Enforcement en `taking_service.obtener_para_rendir`: resuelve examen→comisión→materia y bloquea si inactiva (409); los ya inscriptos conservan acceso
- [x] 17.5 Frontend: ítem Activar/Desactivar en el menú + badge "Inactiva"; NO oculta al inscripto. E2E: desactivar → badge visible + PATCH 200

## 18. Config de resultados — lock tras la primera entrega

- [x] 18.1 Test: candado DIRECCIONAL de publicación (habilitar revisión / mostrar antes = OK; quitar revisión / ocultar nota = 409) — test_c72_candado 11/11
- [x] 18.2 DECISIÓN owner: NO lock duro sino DIRECCIONAL (coherente con C-72 §6). `mostrar_nota`/`revision_habilitada` movidos de CAMPOS_LIBRES a CAMPOS_DIRECCIONALES en config.py; `cambios_bloqueados` bloquea solo la dirección que perjudica a quien ya rindió
- [x] 18.3 Frontend: el 409 `config_congelada` ya se muestra; banner actualizado ("la publicación solo se puede aflojar")

## 19. Detalle de examen — stat cards + página de resultados

- [x] 19.1 Stat cards unificadas: componente `StatCard` reusado; mismo tamaño y tono; quitado el fondo `primary-fixed` especial de "Preguntas" (E2E verificado)
- [x] 19.2 Página dedicada `ExamResultados.tsx` en `/admin/examenes/:id/resultados`: toolbar, filtros, paginación, sync Moodle, estado vacío (E2E: carga OK)
- [x] 19.3 Detalle: tabla reemplazada por card + botón "Ver alumnos que rindieron →"; "Volver al detalle" desde la página (E2E: round-trip OK)
- [~] 19.4 Tabla relocalizada a su página; jerarquía base OK. NOTA: rediseño visual más profundo (densidad/estados) pendiente — conviene iterarlo con datos reales (hoy 0 resultados seedeados)

## 20. Verificación (gestión de catálogo)

- [x] 20.1 `tsc --noEmit` del frontend sin errores
- [x] 20.2 Servicios tocados por C-72 en verde con DB real: catálogo CRUD 39, enforcement materia inactiva, inscripciones, repo+integridad materia/comisión (12, ya sin los 7 fallos pre-existentes)
- [x] 20.3 E2E verificado incrementalmente en la sesión de apply (ver anotaciones 15.1/16.x/17.5/18/19): editar código, borrar materia vacía + bloqueo con contenido, desactivar → inscripción/rendición 409, candado direccional de config con entrega, página de resultados navegable
