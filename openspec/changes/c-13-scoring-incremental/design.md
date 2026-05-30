# Design — C-13 `scoring-incremental`

> Design técnico de producción del **score de riesgo incremental** (Flujo 6). Continuous aggregates de TimescaleDB (CQRS-lite), consolidación asíncrona al cierre, decisión de encolado por umbral. **Principio rector**: el score PRIORIZA, nunca emite veredicto (RN-SC-01, DD-01).

## Context

El sistema Proctoring genera millones de eventos por examen (`14`). El revisor humano es el recurso escaso (5–15% de sesiones revisadas, RN-RV-01, SU-03). El score de riesgo existe para una única función: **ordenar la cola de revisión por prioridad**, poniendo primero lo más sospechoso ante un tiempo de revisión finito.

**Constraint inviolable (gobernanza)**: el nivel L2.5 (DD-01) prohíbe la sanción automática. RN-SC-01 lo fija: el score es "una **prioridad** para la cola de revisión, **no un veredicto**". RN-RV-07: "ninguna sanción es automática". RN-DSR-04: el derecho de oposición a decisiones automatizadas "se cumple por arquitectura, ya que ninguna sanción es automática". Este change debe **calcular y ordenar, jamás decidir**.

**Constraints técnicos** (de la KB):
- **RN-SC-02**: score incremental durante el examen, ponderando **severidad, frecuencia y persistencia**.
- **RN-SC-03**: patrón sostenido > pico aislado; **eventos correlacionados pesan más que la suma** de sus partes.
- **RN-SC-04**: al cierre, tarea asíncrona calcula el **score final**; si supera el umbral institucional → cola de revisión.
- **RN-SC-05**: calibración **conservadora** (minimizar falsos positivos; el humano recupera los verdaderos positivos); afinada con datos reales en Fase 2.
- **DD-05 / `04`**: TimescaleDB con **continuous aggregates** (eventos por sesión por minuto, score por sesión) — el patrón de escritura intensa se resuelve con agregados materializados.
- **`08` §Patrones**: **CQRS-lite** — las lecturas de score salen de agregados materializados, no de recorrer la hypertable.

**Decisión heredada (no se re-decide)**: el `Evento` (hypertable), sus severidades (RN-EV-04) y el enum de estado de `Sesión` (incluye `flaggeada`) vienen de C-05/C-10. Este change agrega los continuous aggregates de score y la lógica de cierre **sobre** esas estructuras.

**Stakeholders**: revisor (consume la cola priorizada vía C-16), coordinador (monitorea backlog), DPO/legal (garantía de no-veredicto), estudiante (NO recibe veredicto del score).

## Goals / Non-Goals

**Goals:**
- Calcular el score **incrementalmente** vía continuous aggregate de TimescaleDB (al minuto), ponderando severidad, frecuencia y persistencia.
- Modelar la **correlación**: eventos correlacionados pesan más que la suma de sus partes.
- Consolidar el **score final** en una tarea asíncrona al cierre y **liberar la clave de sesión**.
- Decidir el **encolado por umbral**: flaggeada → cola; si no → archivada.
- Garantizar por diseño que el score **prioriza, nunca sanciona**.

**Non-Goals:**
- NO emitir veredicto, sanción ni decisión disciplinaria (eso es **humano**, C-16).
- NO implementar la cola de revisión ni su orden de presentación al revisor (eso es **C-16**; este change deja la sesión flaggeada y el score como insumo).
- NO redefinir el esquema de `Evento` ni el enum de `Sesión` (vienen de C-05/C-10).
- NO afinar los umbrales con datos reales (eso es Fase 2, RN-SC-05); el MVP usa umbrales conservadores configurables.
- NO calcular reportes ni analytics (eso es C-20).

## Decisions

### D1 — Score incremental vía continuous aggregate de TimescaleDB (CQRS-lite)
**Decisión**: materializar el score por sesión como un **continuous aggregate** que se refresca al minuto sobre la hypertable de eventos; las lecturas del score salen del agregado, no de recorrer eventos crudos.
**Por qué**: DD-05 + `08` §Patrones (CQRS-lite) — recorrer millones de eventos por sesión en cada lectura no escala; el agregado materializado reduce la latencia en órdenes de magnitud y se actualiza incrementalmente.
**Alternativa considerada**: recálculo on-demand recorriendo la hypertable → costo prohibitivo bajo carga.

### D2 — Ponderación por severidad, frecuencia y persistencia
**Decisión**: el peso de cada evento combina su **severidad** (baseline/media/alta/crítica, RN-EV-04), su **frecuencia** (cuántos del mismo tipo) y su **persistencia** (cuánto se sostiene en el tiempo); un patrón sostenido pesa más que un pico aislado.
**Por qué**: RN-SC-02/RN-SC-03 — un único frame anómalo es ruido; un patrón sostenido es señal. La persistencia distingue ruido de comportamiento.
**Alternativa considerada**: suma simple de eventos por severidad → no distingue ruido instantáneo de patrón sostenido; genera falsos positivos.

### D3 — Correlación: eventos correlacionados pesan más que la suma
**Decisión**: cuando eventos de distinto tipo coinciden en una ventana temporal (p. ej. mirada desviada + pérdida de foco simultáneas), su contribución combinada es **mayor que la suma** de sus contribuciones individuales.
**Por qué**: RN-SC-03 — la coincidencia de señales independientes es más sospechosa que cada una por separado; la correlación es información, no redundancia.
**Alternativa considerada**: tratar cada evento de forma independiente → subestima patrones coordinados de fraude.

### D4 — El score PRIORIZA, NUNCA emite veredicto (gobernanza por diseño)
**Decisión**: el score solo produce un **número ordinal** y una **decisión de encolado** (flaggeada/archivada); **jamás** una sanción, culpa o decisión disciplinaria. La decisión terminal es exclusivamente humana (C-16).
**Por qué**: DD-01 (L2.5), RN-SC-01, RN-RV-07, RN-DSR-04 — es el corazón de la garantía legal del sistema; el derecho de oposición a decisiones automatizadas se cumple **por arquitectura**.
**Alternativa considerada**: que el score emita un veredicto automático sobre un umbral → viola el axioma del sistema y el contrato de C-01; **descartada categóricamente**.

### D5 — Consolidación asíncrona al cierre; liberación de la clave de sesión
**Decisión**: `POST /sessions/{id}/finish` dispara una **tarea asíncrona** que consolida métricas, calcula el **score final** y **libera la clave de sesión rotativa**; la decisión de encolado se toma sobre el score final.
**Por qué**: RN-SC-04 — el cierre no debe bloquear al estudiante esperando el cálculo; la consolidación corre en background. La clave de sesión se libera al cerrar (ya no se firman más eventos de esa sesión).
**Alternativa considerada**: cálculo síncrono al cierre → bloquea la respuesta al estudiante y no escala al pico de cierres simultáneos.

### D6 — Umbral institucional configurable, calibración conservadora
**Decisión**: el umbral de encolado es **configurable por examen** (`SCORE_THRESHOLD_DEFAULT`, de C-07/`08`); el MVP usa un valor **conservador** que minimiza falsos positivos.
**Por qué**: RN-SC-05 — saturar la cola humana con falsos positivos hace fracasar el sistema (SU-03); es preferible que el humano recupere algún verdadero positivo perdido a ahogar la capacidad de revisión.
**Alternativa considerada**: umbral agresivo → backlog inmanejable; viola la capacidad sostenible de revisión (C-02).

## Arquitectura del scoring

```
EVENTOS (hypertable TimescaleDB)              ← producidos por C-10
   │  continuous aggregate (refresh al minuto)
   ▼
SCORE INCREMENTAL por sesión
   ├─ peso = f(severidad, frecuencia, persistencia)        [D2]
   └─ correlación: eventos coincidentes > Σ partes         [D3]
   │
   │  POST /sessions/{id}/finish
   ▼
TAREA ASÍNCRONA de cierre                                   [D5]
   ├─ consolida métricas
   ├─ calcula SCORE FINAL
   └─ libera clave de sesión
   │
   ▼
DECISIÓN DE ENCOLADO (por umbral institucional)            [D4, D6]
   ├─ score_final > umbral  → Sesión = FLAGGEADA → cola de revisión (→ C-16)
   └─ score_final ≤ umbral  → Sesión = ARCHIVADA
   │
   ⚠ EN NINGÚN CASO el sistema emite veredicto/sanción     [D4 — inviolable]
        la decisión terminal es HUMANA (C-16)
```

## Modelo de datos afectado

| Estructura | Qué agrega este change | Origen |
|-----------|------------------------|--------|
| `Evento` (hypertable) | continuous aggregates: eventos por sesión por minuto, **score por sesión** | C-05/C-10 (existe); aquí se agregan los agregados de score |
| `Sesión` | transición de estado a `flaggeada` (encolar) o `cerrada/archivada`; campo `score` final | C-05 (enum existe); aquí se usa |

## Risks / Trade-offs

- **[Umbral agresivo satura la cola humana]** → Mitigación: calibración conservadora por defecto (D6, RN-SC-05); afinar con datos reales en Fase 2.
- **[El refresh del continuous aggregate (al minuto) introduce lag en el score en vivo]** → Trade-off **aceptado**: el score en vivo prioriza el panel (C-15); el score que decide el encolado es el **final** (consolidado al cierre, exacto). El lag de un minuto no afecta la decisión terminal.
- **[Modelar correlación mal → doble conteo o subestimación]** → Mitigación: ventana temporal explícita y tests de correlación contra casos conocidos (mirada+foco simultáneos).
- **[Interpretar el score como veredicto en algún consumidor downstream]** → Mitigación: D4 — el score se expone como **prioridad ordinal**, nunca como decisión; la gobernanza se documenta y se testea (ningún path automático produce sanción).
- **[Tarea de cierre se pierde y la sesión queda sin score final]** → Mitigación: la tarea asíncrona es idempotente y reintentable; el continuous aggregate permite recomputar el score final desde los eventos persistidos (sin pérdida).

## Migration Plan

1. Definir los **continuous aggregates** de score sobre la hypertable `Evento` (refresh al minuto).
2. Implementar la función de ponderación (severidad × frecuencia × persistencia) y la lógica de correlación (D2, D3).
3. Implementar `POST /sessions/{id}/finish` → tarea asíncrona de consolidación + liberación de clave (D5).
4. Implementar la decisión de encolado por umbral configurable (flaggeada/archivada) (D4, D6).
5. Garantizar y testear que **ningún path** emite veredicto/sanción automática.
6. Instrumentar la distribución de score (métrica de negocio, `14`) para el monitoreo del backlog.

**Rollback**: feature aislada; el continuous aggregate puede dropearse y recrearse sin perder eventos (la hypertable es la fuente de verdad). La decisión de encolado es recomputable.

## Open Questions

Cerradas por este change:
- ¿Cómo se calcula el score incrementalmente sin recorrer todos los eventos? → continuous aggregate (D1).
- ¿Cómo pesan los eventos correlacionados? → más que la suma (D3).
- ¿El score sanciona? → **NO, jamás**; prioriza (D4).

Fuera de alcance (otros changes):
- Orden de presentación de la cola al revisor + audit de apertura + decisión terminal → **C-16**.
- Afinado de umbrales con datos reales → **Fase 2** (RN-SC-05).
- Reportes y distribución estadística → **C-20**.
