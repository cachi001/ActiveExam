# Tasks — C-13 `scoring-incremental`

> Implementa el score incremental, el cierre asíncrono y la decisión de encolado por umbral. **Principio inviolable**: el score prioriza, NUNCA sanciona (RN-SC-01, DD-01). El Done de cada tarea es un test verde.

## 1. Score incremental vía continuous aggregate (capability `incremental-risk-score`)

- [x] 1.1 Definir el **continuous aggregate** de score por sesión sobre la hypertable `Evento` (refresh al minuto); Done: `cagg_score_ponderado_min` (migración 0004) con policy de refresh al minuto; test de creación/refresh @requires_stack (test_scoring_stack)
- [x] 1.2 Implementar la función de ponderación `peso = f(severidad, frecuencia, persistencia)` (RN-SC-02); Done: `peso_evento`/`score_incremental` (dominio puro), test de ponderación por severidad
- [x] 1.3 Modelar la **persistencia**: patrón sostenido pesa más que pico aislado (RN-SC-03); Done: `peso_evento` con bono por persistencia, test sostenido > pico aislado
- [x] 1.4 Modelar la **correlación**: eventos coincidentes en ventana temporal pesan más que la suma (RN-SC-03); Done: `score_correlacionado` (bono por par de tipos distintos en ventana), test correlación > Σ partes + tests de fuera-de-ventana y mismo-tipo
- [x] 1.5 Exponer la lectura del score desde el agregado materializado (CQRS-lite, no recorrer la hypertable); Done: `cagg_score_ponderado_min` es la fuente CQRS-lite en vivo; lectura desde el agregado @requires_stack

## 2. Cierre de sesión asíncrono (capability `session-finalization`)

- [x] 2.1 Endpoint `POST /sessions/{id}/finish` que marca la sesión finalizada y dispara tarea asíncrona; Done: `finish_session` router + `SessionFinalizationService.finish` (encola, no calcula), test de cierre no bloqueante
- [x] 2.2 Tarea asíncrona: consolidar métricas y calcular el **score final**; Done: `consolidar` + worker `session_finalization.consumir_una`, test de consolidación (flaggea/archiva según score)
- [x] 2.3 **Liberar la clave de sesión** rotativa al cierre; Done: `consolidar` setea `clave_sesion=""` (la ingesta rechaza eventos post-cierre vía `SesionSinClaveError`), test de liberación de clave
- [x] 2.4 Hacer la consolidación **idempotente y recomputable** desde la hypertable; Done: `consolidar` recomputa desde `eventos.posteriores_a` (no acumula), test de reintento sin doble conteo
## 3. Decisión de encolado por umbral (capability `review-queueing-decision`)

- [x] 3.1 Umbral institucional **configurable por examen** (`SCORE_THRESHOLD_DEFAULT`, conservador por defecto, RN-SC-05); Done: `decidir_encolado(umbral=...)` lee `examen.umbral_score` con fallback `SCORE_THRESHOLD_DEFAULT=5.0`, test de umbral configurable
- [x] 3.2 Si `score_final > umbral` → sesión **flaggeada** a la cola de revisión; Done: `consolidar` transiciona a FLAGGEADA y encola `review.queue` (insumo C-16), test de encolado por sobre-umbral
- [x] 3.3 Si `score_final ≤ umbral` → sesión **archivada**; Done: `consolidar` transiciona a CERRADA (archivada), no encola, test de archivado por bajo-umbral

## 4. Garantía de no-veredicto (capability `review-queueing-decision`)

- [x] 4.1 Verificar que **ningún path** del score/encolado emite sanción ni decisión disciplinaria (RN-SC-01, RN-RV-07, RN-DSR-04); Done: `DecisionEncolado` solo {flaggeada, archivada}; tests `test_score_nunca_emite_veredicto_solo_prioridad` y `test_ningun_path_produce_veredicto_solo_estado`
- [x] 4.2 Exponer el score solo como **prioridad ordinal** (no como culpa/decisión); Done: `ResultadoScore`/`ResultadoCierre` solo exponen `score_final` (ordinal) + `decision` (estado), sin campos de veredicto/sanción; test de contrato de salida

## 5. Observabilidad y cierre

- [x] 5.1 Instrumentar la **distribución de score** como métrica de negocio (`14`) para monitoreo del backlog; Done: `ResultadoCierre` expone `score_final` por consolidación (contable/distribuible); el sink a Prometheus es @requires_stack (test_scoring_stack)
- [x] 5.2 Confirmar que la sesión flaggeada + el orden por score quedan consumibles por **C-16**; Done: `consolidar` deja la sesión FLAGGEADA con `score` y encola `review.queue` con `{session_id, score, prioridad}` (contrato documentado para C-16)
