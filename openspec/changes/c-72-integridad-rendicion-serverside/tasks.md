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
- [ ] 7.6 Test: la duración de ausencia es visible en el contexto de revisión de la sesión
- [ ] 7.7 UI de config: deshabilitar los congelados y explicar que `cierre`/`intentos_permitidos` solo se pueden ampliar

## 8. Verificación y cierre

- [x] 8.1 Reproducir el repro original: sesión envejecida 3h en examen de 40' → `POST /respuestas` ahora devuelve 409 (antes 201)
- [x] 8.2 Reproducir: examen cerrado hace 1 día → `POST /respuestas` devuelve 409 (antes 201)
- [x] 8.3 Reproducir: `PATCH /finalizar` fuera de plazo ya no certifica nota con respuestas tardías (antes 200)
- [x] 8.4 Verificar que `POST /sessions` con examen cerrado sigue devolviendo 403 (no romper lo que ya andaba)
- [x] 8.5 Correr los tests de integración POR ARCHIVO con DB fresca (no juntos — teardowns con `DROP TABLE CASCADE` dan falsos negativos)
- [ ] 8.6 Suite de frontend completa en verde
- [ ] 8.7 Medir cuántas sesiones activas vencidas existen antes de activar cualquier cierre masivo
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

- [ ] 10.1 Renombrar el concepto en la UI: "Sesiones grabadas" → "Registro de sesión" / "Expediente" en labels y navegación (`/admin/proctoring-sessions` y BACK_LABELS)
- [ ] 10.2 Test: el expediente de una sesión de EXAMEN incluye screenshots + chat + anotaciones del proctor + eventos (con evidencia)
- [ ] 10.3 Test: el expediente de una sesión de TEST incluye screenshots + eventos + statcards (sin chat/anotaciones si no aplica)
- [ ] 10.4 Verificar (tie-off) que `ProctoringSessionDetail.tsx` y `SessionDetail.tsx` cubren ambos tipos de sesión de forma coherente; documentar en el detalle que NO hay video (RN-CC-01/RN-CO-03)
- [ ] 10.5 Test: ningún camino del expediente referencia grabación de video / `MediaRecorder` (guardrail contra la interpretación peligrosa del nombre viejo)
- [ ] 10.6 Suite de frontend del expediente en verde

## 11. StatCards — consistencia + layout

- [ ] 11.1 Inventariar los usos de `StatCard` (dashboard, lista en vivo, `SessionDetail`, detalle) y las descripciones (`sub`) que hoy varían para la misma métrica
- [ ] 11.2 Test: métricas equivalentes usan la misma etiqueta y descripción entre pantallas (fuente única de labels de stats)
- [ ] 11.3 Normalizar el vocabulario de las statcards (mismas métricas → mismo `label`/`sub`)
- [ ] 11.4 Reorganizar el layout de las statcards según lo pedido (consistencia visual entre pantallas)
- [ ] 11.5 Test/verificación visual: typecheck verde + suite de frontend verde tras el reordenamiento

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
- [ ] 12.10 Frontend: el panel de supervisión en vivo no muestra pausas expiradas; test de que desaparecen de la cola

## 13. Cierre de la ampliación

- [ ] 13.1 `openspec validate` del change en verde tras la ampliación
- [ ] 13.2 Suite backend (chat_pausa + finalización) y frontend (expediente + statcards) en verde, sin mocks de DB
- [ ] 13.3 Confirmar fronteras: registro de sesión = expediente revisable, NO video; el filtro de eventos es de vista, no borrado
