## Context

El enrollment biométrico y el consentimiento dejan de ser pasos repetidos del pre-examen y se vuelven un acto **único, reutilizable y con vigencia** que vive en el Perfil del alumno. Esta es una capability de gobernanza ALTO: toca biometría, consentimiento y legal a la vez. La demo es frontend (React + Vite + Zustand + Tailwind, mock en `frontend/src/lib/api.ts`), reutilizando el motor de visión existente (`frontend/src/vision/VisionEngine.ts`, `MediaPipeVisionEngine.ts`, `liveness.ts`). La verificación real es server-side; el cliente es sensor no confiable. No hay sanción automática (L2.5).

## Decisions

### 1. El enrollment vive en el Perfil, una sola vez
El consentimiento y la captura de referencia biométrica se hacen en una pantalla de Perfil dedicada, **no** como pasos del pre-examen. El flujo de pre-examen pasa a **verificar** contra la referencia ya enrollada (1:1) en lugar de **capturarla**. Motivo: minimización de datos sensibles (un solo embedding/imagen de referencia por período de vigencia en vez de uno por rendición) y trazabilidad legal del acuse.

### 2. El gate de consentimiento se resuelve en el perfil, manteniendo TODAS las garantías legales
Se reubica `consent-gate` e `informed-consent-presentation`: el acuse afirmativo sin casilla premarcada (RN-CO-02), el texto versionado con acuse inmutable (RN-CO-01) y la vía alternativa sin biometría (RN-CO-05) se presentan dentro del perfil. Cambia el **cuándo/dónde**, no el **qué**. El gate ahora habilita "perfil completo", no "siguiente examen".

### 3. Vigencia de la referencia: 24 meses configurable
La captura de referencia caduca a los **24 meses** (parámetro de configuración, no hardcode). Fundamento doble:
- **Face template aging**: la literatura biométrica documenta degradación notoria de la coincidencia facial a los **2–4 años**, más marcada en adultos jóvenes (la población universitaria objetivo). 24 meses se ubica en el extremo conservador de esa ventana, priorizando precisión sobre comodidad.
- **Ley 25.326 — responsabilidad reforzada**: el dato biométrico es sensible; mantener una referencia indefinida amplía la superficie de riesgo. Una vigencia acotada con renovación periódica es coherente con minimización y calidad del dato.

### 4. Renovación anticipada gatillada por deriva del embedding
La verificación silenciosa continua (ya en la KB, `12_biometria_y_liveness`) detecta deriva del embedding respecto de la referencia. Si la deriva supera el umbral de forma sostenida, el sistema **marca la referencia para renovación anticipada** y la solicita en el próximo acceso al perfil. La deriva **nunca** sanciona ni invalida una rendición en curso por sí sola: solo gatilla renovación (L2.5, decisión disciplinaria siempre humana).

### 5. Imagen de referencia persistida como dato sensible
Además del embedding, el perfil guarda la **imagen de referencia** (necesaria para revisión humana y re-inferencia server-side). Se trata como dato sensible: cifrada at-rest, finalidad acotada a la verificación de identidad, eliminada al egreso del estudiante, y los holds legales **difieren** esa eliminación. Lleva metadato de `captured_at` / `expires_at` / `version`.

### 6. DNI opcional y flaggeado (fase posterior)
El escaneo de DNI es un paso **opcional** que no bloquea el enrollment ni la habilitación para rendir. Se modela detrás de un flag para una fase posterior. Resguardo legal: el DNI es dato sensible (Ley 25.326); si se captura, sigue la misma custodia que la imagen de referencia (cifrado, finalidad acotada, eliminación al egreso, holds difieren). Mientras el flag esté off, la UI lo presenta como "próximamente / opcional".

### 7. Gate de habilitación = perfil completo
"Perfil completo" = consentimiento válido vigente **(o** vía alternativa elegida**)** + referencia biométrica **vigente**. Solo con perfil completo el alumno puede inscribirse/rendir; esto alimenta el `puedeRendir` que modela C-21. Si la referencia caduca, el alumno sigue "habilitado para gestionar perfil" pero **no** para rendir hasta renovar.

### 8. Reuso del motor de visión existente
La captura de referencia reutiliza `VisionEngine` / `MediaPipeVisionEngine` (Face Detection / Mesh 468 / Pose en Web Worker) y `liveness.ts` (retos activos + pasivo). No se introduce un motor nuevo. El embedding se calcula con Face Mesh sobre el clip, igual que en C-09, pero en contexto de perfil.

### 9. Server-side es la fuente de verdad
Todo lo capturado en el cliente (clip, embedding, imagen, DNI) se re-hashea, re-infiere y firma server-side (cadena de custodia C-12). En la demo esto se mockea en `api.ts`, pero las specs lo exigen como comportamiento.

## Risks / Trade-offs

- **Referencia stale entre renovaciones**: una referencia válida hasta 24 meses puede degradarse antes del vencimiento. Mitigación: la verificación silenciosa continua + renovación anticipada por deriva.
- **Vía alternativa y gate**: si el alumno elige vía alternativa sin biometría, "perfil completo" se resuelve sin referencia; el gate debe permitir rendir derivando la verificación al proctor humano (consistente con `no-biometric-alternative-path` de C-08).
- **Migración del flujo C-08/C-09**: mover consentimiento y captura fuera del pre-examen es BREAKING respecto del orden original; el pre-examen queda como verificación 1:1 contra la referencia.
- **DNI flaggeado**: dejar el DNI como fase posterior evita asumir un proveedor OCR/validación documental antes de tiempo, pero deja un hueco de identidad documental que la institución debe aceptar para la demo.

## Open Questions

- ~~**¿Hace falta un acuse de consentimiento por-examen además del de perfil?**~~ **RESUELTA — C-26.** El usuario decidió un modelo de **consentimiento EN CAPAS** (implementado en C-26):
  - **Capa de perfil (C-22, esta)**: acuse PESADO del dato biométrico/sensible. Texto versionado, acción afirmativa, acuse inmutable, vía alternativa. Es la **base de licitud** del tratamiento (Ley 25.326).
  - **Capa por-examen (C-26)**: acuse LIVIANO y ESPECÍFICO por (estudiante, examen). Da **finalidad/propósito concreto** (art. 4, Ley 25.326) para ESA instancia de tratamiento — cátedra, fecha/hora, duración, alcance de monitoreo. NO re-captura biometría ni re-presenta el texto pesado: **referencia** el acuse de perfil vigente.
  - El gate de rendir pasa a ser EN CAPAS: `puedeRendir(examenId)` evalúa (1) perfil completo → (2) acuse por-examen afirmativo para ESE examen. Si falta (2) retorna `{ codigo: 'acuse_examen_faltante' }` y deriva a completarlo (nunca sanciona — L2.5).
  - Ver detalles completos: `openspec/changes/c-26-acuse-consentimiento-por-examen/design.md`.
- **Umbral y ventana de deriva** para gatillar renovación anticipada: a definir con datos de la verificación silenciosa continua (no bloquea esta demo).
