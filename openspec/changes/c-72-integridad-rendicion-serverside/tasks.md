## 1. Deadline efectivo — dominio puro

- [ ] 1.1 Test puro: `deadline_efectivo(creada_en, tiempo_limite_min, cierre)` devuelve `creada_en + limite` cuando el límite vence antes que la ventana
- [ ] 1.2 Test puro: devuelve `cierre` cuando la ventana cierra antes que el límite individual (arranque tardío)
- [ ] 1.3 Test puro: devuelve `cierre` cuando `tiempo_limite_min is None`
- [ ] 1.4 Implementar `deadline_efectivo` puro en `app/domain/exam_content/` (sin DB, sin I/O)
- [ ] 1.5 Test puro: `vencido(deadline, ahora, gracia_seg)` — False antes del deadline, False dentro de la gracia, True pasada la gracia
- [ ] 1.6 Test puro: bordes exactos de `vencido` (justo en el deadline, justo en el fin de la gracia)
- [ ] 1.7 Implementar `vencido` puro con la gracia como parámetro explícito (nunca leída del cliente)
- [ ] 1.8 Constante de gracia configurable por env con default 60s; documentar que es tolerancia a latencia, NO tiempo de examen

## 2. Enforcement en el envío de respuestas (H-1 / H-2)

- [ ] 2.1 Test integración (DB real): `POST /sessions/{id}/respuestas` con límite vencido → `409 tiempo_agotado`, nada persistido
- [ ] 2.2 Test integración: `POST /respuestas` con la ventana del examen cerrada → `409 tiempo_agotado`, nada persistido
- [ ] 2.3 Test integración: `POST /respuestas` dentro del plazo → 201 y respuesta persistida (no romper el camino feliz)
- [ ] 2.4 Test integración: respuesta que llega dentro de la gracia → 201 y persistida
- [ ] 2.5 Test integración: lote fuera de plazo con varias respuestas → ninguna se persiste (rechazo atómico)
- [ ] 2.6 Test integración: el error distingue `tiempo_agotado` de `sesion_finalizada`
- [ ] 2.7 Implementar la validación de plazo en `submit_respuestas` (`sessions/router.py`), cargando config del examen + `creada_en`
- [ ] 2.8 Test integración: la hora declarada por el cliente no altera el rechazo (se usa hora del servidor)

## 3. Enforcement en la finalización

- [ ] 3.1 Test integración: finalizar dentro de plazo → 200, nota sobre las respuestas persistidas
- [ ] 3.2 Test integración: finalizar fuera de plazo → la nota se calcula solo sobre respuestas persistidas antes del vencimiento (llegar tarde no da ventaja)
- [ ] 3.3 Test integración: el cierre fuera de plazo queda asentado en el registro de la sesión
- [ ] 3.4 Implementar la revalidación temporal en `finalizar` (`sessions/router.py`) preservando la idempotencia actual
- [ ] 3.5 Test integración: finalizar dos veces sigue siendo idempotente tras el cambio

## 4. Auto-finalización lazy (H-3)

- [ ] 4.1 Test integración: alumno vuelve pasado el deadline → su sesión queda finalizada y no puede seguir respondiendo
- [ ] 4.2 Test integración: sesión auto-finalizada se puntúa con las respuestas persistidas (14 de 20 → nota sobre 14, NO cero)
- [ ] 4.3 Test integración: sesión auto-finalizada sin ninguna respuesta → cierre consistente, nota sobre cero respuestas
- [ ] 4.4 Test integración: el write-back de una auto-finalizada sigue el mismo camino (y el mismo gate de revisión) que la manual
- [ ] 4.5 Implementar el cierre lazy al tocar una sesión vencida (reanudar / responder / consultar)
- [ ] 4.6 Test integración: doble cierre lazy es idempotente — no muta `finalizada_en` ni duplica write-back
- [ ] 4.7 Test integración: carrera cierre lazy vs. finalización manual → un único cierre, una única nota

## 5. Evento de reanudación server-side (H-4)

- [ ] 5.1 Registrar `recarga_pagina` (baja) y `reanudacion_tardia` (media) como `TipoEvento` del dominio con descripción y etiqueta
- [ ] 5.2 Migración Alembic: sembrar ambos tipos en `evento_score_config` con peso CONSERVADOR y `activo=true`
- [ ] 5.3 Test puro: la clasificación por duración de ausencia elige `recarga_pagina` bajo el umbral y `reanudacion_tardia` por encima
- [ ] 5.4 Test integración: reanudar una sesión activa emite el evento server-side, sin que el cliente reporte nada
- [ ] 5.5 Test integración: crear una sesión nueva (sin activa previa) NO emite evento de reanudación
- [ ] 5.6 Test integración: el evento registra la duración de ausencia medida server-side
- [ ] 5.7 Implementar la emisión en la rama de resume de `crear_o_reanudar_sesion` (`session_service.py:46`)
- [ ] 5.8 Test integración: reanudar conserva `creada_en` y el deadline efectivo (no extiende ni pausa)
- [ ] 5.9 Test integración: reanudar dentro del plazo restaura las respuestas ya persistidas
- [ ] 5.10 Test: el peso sembrado por sí solo NO empuja una sesión sobre el umbral de encolado a revisión

## 6. Candado direccional de configuración (H-5)

- [ ] 6.1 Test puro: los campos del grupo congelado duro se rechazan siempre en examen ya rendido
- [ ] 6.2 Test puro: `cierre` posterior al vigente se permite; anterior se rechaza
- [ ] 6.3 Test puro: `intentos_permitidos` mayor al vigente se permite; menor se rechaza
- [ ] 6.4 Test puro: `mostrar_nota` y `revision_habilitada` se permiten siempre
- [ ] 6.5 Test puro: examen sin intentos finalizados admite cualquier cambio
- [ ] 6.6 Reemplazar `CAMPOS_CONGELADOS_POST_RENDICION` por el modelo de tres grupos en `app/domain/exam_content/config.py`
- [ ] 6.7 Test integración: `PATCH /config` extendiendo `cierre` en examen rendido → 200 y persistido
- [ ] 6.8 Test integración: `PATCH /config` acortando `cierre` en examen rendido → `409 config_congelada`
- [ ] 6.9 Test integración: PATCH mixto (congelado + libre) → 409 y el campo libre NO se persiste (atómico)
- [ ] 6.10 Implementar la regla direccional en `PATCH /config` (`exam_content/router.py`), comparando contra el valor vigente
- [ ] 6.11 `GET /config` expone qué campos están congelados y cuáles admiten solo ampliación
- [ ] 6.12 Test integración: examen sin rendiciones reporta que ningún campo está congelado

## 7. Frontend

- [ ] 7.1 Test: manejo de `409 tiempo_agotado` al guardar respuestas — mensaje claro, sin pérdida silenciosa
- [ ] 7.2 Test: `409 sesion_finalizada` muestra un mensaje distinto de `tiempo_agotado`
- [ ] 7.3 Implementar el manejo de ambos 409 en el flujo de rendición
- [ ] 7.4 Test: el timer muestra el límite nominal y la gracia NO se expone ni se deriva de la API
- [ ] 7.5 Etiquetas y descripciones de UI para `recarga_pagina` y `reanudacion_tardia`
- [ ] 7.6 Test: la duración de ausencia es visible en el contexto de revisión de la sesión
- [ ] 7.7 UI de config: deshabilitar los congelados y explicar que `cierre`/`intentos_permitidos` solo se pueden ampliar

## 8. Verificación y cierre

- [ ] 8.1 Reproducir el repro original: sesión envejecida 3h en examen de 40' → `POST /respuestas` ahora devuelve 409 (antes 201)
- [ ] 8.2 Reproducir: examen cerrado hace 1 día → `POST /respuestas` devuelve 409 (antes 201)
- [ ] 8.3 Reproducir: `PATCH /finalizar` fuera de plazo ya no certifica nota con respuestas tardías (antes 200)
- [ ] 8.4 Verificar que `POST /sessions` con examen cerrado sigue devolviendo 403 (no romper lo que ya andaba)
- [ ] 8.5 Correr los tests de integración POR ARCHIVO con DB fresca (no juntos — teardowns con `DROP TABLE CASCADE` dan falsos negativos)
- [ ] 8.6 Suite de frontend completa en verde
- [ ] 8.7 Medir cuántas sesiones activas vencidas existen antes de activar cualquier cierre masivo
- [ ] 8.8 `openspec validate` del change en verde
