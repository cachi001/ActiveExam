# Design — C-09 `biometria-liveness`

> Design del pipeline de verificación biométrica de identidad, **frontend (MediaPipe) + backend (FastAPI) acoplados**. El cliente captura, hace liveness y calcula el embedding; el backend **re-infiere server-side** (no confía en el cliente), compara 1:1 contra la referencia cifrada, emite la clave de sesión rotativa y gestiona reintentos/escalación. Liveness híbrido + detección de cámara virtual + re-inferencia + revisión humana son la defensa en capas (DD-18); ninguna capa por sí sola es suficiente.

## Context

El proyecto Proctoring trata el embedding como dato sensible por defecto (IN-04, Ley 25.326). DD-03 exige biometría con liveness desde el MVP: sin identidad fuerte, toda la evidencia opera sobre un supuesto no validado. DD-18 fija el enfoque escalonado: MVP = **liveness híbrido propio en el navegador** (pasivo + 1–2 retos activos aleatorios) + **detección de cámara virtual** + **re-inferencia server-side**; la red de seguridad real es la **verificación continua + revisión humana**.

C-09 es el paso `[BIOMETRÍA]` del ciclo (Flujo 2, pasos 2–7). Llega con C-08 resuelto (consentimiento válido o vía alternativa) y C-07 listo (embedding/foto de referencia cifrado, estudiante habilitado). Las entidades `Embedding` (cifrado), `Sesión` (con clave de sesión rotativa) y `Evidencia` ya existen en C-05.

**La amenaza moderna** (`12_biometria §Amenaza moderna 2024–2026`): ya no es solo el ataque de presentación (mostrar algo a la cámara) sino la **inyección de cámara** (camera pipe injection): el atacante inyecta video sintético directo en el flujo de la app, evitando la cámara física; un deepfake "puppet master" puede ejecutar los retos activos. **Implicación honesta**: ningún liveness en navegador es inmune a la inyección. Por eso el diseño combina capas y delega la decisión final a un humano.

**Constraints**:
- **El cliente es sensor no confiable** (RN-GLB-01): el veredicto de liveness/match del cliente **no es la fuente de verdad**; el backend re-infiere sobre el clip.
- **Liveness obligatorio** (RN-BIO-05): prerrequisito de la verificación; sin liveness exitoso no se compara.
- **Umbral conservador** (RN-BIO-03): rechazar a un legítimo es peor que aceptar a un impostor en este paso.
- **Nunca abort, nunca sanción automática** (RN-BIO-04, RN-GLB-02, L2.5): al 3.º fallo se emite evento crítico y se escala a proctor; el sistema no decide "impostor".
- **Embedding cifrado at-rest, finalidad acotada, eliminado al egreso** (RN-BIO-07/08, RN-CO-04).
- **Clip bajo cadena de custodia** (RN-BIO-07): mismo tratamiento que cualquier evidencia.

**Stakeholders**: estudiante (se verifica), proctor (atiende escalación), DPO (audita el tratamiento), equipo de C-10/C-12 (consumen la clave de sesión y la custodia).

## Goals / Non-Goals

**Goals:**
- Captura 3–5 s con instrucciones claras (US-004 CA-1).
- Liveness híbrido propio (pasivo + 1–2 retos activos aleatorios) y detección de cámara virtual (CA-2, DD-18).
- Cálculo del embedding (Face Mesh) y comparación 1:1 por distancia coseno contra la referencia cifrada (CA-3).
- Re-inferencia server-side del clip (RN-GLB-01).
- Emisión de la clave de sesión rotativa (HMAC) si distancia < umbral (CA-4, RN-BIO-02).
- Hasta 2 reintentos; 3.º fallo → evento crítico + escalación a proctor, sin abort (CA-5, RN-BIO-04).
- Clip + embedding persistidos con custodia inicial; embedding cifrado at-rest (CA-6, RN-BIO-07/08).

**Non-Goals:**
- NO implementar la verificación silenciosa continua durante el examen (US-005): C-09 deja el embedding inicial; el bucle continuo es parte del monitoreo (C-10/C-11).
- NO implementar la cadena de custodia completa de 4 etapas (C-12): C-09 deja la **custodia inicial** (hash + firma de sesión); el worker de firma maestra y re-inferencia completa es C-12.
- NO redactar/registrar el consentimiento (C-08): C-09 lo **exige** como precondición.
- NO cargar la foto de referencia (C-07): C-09 la **consume** cifrada.
- NO implementar el panel del proctor (C-15): C-09 **escala** emitiendo el evento crítico.
- NO promover a Fase 2/3 el liveness (modelo pasivo self-hosted, SDK certificado): MVP es el híbrido propio (DD-18).

## Decisions

### D1 — Defensa en capas; ninguna capa es suficiente por sí sola (DD-18)
**Decisión**: combinar liveness híbrido (pasivo + retos activos aleatorios) + detección de cámara virtual + re-inferencia server-side + (downstream) verificación continua + revisión humana. El veredicto de habilitación nace de la comparación 1:1 re-inferida en el backend, no del cliente.
**Por qué**: ningún liveness en navegador es inmune a la inyección de cámara/deepfakes (`12_biometria`). La seguridad surge de apilar capas que suben el costo del ataque, con el humano como red final.
**Alternativa considerada**: confiar en un liveness pasivo del cliente → bypaseable con video pregrabado o inyección; sin re-inferencia, el cliente decide (viola RN-GLB-01).

### D2 — Re-inferencia server-side: el backend no confía en el veredicto del cliente
**Decisión**: el cliente envía el clip 3–5 s (bajo custodia); el backend **recalcula** la inferencia (liveness/embedding/match) sobre el clip exacto y toma la decisión de habilitación con su propio resultado. El veredicto del cliente es una señal, no la verdad.
**Por qué**: RN-GLB-01 — el cliente es sensor no confiable, manipulable. Si el backend confiara en el cliente, un cliente parcheado emitiría "verificado" sin verificar.
**Alternativa considerada**: confiar en el resultado del cliente y solo loguear → identidad falsificable; rompe el supuesto de identidad fuerte de DD-03.

### D3 — Umbral conservador: priorizar no rechazar al legítimo
**Decisión**: el umbral de distancia coseno se configura conservadoramente (RN-BIO-03): se prefiere dejar pasar un caso dudoso (que la verificación continua y la revisión humana recuperan) antes que rechazar a un estudiante legítimo en el inicio.
**Por qué**: el costo de un falso rechazo (estudiante legítimo bloqueado, ansiedad, escalación innecesaria) es peor en este paso que un falso positivo, porque el impostor aún debe superar la verificación silenciosa continua (RN-BIO-06) y la revisión humana.
**Alternativa considerada**: umbral estricto → falsos rechazos de legítimos, fricción, carga sobre el proctor.

### D4 — Reintentos acotados; 3.º fallo escala a humano, nunca aborta ni sanciona (L2.5)
**Decisión**: hasta 2 reintentos. Al 3.º fallo, el sistema emite un **evento crítico** y **escala a un proctor humano**; **no** aborta el examen ni declara "impostor". La decisión la toma el humano.
**Por qué**: RN-BIO-04 + RN-GLB-02 + L2.5 — el sistema flaggea y deriva, nunca sanciona automáticamente. Abortar o sancionar automáticamente violaría el principio rector de decisión humana (RN-RV-07).
**Alternativa considerada**: bloquear tras N fallos → sanción automática, viola L2.5 y RN-GLB-02.

### D5 — El embedding de referencia se lee cifrado y se compara sin exponerlo en claro innecesariamente
**Decisión**: el embedding de referencia (cargado en C-07) se lee cifrado de la DB; la comparación 1:1 ocurre server-side; el embedding capturado se persiste cifrado at-rest, con finalidad acotada y eliminación al egreso.
**Por qué**: el embedding es dato sensible por defecto (IN-04, Ley 25.326). Minimizar su exposición en claro y cifrarlo at-rest es responsabilidad reforzada.
**Alternativa considerada**: comparación en el cliente con la referencia descifrada → expone el embedding sensible al cliente no confiable.

### D6 — La clave de sesión rotativa (HMAC) nace de una verificación exitosa
**Decisión**: solo cuando la comparación 1:1 re-inferida da distancia < umbral, el backend emite la clave de sesión rotativa (HMAC) que habilita el examen y firma los eventos posteriores (C-10) y la evidencia (C-12).
**Por qué**: RN-BIO-02 — la clave de sesión ata criptográficamente toda la telemetría posterior a una identidad verificada. Sin verificación exitosa, no hay clave, no hay examen monitoreado válido.
**Alternativa considerada**: emitir la clave en el login → la telemetría no estaría atada a una identidad biométricamente verificada.

## Arquitectura (frontend MediaPipe + backend FastAPI)

```
[CLIENTE React + MediaPipe]                         [BACKEND FastAPI]            [DB / Storage]
  precondición: ConsentGate (C-08) OK
  │ captura video 3-5s (instrucciones claras)
  │ liveness híbrido:
  │   - pasivo: parpadeo, micro-mov, profundidad 3D (468 landmarks Face Mesh)
  │   - 1-2 retos activos aleatorios
  │ detección de cámara virtual (heurística integridad)
  │ calcula embedding (Face Mesh)
  │── sube clip (hash+firma sesión) por URL firmada ───────────────────────────► storage (custodia inicial)
  │── POST /api/v1/identity/verify {session, clip_ref, client_signals} ─►│
  │                                          re-inferencia server-side (D2)│
  │                                          lee embedding referencia ─────┼──► DB (cifrado, D5)
  │                                          distancia coseno < umbral? (D3)│
  │                                  ┌─ SÍ ─► emite clave de sesión HMAC (D6)┼──► Sesión.clave_rotativa
  │◄── clave de sesión / examen habilitado ─┘                              │
  │                                  └─ NO ─► reintento (máx 2)             │
  │                                          3.º fallo → evento crítico ────┼──► Evento(crítico)
  │                                          + escalación a proctor (D4) ───┼──► panel C-15
  │                                          (NUNCA abort, NUNCA sanción)   │
  persiste: embedding capturado cifrado at-rest (D5) ─────────────────────►│──► DB (Embedding cifrado)
```

## Mapa de requisitos → reglas/criterios

| Capability | Regla / Criterio | Verificación |
|------------|------------------|--------------|
| `liveness-detection` | RN-BIO-05, DD-18, US-004 CA-2 | liveness híbrido obligatorio; sin liveness no se compara |
| `virtual-camera-detection` | DD-18 | señal de cámara virtual detectada y reportada |
| `embedding-computation` | RN-BIO-01, US-004 CA-1 | embedding calculado sobre clip 3–5 s |
| `identity-match-1to1` | RN-BIO-01/02/03, US-004 CA-3 | distancia coseno contra referencia cifrada; umbral conservador |
| `server-side-reinference` | RN-GLB-01 | backend re-infiere; veredicto del cliente no es la verdad |
| `session-key-issuance` | RN-BIO-02, US-004 CA-4 | distancia < umbral → emite clave de sesión rotativa HMAC |
| `retry-and-escalation` | RN-BIO-04, RN-GLB-02, US-004 CA-5, L2.5 | 2 reintentos; 3.º fallo → evento crítico + escalación; sin abort/sanción |
| `biometric-custody-encryption` | RN-BIO-07/08, US-004 CA-6 | clip con custodia inicial; embedding cifrado at-rest; eliminado al egreso |

## Risks / Trade-offs

- **[Inyección de cámara / deepfake en tiempo real]** → Mitigación: D1 — defensa en capas (liveness híbrido + detección de cámara virtual + re-inferencia server-side + verificación continua + revisión humana). Riesgo residual **aceptado y documentado** (`12_biometria`): ningún liveness en navegador es inmune; la red final es el humano.
- **[Cliente parcheado reporta "verificado" sin verificar]** → Mitigación: D2 — re-inferencia server-side; el cliente no decide.
- **[Falso rechazo de estudiante legítimo]** → Mitigación: D3 — umbral conservador + 2 reintentos + escalación a proctor (no bloqueo).
- **[Sanción automática por fallo biométrico]** → Mitigación: D4 — 3.º fallo escala a humano, nunca aborta ni sanciona (L2.5, RN-RV-07).
- **[Exposición del embedding sensible]** → Mitigación: D5 — referencia leída cifrada, comparación server-side, embedding capturado cifrado at-rest, eliminado al egreso.
- **[Sin foto de referencia o sin consentimiento]** → Mitigación: precondiciones de C-07 (referencia) y C-08 (consentimiento/vía alternativa); si falta referencia, la 1:1 no opera (se deriva a la vía alternativa de C-08).
- **Trade-off aceptado**: el liveness híbrido propio del MVP no está certificado PAD Nivel 2+ (eso es Fase 3, DD-18, solo si se eleva el nivel de impacto). Es coherente con el principio de empezar simple y escalar por necesidad.

## Migration Plan

1. **Cliente**: implementar captura 3–5 s, liveness híbrido (pasivo + retos activos aleatorios), detección de cámara virtual y cálculo de embedding (MediaPipe Face Mesh) en el frontend; subida del clip por URL firmada con custodia inicial (hash + firma de sesión).
2. **Backend**: implementar `VerifyIdentity` con re-inferencia server-side, lectura del embedding de referencia cifrado, comparación 1:1 por distancia coseno (umbral conservador), emisión de la clave de sesión rotativa (HMAC) en caso exitoso.
3. **Reintentos/escalación**: implementar el contador de reintentos (máx 2); al 3.º fallo, emitir evento crítico y escalar a proctor, sin abortar.
4. **Custodia/cifrado**: persistir el clip con custodia inicial y el embedding cifrado at-rest, finalidad acotada, marcado para eliminación al egreso.
5. **Tests**: liveness (pasa/falla, reto activo), detección de cámara virtual, distancia coseno (match/no-match), emisión de clave (solo si < umbral), 2 reintentos → 3.º fallo escala (sin abort), embedding persistido cifrado.
6. **Criterio de salida**: `openspec validate --strict` ✓ y tests del scope verdes → desbloquea C-10 (la clave de sesión existe; los eventos pueden firmarse).

**Rollback**: la verificación es idempotente por intento; una verificación fallida no deja estado de examen habilitado. El embedding capturado en una verificación abortada se elimina (no se retiene biometría innecesaria, minimización).

## Open Questions

- ¿Qué heurística concreta de detección de cámara virtual se adopta en el MVP? → se elige durante apply dentro del marco DD-18 (varianza de pixels, integridad del pipeline, DevTools); la spec fija el **qué** (detectar y reportar), no el **cómo** exacto.
- ¿La re-inferencia server-side del clip usa el mismo modelo que el cliente o uno self-hosted distinto? → MVP usa re-inferencia sobre el clip; el modelo pasivo self-hosted dedicado es Fase 2 (DD-18). C-09 deja la re-inferencia server-side operativa.
- ¿Cobertura de la verificación silenciosa continua (US-005, RN-BIO-06)? → fuera del scope de C-09 (deja el embedding inicial); el bucle continuo es del monitoreo (C-10/C-11).
