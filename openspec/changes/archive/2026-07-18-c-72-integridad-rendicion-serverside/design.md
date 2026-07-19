## Context

El enforcement temporal vive solo en `verificar_enforcement` (`app/application/proctoring/enforcement.py:100`), invocado únicamente al crear la sesión. Los endpoints que mutan la rendición —`submit_respuestas` (`.../sessions/router.py:~349`) y `finalizar`— validan IDOR y `finalizada_en`, pero nunca el reloj. La causa raíz no son tres bugs independientes: es **un modelo mental** —"valido en la puerta y después confío"— que se manifiesta tres veces.

`crear_o_reanudar_sesion` (`app/application/proctoring/session_service.py:46`) ya resuelve bien la recarga: reanuda la sesión activa conservando `creada_en`, lo que impide que F5 reinicie el reloj. Ese ancla inmutable es la pieza sobre la que se apoya todo este diseño.

**Restricciones**:
- Regla dura de dominio #6: cliente = sensor no confiable. Ninguna decisión temporal puede originarse en el navegador.
- Regla dura de dominio #5 (L2.5): el sistema no sanciona automáticamente. **Pero el deadline no es una sanción por sospecha, es la regla académica del examen** ("lapiceras abajo"). Por eso se enforcea duro, a diferencia de los eventos del catálogo, que solo priorizan para revisión humana. Confundir ambas categorías es el error a evitar.
- Regla dura de código #4: tests sin mocks de DB (DB real o contenedor).
- Dominio CRÍTICO (integridad de examen, notas): sin verde comprobado no se asegura nada.

## Goals / Non-Goals

**Goals:**
- Un único cálculo de deadline efectivo, server-side, reutilizado por todos los endpoints que mutan la rendición.
- Que ningún alumno pierda trabajo por una falla de infraestructura que no controla.
- Que reabrir el examen deje rastro que un cliente modificado no pueda suprimir.
- Que el candado de configuración deje de bloquear actos benignos, y quede especificado (hoy está en código sin spec).

**Non-Goals:**
- Bloquear la recarga o el cambio de pestaña. **Es imposible en un navegador** (el sandbox le garantiza al usuario que siempre puede irse) y además contradice L2.5. Bloquear requiere una app nativa en modo kiosco (Safe Exam Browser / LockDown Browser) — otra categoría de producto, L3+, fuera del alcance de esta plataforma.
- Emitir veredicto disciplinario. El score prioriza; el humano decide.
- Cambiar el transporte o la cola (decisión de C-03, aún abierta).

## Decisions

### D1: El deadline efectivo es `min(cierre, creada_en + tiempo_limite_min)`

Los dos relojes del examen son distintos y hoy se tratan por separado: la **ventana** `[apertura, cierre]` dice *cuándo está disponible* el examen (igual para todos), y `tiempo_limite_min` dice *cuánto dura para cada alumno desde que arranca* (individual, anclado en `creada_en`). El vencimiento real de una rendición es el que ocurra primero.

Sin esto aparece un agujero silencioso: con ventana 10:00–12:00 y límite 40', quien arranca 11:50 tendría hasta 12:30 — media hora después de cerrado el examen.

**Alternativa descartada**: validar cada reloj por separado en cada endpoint. Duplica la lógica y reintroduce la asimetría que causó estos bugs.

### D2: Función pura para el deadline, llamada desde cada puerta

`deadline_efectivo(creada_en, tiempo_limite_min, cierre) -> datetime` y `vencido(deadline, ahora, gracia) -> bool` como funciones **puras** en el dominio, sin DB ni I/O. Los endpoints cargan config + sesión y consultan.

Puras porque el corte fino (gracia, límite nulo, ventana que gana al reloj individual, borde exacto) se testea exhaustivamente sin levantar nada — que es donde viven los errores de este tipo. La integración con DB real cubre el cableado.

**Alternativa descartada**: un middleware que gatee toda `/sessions/{id}/*`. Rechazado: no todos los endpoints deben gatearse igual (finalizar debe funcionar aun vencido — es justamente el cierre; el chat de pausa tiene otra semántica). Un gate transversal generaría falsos bloqueos.

### D3: La gracia es server-side e invisible

Constante configurable (~60–90s), aplicada solo en la comparación server-side. **No se expone en ninguna respuesta ni proyección.** La UI sigue cortando en el límite nominal.

Si el alumno la ve, la gracia se vuelve el límite real y el problema se corre 60 segundos a la derecha. Invisible, solo salva al que la necesita: el que apretó *Enviar* a tiempo y tiene mala conexión. No es tiempo de examen, es tolerancia a la latencia y al desfasaje de reloj. Es lo que hace Moodle.

**Alternativa descartada**: corte duro exacto. Penaliza al alumno con peor conectividad por una latencia que no controla — contradice el objetivo explícito de no perjudicar al alumno.

### D4: Auto-finalización lazy + barrido, puntuando lo respondido

Dos caminos hacia el mismo cierre idempotente:
- **Lazy**: al tocar una sesión vencida (reanudar, responder, consultar), se finaliza en el acto. Cubre al que vuelve tarde, sin infraestructura nueva.
- **Barrido**: proceso periódico que cierra las vencidas que nadie tocó. Cubre al que no vuelve nunca.

La nota se calcula sobre las respuestas ya persistidas. El alumno se lleva lo que hizo: hoy, un corte de luz en el minuto 38 lo deja sin nota **para siempre**.

La idempotencia es obligatoria porque ambos caminos pueden coincidir. Se apoya en el `finalizar_sesion` ya idempotente (`finalizada_en = now() if IS NULL`) y en la consolidación de score, ya idempotente y recomputable por spec de `session-finalization`.

**Alternativa descartada**: solo barrido. Deja una ventana en la que el alumno que vuelve tarde encuentra su sesión aún activa y puede seguir respondiendo — el agujero que estamos cerrando.

**Alternativa descartada**: nota 0. Convierte un corte de luz en un examen perdido.

**Pendiente de decisión (ver Open Questions)**: el mecanismo concreto del barrido depende de C-03, que aún no cerró la arquitectura de cola. El lazy no depende de C-03 y puede implementarse ya.

### D5: El evento de reanudación se emite SERVER-SIDE, en el resume

`crear_o_reanudar_sesion` ya sabe con certeza cuándo reanuda: es la rama que encuentra una sesión activa y la devuelve. Ese es el punto de emisión.

Decisivo: si el evento lo reportara el cliente, **el sensor que delata la conducta sería el mismo que la ejecuta.** Un alumno con DevTools no lo reporta y recarga cincuenta veces sin dejar rastro. Emitido por el servidor, no se puede suprimir, falsear ni desactivar. Es la regla dura #6 llevada hasta el final, y es gratis: la rama del código ya existe.

Desde el servidor, F5 y cerrar-y-reabrir son **indistinguibles** — ambos son un POST que reanuda. Esa indistinguibilidad no es un defecto: lo que importa no es *cómo* se fue, sino *cuánto tiempo* estuvo afuera.

### D6: La señal es la duración de la ausencia, no la reanudación

Dos tipos, discriminados por duración medida server-side (desde el último evento/actividad recibida): `recarga_pagina` (baja) para ausencias breves, `reanudacion_tardia` (media) para prolongadas.

La reanudación por sí sola **no es señal**: la produce un corte de luz, una batería agotada, un wifi caído, un crash del navegador, un Windows Update. Ponderarla alto flaggea al alumno con peor infraestructura — exactamente al que ya la tiene más difícil. Volver en 3 segundos es ruido; volver en 4 minutos es señal. Es el mismo evento; los separa la duración.

Peso sembrado **conservador** y ajustable desde `evento_score_config` sin tocar código. Los revisores humanos son el recurso más escaso del proyecto (C-02, SU-03: *"la dependencia más subestimada"*): inundar la cola con víctimas de mala conectividad hace que el revisor deje de mirar los casos que importan. **Un detector que grita siempre es un detector apagado.**

### D7: Candado direccional en tres grupos

`CAMPOS_CONGELADOS_POST_RENDICION` (frozenset binario) → modelo de tres grupos. El principio que los ordena:

> **Aflojar siempre se puede. Apretar, nunca. Y lo que toca la nota, jamás.**

| Grupo | Campos | Regla |
|---|---|---|
| Congelado duro | `nota_maxima`, `nota_aprobacion`, `tiempo_limite_min`, `mezclar_preguntas`, `apertura`, selección de preguntas | 409 ante cualquier cambio |
| Direccional | `cierre` (solo posterior), `intentos_permitidos` (solo mayor) | 409 solo al restringir |
| Libre | `mostrar_nota`, `revision_habilitada` | siempre editable |

El candado binario actual (commit `da78f0f`) bloquea `cierre` e `intentos_permitidos`, impidiendo extender la ventana ante una caída o dar un intento a quien se le colgó la máquina — perjudica al alumno, que es lo contrario de su objetivo. Direccional requiere comparar contra el valor vigente, no solo detectar presencia del campo en el PATCH.

El rechazo es **atómico**: un PATCH mixto (campo congelado + campo libre) se rechaza entero. Un rechazo parcial dejaría al administrador sin saber qué quedó aplicado.

## Risks / Trade-offs

- **[Peso mal calibrado de `recarga_pagina` inunda la cola de revisión]** → severidad baja por defecto, peso conservador sembrado, ajustable sin desplegar; la duración —no la recarga— es la señal. Observar la tasa real antes de subirlo.
- **[La gracia se filtra al cliente y se vuelve el límite real]** → test explícito de que ninguna respuesta de la API expone gracia ni deadline con gracia incluida.
- **[Sesiones legacy activas y vencidas al desplegar]** → el barrido las cierra puntuando lo respondido; conviene medir cuántas hay antes de activarlo, para no disparar un lote de write-backs inesperado.
- **[El corte por plazo hace perder trabajo si el frontend no lo maneja]** → el 409 debe distinguir `tiempo_agotado` de `sesion_finalizada` y el front debe explicarlo sin pérdida silenciosa.
- **[Falso sentido de seguridad]** → esto cierra el enforcement temporal, NO convierte la plataforma en L3. La recarga y el cambio de pestaña siguen siendo imposibles de bloquear por diseño del navegador. Se registran y los pondera un humano; ese es el modelo elegido.
- **[Tests de integración no aislados]** → varios archivos hacen `create_all`/`DROP TABLE CASCADE` en teardown contra DB compartida; correrlos juntos da falsos negativos. Verificar por archivo con DB fresca o vía `backend/scripts/run_tests_in_container.sh`.

## Migration Plan

1. Funciones puras de deadline + gracia (sin efecto observable).
2. Enforcement en `submit_respuestas` → `409 tiempo_agotado`. **BREAKING** para clientes que asumen aceptación incondicional.
3. Frontend maneja el 409 antes o junto con (2), para que ningún alumno vea una pérdida silenciosa.
4. Finalización revalida estado temporal y lo asienta.
5. Auto-finalización lazy.
6. Tipos de evento nuevos + migración de `evento_score_config` con peso conservador + emisión server-side en el resume.
7. Candado direccional (reemplaza el binario).
8. Barrido, cuando C-03 defina el mecanismo.

**Rollback**: los pasos 1–2 son reversibles revirtiendo el chequeo. El paso 6 agrega filas de catálogo — reversible con `activo=false` sin borrar datos históricos. El paso 7 puede volver al frozenset binario.

## Open Questions

- **Valor exacto de la gracia** (60 vs 90s): arrancar en 60s y medir. Requiere dato de latencia real de la población.
- **Umbral rápida/tardía** (~30s propuesto): calibrable, debería surgir de la distribución real de ausencias. Arrancar conservador.
- **Mecanismo del barrido**: depende de C-03 (Postgres-como-cola vs. RabbitMQ+Celery). El lazy no depende de C-03 — implementar lazy ahora, barrido después. **No asumir arquitectura de cola antes de C-03** (regla dura de dominio #4).
- **Umbral del timeout del pedido de pausa** (ver ampliación §D-A4): arrancar conservador (default configurable por env) y medir contra el tiempo real de respuesta del proctor.

## Decisiones cerradas (antes Open Questions)

- **La pausa autorizada NO extiende el deadline efectivo** (resuelto con el owner). El reloj sigue corriendo aunque el proctor apruebe una pausa. Consistente con la §5.8 (reanudar no extiende ni pausa) y con el objetivo de integridad del change: `deadline_efectivo = min(cierre, creada_en + tiempo_limite_min)` NO depende de ventanas de pausa. La justicia ante interrupciones legítimas ya la da el **scoring** (contextualiza/excluye los eventos en pausa autorizada), no el reloj. Alternativa descartada (congelar el reloj durante la pausa): abre el vector "pausa = nuevo botón de pausa" y complica el cálculo del deadline con ventanas que restar.

---

# Ampliación (scope decidido por el owner) — registro de sesión + UX + timeout de pausa

> Estas 4 líneas de trabajo se suman a C-72 por decisión del owner. Van con **tasks explícitas** (§9–§12): la lección de C-71 slice 3 fue que el scope sin tasks propias se pierde.

## D-A1 — "Registro de sesión" (ex "Sesiones Grabadas"): renombre + tie-off, NO feature nueva

**El nombre "Sesiones Grabadas" es peligroso**: sugiere video y alguien lo implementaría con `MediaRecorder`, violando RN-CC-01/RN-CO-03 (*"no se graba video continuo bajo ninguna circunstancia"*). Se renombra el concepto a **registro de sesión / expediente de sesión**: el conjunto revisable de evidencia discreta de una sesión de proctoring — screenshots, chat proctor↔alumno, anotaciones del proctor y eventos discretos. **NO es video.**

El expediente **ya está casi construido** y disperso entre c-15/c-16/c-69, sin que nadie lo cerrara: `ProctoringSessionDetail.tsx` (examen: `DetalleHeader` + `EventoCard` + `BiometriaCard` + `ChatBox` + `ObservacionesProctor` + `PausaSesionPanel`/`PausasHistorial`) y `SessionDetail.tsx` (test: StatCards + eventos + cadena de custodia), con la ruta `/admin/proctoring-sessions` ya etiquetada. Esta línea es **auditoría y tie-off**, no construcción: verificar que el expediente es completo y coherente por tipo de sesión (examen vs test) y darle spec al concepto que hoy no la tiene. **Alternativa descartada:** rehacer un expediente nuevo → duplica lo existente.

## D-A2 — Ruido del conteo de rostros (NO ocultar eventos)

**Corrección de criterio (dialogada con el owner).** El primer planteo —ocultar los eventos con `tiene_evidencia === false`— era **incorrecto**: los 9 `TipoEvento` son anomalías discretas (`copiar_pegar`, `cambio_pestana`, `perdida_de_foco`, `monitor_adicional`, `salida_pantalla_completa`, `corte_conectividad_prolongado`, `rostro_ausente`, `multiples_rostros`, `mirada_desviada_sostenida`) donde **el evento ES la evidencia**: un `copiar_pegar` no tiene screenshot y aun así es señal. Filtrar por captura ocultaría anomalías reales.

El ruido real es otro: `EventoCard.tsx:119-124` muestra en cada tarjeta un bloque **"Navegador: N rostros / Servidor: N rostros"** (reconciliación cliente↔servidor, regla dura #6). Ese bloque solo tiene señal cuando **cliente y servidor NO coinciden** (`discrepanciaFC`, `:46`) — es el caso "el cliente mintió". Y una discrepancia solo es **accionable si hay captura**: sin imagen el revisor no puede inspeccionar quién tiene razón. Regla: **mostrar el bloque de conteo SOLO cuando hay discrepancia Y captura**; si coinciden o no hay captura, ocultarlo. **Ningún evento se oculta.** Es cambio de vista; el conteo crudo se conserva. La verificación del servidor (`veredicto_reinferencia`, `:87`) se muestra aparte cuando flaggea — no se toca. **Alternativa descartada:** filtrar eventos por `tiene_evidencia` → ocultaría copiar/pegar, pestaña, foco, etc., que son la evidencia misma.

## D-A3 — StatCards: consistencia y layout

`StatCard.tsx` es un componente único reutilizado en dashboard, lista en vivo y detalle. El problema NO es el componente sino la **inconsistencia de las descripciones (`sub`) entre pantallas** y la organización. Se normaliza el vocabulario de las stats (mismas métricas → misma etiqueta/descripción) y se ordena el layout. UX, sin cambio de contrato de datos.

## D-A4 — Timeout del pedido de pausa

Hoy `solicitar_pausa` crea una pausa `estado='solicitada'` que vive para siempre hasta que el proctor la resuelva. `listar_pausas_pendientes` (poll del proctor) devuelve TODAS las `'solicitada'` de todas las sesiones. Problema del owner: si el alumno pide una pausa, el proctor no responde y el alumno finaliza el examen, **el pedido pendiente sobrevive y ensucia el panel de supervisión en vivo**. Dos reglas nuevas:

1. **Timeout**: una pausa `'solicitada'` cuya antigüedad supera un umbral (configurable por env, default conservador) SHALL transicionar a un estado terminal (`'expirada'`) y salir de la cola de pendientes. Es cancelación del PEDIDO sin responder — distinto de `pausa_max_min`, que limita la DURACIÓN de una pausa ya aprobada.
2. **Cancelación al finalizar**: al finalizar (manual o automática) una sesión con pausas `'solicitada'` pendientes, esas pausas SHALL cancelarse (`'expirada'`) — no tiene sentido una pausa pendiente sobre una sesión cerrada.

La transición a `'expirada'` es un acto del sistema, no una sanción (L2.5): no aprueba ni rechaza, solo limpia. **Alternativa descartada:** borrar la fila → pierde el rastro de que se pidió; se conserva como estado terminal.
