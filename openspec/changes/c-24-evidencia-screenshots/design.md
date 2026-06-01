## Context

El modelo de evidencia automática vigente captura un **clip de video de 5–10 s** por cada evento de severidad alta/crítica:

- `05_reglas_de_negocio.md` **RN-CC-01**: "Solo los eventos de severidad alta o crítica disparan captura automática de evidencia (clip de 5–10 s)."
- `07_flujos_principales.md` §EVIDENCIA: "evento severo → clip 5-10s → hash+firma cliente → upload directo a storage (URL firmada)."
- `14_observabilidad_y_devops.md` §Capacity: "Subidas de evidencia: ~2,8 GB por examen (4 clips/estudiante)."
- `11_ia_y_vision.md`: el backend re-ejecuta modelos **sobre el clip** (1–10 s) y compara con lo reportado; la discrepancia es señal forense de tampering.

El sistema es **L2.5**: nunca sanciona automáticamente; la evidencia es **insumo para revisión humana** y el cliente es un **sensor no confiable** (toda evidencia se re-hashea/re-infiere/firma server-side, WORM cifrado). La Ley 25.326 y `13_legal_y_cumplimiento_argentina.md` exigen **minimización de datos** y **proporcionalidad** (sin video continuo).

Este change es una **decisión de arquitectura** (gobernanza ALTO) que cambia el artefacto de evidencia.

## Goals / Non-Goals

**Goals**
- Reemplazar el clip de video por un **screenshot** (frame único) como artefacto de evidencia automática.
- Definir la **cadencia** de captura: **event-driven + heartbeat configurable por examen**.
- Conservar la **cadena de custodia completa** sobre el nuevo binario (imagen).
- Reducir drásticamente costo/almacenamiento y mejorar la minimización de datos.

**Non-Goals**
- No se modifica el motor de detección ni los umbrales de severidad (siguen iguales; cambia el artefacto que producen).
- No se reintroduce video continuo bajo ninguna circunstancia.
- No se cambia el contrato de las capabilities de custodia de c-12 (`evidence-custody-chain`, `evidence-worm-storage`, `evidence-audit-log`): solo cambia el tipo de binario al que aplican.
- No se elimina la posibilidad futura de clips puntuales si una revisión humana lo justifica — eso sería otro change.

## Decisions

### DD-24-01 — Evidencia por SCREENSHOT (frame único) en lugar de CLIP de video

**Decisión**: El artefacto de evidencia automática pasa de **clip de 5–10 s** a **screenshot** (captura de un frame único). El disparo es **event-driven** (evento de severidad alta/crítica) **+ heartbeat** periódico de baja frecuencia, configurable por examen.

**Motivación**: costo. El modelo actual cuesta **~2,8 GB por examen** (`14_observabilidad_y_devops.md`); un frame son **KB**.

#### A favor
- **Costo/almacenamiento drásticamente menor**: de ~GB de video a KB de imágenes por examen. El SLI de "subidas de evidencia pesadas" deja de ser un cuello de botella.
- **Más proporcional para L2.5**: la evidencia mínima necesaria para que un revisor humano contextualice un flag, sin acumular video.
- **Mejor minimización de datos**: lo apoya `13_legal_y_cumplimiento_argentina.md` (Ley 25.326, proporcionalidad, sin video continuo). Menos dato sensible retenido.

#### En contra / lo que se PIERDE (aceptado como tradeoff L2.5)
- **No hay re-inferencia TEMPORAL**: sobre un clip (1–10 s) el backend re-corría modelos y comparaba dinámica/movimiento (`11_ia_y_vision.md`); sobre un frame fijo la re-inferencia es **estática** (labels/confidences del frame), no temporal.
- **No hay re-verificación de liveness/movimiento** sobre la evidencia: un frame no permite analizar parpadeo, micro-movimiento ni continuidad temporal. (El liveness del enrollment/verificación vive en su propio flujo, c-22/biometría — este tradeoff aplica a la evidencia de eventos, no al liveness de identidad.)
- **Evidencia más débil para impugnaciones que requieran contexto temporal**: ante una apelación donde el contexto dinámico importe, un frame da menos información que un clip.

**Aceptación explícita**: para un sistema **L2.5** cuya decisión es **siempre humana** y donde la evidencia **prioriza, no dictamina**, un frame con cadena de custodia íntegra es **suficiente y proporcional**. Se acepta conscientemente perder el contexto temporal a cambio de minimización y costo.

**Alternativas consideradas**
- *Mantener clips de 5–10 s* (status quo): rechazada por costo y por exceso de retención frente a L2.5.
- *Clip corto de 1–2 s*: rechazada — sigue siendo video (mayor costo, mayor dato sensible) por una ganancia temporal marginal.
- *Solo event-driven, sin heartbeat*: rechazada — sin línea base, un revisor no tiene referencia de "normalidad" del estudiante para contextualizar el frame del evento.
- *Solo heartbeat periódico, sin event-driven*: rechazada — perdería el frame del momento exacto del evento severo, que es la evidencia primaria.

### DD-24-02 — Cadencia: event-driven + heartbeat configurable por examen

**Decisión**: dos disparadores complementarios.
- **Event-driven**: un screenshot en el instante en que un detector emite un evento de severidad **alta/crítica** (alineado con RN-CC-01). Es la evidencia primaria del flag.
- **Heartbeat**: un screenshot periódico de **baja frecuencia** (p. ej. cada N minutos, configurable por examen) que provee una **línea base** de la sesión, independiente de eventos.

La frecuencia del heartbeat y su activación son **parámetros de configuración por examen** (un examen de alto riesgo puede subir la frecuencia; uno de bajo riesgo puede desactivarlo), respetando la proporcionalidad: a mayor frecuencia, mayor dato retenido → mayor justificación necesaria.

**Rationale**: el event-driven captura el "qué pasó"; el heartbeat da el "cómo se veía normalmente", necesario para que la revisión humana interprete el frame del evento sin sobre-retener.

### DD-24-03 — Cadena de custodia intacta sobre el frame

**Decisión**: la cadena de custodia de c-12 se aplica **sin cambios de contrato** al nuevo binario imagen:
1. **Cliente (zona no confiable)**: calcula `hash_cliente = SHA-256(screenshot)` y `firma_cliente = HMAC(clave_sesion, hash_cliente)`; sube el binario **directo al storage** por URL firmada de PUT (el binario no transita por el backend). (RN-CC-02/04, `07_flujos_principales.md` §117.)
2. **Backend**: valida la firma, **recalcula el hash**, persiste metadata, escribe **audit log** y deposita en bucket **WORM cifrado**.
3. **Worker / clave maestra**: re-descarga, **3.ª verificación de hash**, **firma con clave maestra** (RSA-2048/Ed25519) y **re-inferencia firmada** — ahora **estática sobre el frame** (detección de objetos/rostros en la imagen), no temporal sobre clip.

El cliente sigue siendo **sensor no confiable**: nada se confía hasta la re-validación server-side.

## Risks / Trade-offs

- [Pérdida de contexto temporal en la evidencia] → Mitigación: heartbeat para línea base + posibilidad (fuera de alcance) de escalar a clip puntual si una revisión humana lo justifica; documentar el límite L2.5 en el material de revisores (c-02).
- [Re-inferencia estática puede dar menos señal forense de tampering que la temporal] → Mitigación: se conserva la comparación cliente-vs-server sobre el frame (discrepancia = señal); la firma de hash en 3 etapas mantiene la detección de manipulación del binario.
- [Heartbeat mal configurado podría sobre-retener (alta frecuencia) o sub-evidenciar (desactivado)] → Mitigación: frecuencia por examen con default conservador y tope; justificación de proporcionalidad documentada por examen.
- [Frame único podría no contener el indicio si el evento es muy fugaz] → Mitigación: la captura se dispara en el instante del evento (no muestreada); el detector ya determinó severidad antes de pedir el frame.
- [Impugnaciones que exijan video] → Mitigación: aceptado explícitamente como límite L2.5; se comunica en el acuerdo de proctoring (c-01) y a revisores (c-02).

## Migration Plan

1. La capability `evidence-capture-upload` (c-12) se **modifica vía delta** dentro de este change (no se editan archivos de c-12).
2. El cliente reemplaza la captura de `MediaRecorder`/clip por captura de frame (canvas/`ImageCapture`); mantiene el mismo flujo de hash+firma y presigned PUT.
3. El worker de re-inferencia cambia de pipeline temporal (clip) a pipeline de imagen estática; el resto de la cadena de custodia no cambia.
4. Se añade configuración de **heartbeat por examen** (frecuencia, on/off) con default conservador.
5. **Rollback**: como el contrato de custodia (hash/firma/WORM/audit) no cambia, revertir a clip implica solo revertir el tipo de binario capturado y el pipeline de re-inferencia; la evidencia de imagen ya almacenada sigue siendo válida y verificable.

## Open Questions

- Frecuencia default del heartbeat y su tope máximo por nivel de riesgo de examen (a confirmar con legal/c-01 por proporcionalidad).
- Formato/calidad del screenshot (PNG sin pérdida vs JPEG) — balance entre fidelidad forense y tamaño.
- ¿Se captura también un screenshot del compartir-pantalla además de la cámara, o solo cámara? (depende del evento que disparó).
