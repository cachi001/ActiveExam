## Why

El enforcement temporal de la rendición existe **solo en la puerta de entrada**. `verificar_enforcement` corre al CREAR la sesión y valida ventana, intentos e inscripción; una vez que la sesión está abierta, ningún endpoint vuelve a mirar el reloj. Reproducido contra la API real (backend slim, examen seed con `tiempo_limite_min=40`):

| Prueba | Esperado | Real |
|---|---|---|
| `POST /sessions/{id}/respuestas` con el límite vencido hace 140 min | 409 | **201 Created** |
| `POST /sessions/{id}/respuestas` con el examen cerrado hace 1 día | 409 | **201 Created** |
| `PATCH /sessions/{id}/finalizar` con tiempo vencido y ventana cerrada | 409 | **200 OK — calcula y certifica la nota** |
| `POST /sessions` (sesión nueva) con el examen cerrado | 403 | 403 ✅ |

Un examen cronometrado cuyo cronómetro vive en el navegador del que rinde no es un examen cronometrado: viola la regla dura de dominio #6 (*cliente = sensor no confiable*). En paralelo, dos huecos perjudican al alumno: la sesión abandonada queda `finalizada_en = NULL` para siempre y **nunca se puntúa** (el alumno pierde todo lo que respondió), y el candado de configuración post-rendición es binario, por lo que **congela `cierre` e `intentos_permitidos`** — impidiendo actos benignos como extender la ventana ante una caída o dar un intento extra a quien se le colgó la máquina.

Además, la reapertura del examen (cerrar todo y volver) **no deja rastro**: el catálogo de actividad sospechosa tiene 8 tipos y ninguno la cubre, así que el revisor humano no la ve. Y el candado que ya está en código (commit `da78f0f`) **no tiene spec** — drift que este change salda.

## What Changes

- **Deadline efectivo server-side**: el vencimiento de una rendición pasa a ser `min(cierre_del_examen, creada_en + tiempo_limite_min)`, calculado con hora del servidor. El alumno que arranca 11:50 en una ventana que cierra 12:00 tiene 10 minutos, no 40.
- **`POST /sessions/{id}/respuestas` rechaza fuera de plazo** con `409 tiempo_agotado`. **BREAKING** para cualquier cliente que hoy asuma que siempre acepta.
- **`PATCH /sessions/{id}/finalizar` revalida el estado temporal**: finalizar tarde es idempotente y no re-abre la corrección; nunca certifica una nota fuera de plazo sin dejarlo asentado.
- **Margen de gracia invisible** (~60-90s, configurable): tolerancia server-side a latencia de red y desfasaje de reloj. **NO se expone al cliente y la UI sigue cortando en el límite nominal** — si el alumno la ve, la gracia se convierte en el nuevo límite.
- **Auto-finalización de sesiones abandonadas**: al vencer el deadline efectivo, la sesión se finaliza y **se puntúa con las respuestas ya guardadas**. El alumno se lleva lo que hizo en vez de perder todo.
- **Candado de configuración direccional** (reemplaza al binario): aflojar se puede, apretar no, y lo que toca la nota nunca.
- **Dos tipos de evento nuevos, emitidos SERVER-SIDE**: `recarga_pagina` (baja) y `reanudacion_tardia` (media). Se emiten en el momento del resume dentro de `crear_o_reanudar_sesion`, donde el servidor sabe con certeza que reanudó. Al no depender del cliente, **un navegador modificado no los puede suprimir**.

### Modelo del candado direccional

| Grupo | Campos | Regla post-rendición |
|---|---|---|
| **Congelado duro** | `nota_maxima`, `nota_aprobacion`, `tiempo_limite_min`, `mezclar_preguntas`, `apertura`, selección de preguntas | Cualquier cambio reescribe retroactivamente la nota o la equidad → 409 |
| **Direccional** | `cierre` (solo extender), `intentos_permitidos` (solo aumentar) | Aflojar ayuda al alumno; apretar lo perjudica → 409 solo al apretar |
| **Libre** | `mostrar_nota`, `revision_habilitada` | Publicar es un acto legítimo posterior a la rendición |

## Capabilities

### New Capabilities
- `exam-deadline-enforcement`: deadline efectivo `min(cierre, creada_en + tiempo_limite_min)` calculado server-side con hora del servidor, margen de gracia invisible, y rechazo `409 tiempo_agotado` en todo endpoint que mute la rendición.
- `session-auto-finalization`: finalización automática de sesiones vencidas o abandonadas, con puntuación de las respuestas ya guardadas y writeback normal.
- `exam-config-directional-freeze`: candado direccional de la configuración post-rendición (congelado duro / direccional / libre), retrofitea el candado binario ya existente en código sin spec.

### Modified Capabilities
- `exam-taking-api`: el endpoint de respuestas SHALL rechazar con 409 fuera del deadline efectivo (hoy solo valida IDOR y sesión finalizada).
- `session-finalization`: la finalización SHALL revalidar el estado temporal y SHALL NOT certificar una nota fuera de plazo sin registro.
- `suspicious-activity-catalog`: dos tipos nuevos (`recarga_pagina` baja, `reanudacion_tardia` media) con su severidad y etiqueta de UI.
- `proctoring-session-lifecycle`: la reanudación de una sesión activa SHALL emitir el evento correspondiente server-side, con la duración de ausencia medida.

## Impact

**Backend**
- `app/application/proctoring/enforcement.py` — deadline efectivo, gracia, reutilizable desde todos los endpoints (hoy solo lo usa la creación).
- `app/presentation/api/v1/proctoring/sessions/router.py` — `submit_respuestas` (~:349) y `finalizar` pasan a validar plazo.
- `app/application/proctoring/session_service.py` — `crear_o_reanudar_sesion` (~:46) emite el evento de reanudación al resumir.
- `app/domain/exam_content/config.py` — `CAMPOS_CONGELADOS_POST_RENDICION` (binario) → modelo direccional.
- `app/presentation/api/v1/exam_content/router.py` — `PATCH /config` aplica la regla direccional.
- Auto-finalización: componente nuevo (barrido y/o lazy al acceso) + puntuación con lo guardado.
- Migración: sembrar los 2 tipos nuevos en `evento_score_config` con peso conservador.

**Frontend**
- Manejo de `409 tiempo_agotado` al guardar respuestas (mensaje claro, sin pérdida silenciosa).
- Timer sigue mostrando el límite nominal — la gracia NO se expone.
- Etiquetas y descripciones de UI de los 2 tipos de evento nuevos.

**Riesgo principal**: peso mal calibrado de `recarga_pagina` inunda la cola de revisión con víctimas de mala conectividad (corte de luz, wifi, crash), castigando al alumno con peor infraestructura y saturando a los revisores humanos — el recurso más escaso del proyecto (C-02, SU-03). Mitigación: severidad baja por defecto, peso ajustable desde `evento_score_config` sin tocar código, y la duración de ausencia como señal real en vez de la recarga en sí.

**No cambia**: la decisión disciplinaria sigue siendo humana (L2.5, regla dura #5). El deadline es una regla académica ("lapiceras abajo"), no una sanción por sospecha — por eso se enforcea duro, a diferencia de los eventos del catálogo, que solo priorizan.

---

# Ampliación (scope decidido por el owner)

## Why (ampliación)

Cuatro líneas de trabajo se suman a C-72 por decisión del owner, todas del mismo dominio (integridad y revisión de la rendición). Van con **tasks explícitas** (§9–§12): la lección de C-71 slice 3 fue que el scope bundleado sin tasks propias se pierde.

## What Changes (ampliación)

- **Registro de sesión (ex "Sesiones Grabadas")**: se renombra el concepto — **NO es video** (RN-CC-01/RN-CO-03 prohíben video continuo), es el **expediente revisable** de una sesión (screenshots + chat + anotaciones + eventos). El expediente **ya está casi construido** (`ProctoringSessionDetail.tsx`, `SessionDetail.tsx`, ruta `/admin/proctoring-sessions`); esta línea es **auditoría y tie-off** + darle spec, no feature nueva.
- **Limpiar el ruido del conteo de rostros**: ningún evento se oculta (los 9 tipos son anomalías donde el evento ES la evidencia — copiar/pegar, pestaña, foco…). Lo que se limpia es el bloque "Navegador: N / Servidor: N" de cada tarjeta: se muestra SOLO con discrepancia (cliente ≠ servidor) Y captura asociada; si coinciden o no hay imagen para inspeccionar, se oculta.
- **StatCards — consistencia + layout**: se normalizan las descripciones (hoy cambian demasiado entre pantallas) y se reorganiza. UX, sin cambio de contrato de datos.
- **Timeout del pedido de pausa**: una pausa `'solicitada'` sin responder expira por antigüedad (umbral configurable) y se cancela al finalizar la sesión, para que no ensucie el panel de supervisión en vivo. Distinto de `pausa_max_min` (duración de una pausa ya aprobada).

## Capabilities (ampliación)

### New Capabilities
- `session-record-dossier`: el expediente revisable de una sesión de proctoring (evidencia discreta: screenshots, chat, anotaciones, eventos), completo y coherente por tipo de sesión (examen vs test), **sin video**. Todos los eventos se listan (el evento es la evidencia); el bloque de conteo de rostros cliente/servidor se muestra solo con discrepancia y captura.
- `pause-request-timeout`: una solicitud de pausa sin resolver expira por antigüedad y se cancela al finalizar la sesión, saliendo de la cola de pendientes del proctor.

### Modified Capabilities
- `suspicious-activity-catalog`: (ya en el scope base) — sin cambios por la ampliación.

## Impact (ampliación)

**Frontend**
- `frontend/src/screens/proctoring/EventoCard.tsx` — el bloque de conteo cliente/servidor (`:119-124`) se muestra solo con discrepancia (`discrepanciaFC` `:46`) Y captura; ningún evento se oculta.
- `frontend/src/screens/SessionDetail.tsx` y `ProctoringSessionDetail.tsx` — verificación/tie-off del expediente (examen vs test); todos los eventos se siguen listando.
- `frontend/src/screens/proctoring/StatCard.tsx` y sus usos — normalizar descripciones + layout.

**Backend**
- `app/application/proctoring/chat_pausa_service.py` — expirar pausas `'solicitada'` viejas (timeout) + cancelar pendientes al finalizar la sesión.
- `app/presentation/api/v1/proctoring/chat_pausa/router.py` — `listar_pausas_pendientes` excluye las expiradas (naturalmente, al no ser ya `'solicitada'`).
- Constante de timeout del pedido configurable por env (default conservador), en la línea de la gracia (§1.8).

**Gobernanza**: la expiración de una pausa es acto del sistema que **no sanciona ni exime** (L2.5, regla #5) — solo limpia. El expediente NO incorpora video (RN-CC-01/RN-CO-03). El filtro de eventos es de vista: el dato crudo y su cadena de custodia se conservan íntegros (regla #6).
