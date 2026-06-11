# Proposal — C-09 `biometria-liveness`

> **Naturaleza del change**: cierre del ciclo pre-monitoreo (FASE 1, governance **CRÍTICO**), **frontend + backend acoplados**. Implementa la **verificación biométrica de identidad** (US-004, FR-04, UC-01): el último paso antes de habilitar el examen. Es lo que da **identidad fuerte** a toda la evidencia posterior — sin esto, todo el monitoreo opera sobre un supuesto de identidad no validado (DD-03). Biometría + liveness es **obligatoria desde el MVP** (DD-03, DD-18).

## Why

DD-03 lo dice sin ambigüedad: **sin identidad fuerte, toda la evidencia opera sobre un supuesto no validado**. Por eso la biometría con liveness es obligatoria desde la Fase 1, no diferida. C-09 es el paso `[BIOMETRÍA]` del Flujo 0 y los pasos 2–7 del Flujo 2.

- **RN-BIO-01**: la verificación ocurre en cuatro pasos — captura de video 3–5 s, liveness, cálculo de embedding, comparación 1:1 por distancia coseno contra el embedding precomputado. Es el contrato del change.
- **RN-BIO-05**: sin liveness el bypass es trivial (mostrar una foto/video del compañero); el liveness es **prerrequisito obligatorio**. Y la amenaza moderna ya no es solo el ataque de presentación sino la **inyección de cámara** (deepfakes en tiempo real): por eso DD-18 exige liveness **híbrido propio** (pasivo + 1–2 retos activos aleatorios) **+ detección de cámara virtual + re-inferencia server-side**.
- **RN-GLB-01**: el cliente es un **sensor no confiable**. El liveness y el embedding se calculan en el navegador (MediaPipe), pero un cliente puede ser manipulado. La defensa realista es **re-inferencia server-side del clip**: el backend no confía en el veredicto del cliente, lo recalcula sobre el clip exacto.
- **RN-BIO-04**: hasta **2 reintentos**; al **3.º fallo** → **evento crítico + escalación a proctor humano**, **nunca abort automático** (RN-GLB-02). El sistema **nunca sanciona ni bloquea automáticamente** (L2.5): flaggea y escala a decisión humana.
- **RN-BIO-02 / RN-BIO-07**: si la distancia coseno < umbral, el backend emite la **clave de sesión rotativa (HMAC)** que firma todos los eventos posteriores; el clip y el embedding se persisten con **cadena de custodia inicial** (cifrado at-rest, eliminado al egreso — RN-BIO-08).

Este change **consume** la foto/embedding de referencia cargado en C-07 y exige el **consentimiento válido** de C-08 como precondición legal. Sin C-07 (referencia) y C-08 (consentimiento), la verificación 1:1 no puede operar legalmente ni técnicamente.

## What Changes

Agrega la verificación biométrica de identidad, **acoplando frontend (captura, liveness, embedding, detección de cámara virtual) y backend (re-inferencia, comparación contra referencia cifrada, emisión de clave de sesión, reintentos, custodia)**. Se inserta en el Flujo 2, pasos 2–7, **después** del gate de consentimiento de C-08.

- **Cliente (frontend, MediaPipe)**: captura de video 3–5 s con instrucciones claras; **liveness híbrido propio** = análisis pasivo (parpadeo involuntario, micro-movimientos, profundidad 3D de los 468 landmarks de Face Mesh) + **1–2 retos activos aleatorios**; cálculo del **embedding** (Face Mesh); **detección de cámara virtual** (heurística de integridad — DD-18).
- **Comparación 1:1**: distancia coseno entre el embedding capturado y el **embedding de referencia leído cifrado de la DB** (cargado en C-07). Umbral configurado **conservadoramente** (RN-BIO-03): rechazar a un legítimo es peor que aceptar a un impostor en este paso (la verificación continua y la revisión humana son la red de seguridad).
- **Backend**: **re-inferencia server-side** del clip (no confía en el cliente, RN-GLB-01); si la distancia < umbral, emite la **clave de sesión rotativa (HMAC)** que habilita el examen y firma los eventos posteriores.
- **Reintentos y escalación**: hasta **2 reintentos**; al **3.º fallo** → **evento crítico** + **escalación a proctor humano**, sin abortar (RN-BIO-04, RN-GLB-02). El sistema no decide "impostor": flaggea y deriva a humano (L2.5).
- **Cadena de custodia inicial**: el clip de verificación sigue la misma cadena de custodia que cualquier evidencia (hash + firma); el embedding se persiste **cifrado at-rest**, con finalidad acotada, eliminado al egreso del estudiante (RN-BIO-07, RN-BIO-08).

## Capabilities

> Las capabilities modelan la verificación biométrica como pipeline cliente+servidor verificable. Cada requisito SHALL se prueba por test (liveness, distancia coseno, emisión de clave, reintentos→escalación, cifrado del embedding).

### New Capabilities

- `liveness-detection`: liveness **híbrido propio** en el cliente — pasivo (parpadeo, micro-movimientos, profundidad 3D Face Mesh) + 1–2 retos activos aleatorios — prerrequisito obligatorio de la verificación (RN-BIO-05, DD-18).
- `virtual-camera-detection`: detección de cámara virtual / inyección de pipeline en el cliente (heurística de integridad), defensa frente a deepfakes inyectados (DD-18).
- `embedding-computation`: cálculo del embedding facial (Face Mesh) sobre el clip 3–5 s en el cliente.
- `identity-match-1to1`: comparación 1:1 por **distancia coseno** contra el embedding de referencia leído **cifrado** de la DB, con umbral conservador (RN-BIO-01/02/03).
- `server-side-reinference`: **re-inferencia server-side** del clip — el backend recalcula y no confía en el veredicto del cliente (RN-GLB-01).
- `session-key-issuance`: emisión de la **clave de sesión rotativa (HMAC)** cuando la verificación es exitosa, que firma los eventos posteriores (RN-BIO-02).
- `retry-and-escalation`: hasta 2 reintentos; al 3.º fallo → **evento crítico + escalación a proctor**, nunca abort (RN-BIO-04, RN-GLB-02, L2.5).
- `biometric-custody-encryption`: cadena de custodia inicial del clip y **persistencia cifrada at-rest del embedding**, finalidad acotada, eliminado al egreso (RN-BIO-07/08).

### Modified Capabilities

<!-- Ninguna. No existen specs de dominio previas en openspec/specs/ que este change modifique. -->

(Ninguna — no existen specs de dominio previas que este change modifique.)

## Impact

- **Bloquea**: C-10 (event-ingestion-transport). Sin la **clave de sesión rotativa** que C-09 emite, los eventos del estudiante no pueden firmarse ni validarse; el monitoreo continuo no arranca. C-09 también provee el embedding inicial que la **verificación silenciosa continua** (US-005, RN-BIO-06) comparará durante el examen.
- **Dependencias entrantes**: `C-08` (consentimiento — precondición legal de la captura biométrica). Transitivamente: C-07 (foto/embedding de referencia, lista de habilitados), C-06 (auth), C-05 (`Embedding`, `Sesión`, `Evidencia`), C-04.
- **Datos/contratos que produce** (consumidos downstream):
  - Clave de sesión rotativa (HMAC) → firma de eventos en **C-10** y de evidencia en **C-12**.
  - Embedding inicial cifrado → **verificación silenciosa continua** (US-005, RN-BIO-06) durante el examen.
  - Evento crítico de fallo de verificación + escalación → panel del proctor (**C-15**).
  - Clip de verificación con custodia inicial → cadena de custodia de **C-12**.
- **Relación con C-03**: la persistencia del clip y la re-inferencia server-side usan la **cola ganadora de C-03** (re-inferencia + firma < 30 s); C-09 produce el primer clip que recorre esa cola.
- **Actores afectados**: estudiante (se verifica), proctor (recibe la escalación al 3.º fallo y atiende la vía alternativa de C-08), DPO (audita el tratamiento biométrico cifrado y acotado).
- **Privacidad por diseño / L2.5**: el embedding es dato sensible por defecto (cifrado at-rest, finalidad acotada, eliminado al egreso — Ley 25.326, IN-04). El sistema **nunca** decide automáticamente que alguien es un impostor: ante fallo, flaggea y **escala a un humano** (DD-03, L2.5, RN-RV-07).
