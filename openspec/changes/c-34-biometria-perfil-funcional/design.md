## Context

`EnrollmentBiometricStep.tsx` tiene cámara real (`getUserMedia`) pero el flujo de liveness y el embedding son totalmente mock:

- **Liveness mock**: los retos se "resuelven" tocando botones (`resolverReto(id)` en `:83`). No hay frame processing ni thresholds; cualquier usuario puede completar el enrollment sin mover la cara.
- **Embedding falso**: `:116` genera `Array.from({length:128}, () => Math.random()*2-1)`. El valor es no-determinista y no representa ningún rasgo facial real.
- **Sin fullscreen en móvil**: en pantallas pequeñas, el visor de cámara (260×320px) queda dentro del scroll de la página; la captura de liveness activo requiere ver claramente los gestos en una ventana inmersiva.

El motor real ya existe (`RealMediaPipeVisionEngine.ts`) y está siendo usado en el harness admin. La lógica pura de liveness (`liveness.ts`) ya está testeada y lista. El loader lazy con singleton también existe (`harnessEngineLoader.ts`). Solo falta cablearlos en el enrollment.

**Restricciones del cliente**:
- El cliente es SENSOR NO CONFIABLE (RN-GLB-01): esta verificación es para UX/test. El veredicto real sigue siendo server-side (C-12).
- El embedding cliente es dato sensible (Ley 25.326): no se persiste en claro fuera del flujo API existente.
- Bundle inicial objetivo < 500 KB: el motor WASM debe seguir siendo lazy.
- L2.5 intacto: ninguna decisión automática sobre el estudiante.

---

## Goals / Non-Goals

**Goals:**

1. Que los retos de liveness se resuelvan por DETECCIÓN REAL (thresholds sobre landmarks/gaze/bounding-box), no por botón.
2. Que el embedding enviado al backend sea `embeddingFromLandmarks(landmarks)` (determinista desde geometría facial), no random.
3. Que en móvil/touch la captura entre en fullscreen (o un fallback fixed-inset) al iniciar.
4. Que el loader del motor sea lazy, singleton, y no duplique la lógica de `harnessEngineLoader.ts`.
5. Que haya un fallback/skip manual visible solo cuando el motor no puede cargar (WebGL ausente / entorno de test).

**Non-Goals:**

- Cambiar el contrato de la API (`api.guardarReferenciaBiometrica`): el backend recibe exactamente los mismos campos.
- Cambiar la política de privacidad del embedding (RN-BIO-07/08): el flujo de custodia server-side es C-12.
- Usar liveness para verificar identidad 1:1 (ese es C-09/backend): esto es solo UX de captura de referencia.
- Verificación PAD Nivel 2+ (Fase 2 del roadmap): este change es Nivel 1 (liveness híbrido propio).
- Cambiar el harness admin (`harnessEngineLoader.ts`) ni sus rutas.
- Agregar detección de múltiples personas (solo se usa la primera cara detectada).

---

## Decisions

### D-1: Loader lazy para enrollment — loader separado vs. loader genérico centralizado

**Decisión**: Crear `enrollmentEngineLoader.ts` como módulo propio con el mismo patrón singleton de `harnessEngineLoader.ts` (copiar la estructura, no importar desde ella).

**Alternativas consideradas**:
- **A: Generalizar `harnessEngineLoader.ts`** a un `visionEngineLoader.ts` central exportando ambas funciones. Ventaja: un solo módulo. Desventaja: el nombre actual está documentado en C-30/C-32/specs; renombrarlo genera un MODIFIED de spec en cascada. El harness admin ya depende de `harnessEngineLoader` por sus rutas de import.
- **B: Importar `loadRealEngine()` del harness directamente**. Desventaja: acopla el enrollment al loader del harness; si el harness hace dispose, el enrollment pierde el motor.
- **C: Loader separado `enrollmentEngineLoader.ts`** (elegida). Los ciclos de vida son independientes (el harness se monta en `/admin/...`; el enrollment en `/perfil`). Cada módulo gestiona su propio singleton. No afecta los specs ni el loader del harness. Es la opción más conservadora y alineada con la restricción de no tocar el harness.

### D-2: Mapeo reto → métrica de landmarks

Los 5 retos del catálogo (`ACTIVE_CHALLENGES` en `liveness.ts`) se detectan así:

| Reto | Métrica | Threshold | Frames consecutivos |
|------|---------|-----------|---------------------|
| `girar_izquierda` | `gaze.x < -0.25` (gazeFromIris) | gaze.x normalizado (-1..1) | 3 frames |
| `girar_derecha` | `gaze.x > +0.25` | gaze.x normalizado (-1..1) | 3 frames |
| `parpadear` | Variación de apertura ocular: distancia vertical entre landmark superior e inferior del ojo < threshold (< 0.015 normalizado) | cierre de ojo | 2 frames |
| `acercarse` | Bounding box del rostro (FaceDetector): `bbox.width > 0.55` (normalizado al ancho del frame) | face bbox width normalizado | 3 frames |
| `sonreír` | Distancia horizontal entre comisuras de boca (landmarks 61 y 291) > 0.12 normalizado | mouth width normalizado | 3 frames |

**Nota sobre parpadear**: `liveness.ts` ya tiene `derivePassiveSignals.blinkVariance` basado en varianza de apertura entre frames. Para el reto activo de parpadear se usa la señal directa de cierre (landmark ocular < threshold) en un frame puntual, no varianza de clip.

**Índices de landmarks FaceLandmarker** usados:
- Ojo izquierdo superior: 159, inferior: 145 (apertura vertical).
- Comisura boca izquierda: 61, derecha: 291.
- Gaze: vía `gazeFromIris()` con IRIS_LEFT_CENTER=468, EYE_LEFT_OUTER=33, EYE_LEFT_INNER=133.

### D-3: Loop de detección por frame en el enrollment

```
┌─────────────────────────────────────────────────────────────────────┐
│ Fase 'capturando'                                                    │
│                                                                     │
│  requestAnimationFrame loop                                         │
│    │                                                                │
│    ├─ createImageBitmap(videoRef.current)                           │
│    ├─ engine.detectFaceMesh(bitmap) → { landmarks, gaze }           │
│    ├─ engine.detectFaces(bitmap) → { faces[0].bbox }               │
│    │                                                                │
│    ├─ Para cada reto pendiente:                                     │
│    │    evaluarReto(reto, landmarks, gaze, bbox)                    │
│    │    → si threshold cumplido N frames consecutivos               │
│    │       → marcar reto resuelto (resolverReto)                    │
│    │                                                                │
│    ├─ Si todos los retos resueltos → procesarCaptura()              │
│    └─ Si fase != 'capturando' → cancelar loop                       │
└─────────────────────────────────────────────────────────────────────┘
```

**Frecuencia**: `requestAnimationFrame` (~30fps en móvil, ~60fps en desktop). No se necesita throttle artificial: `detectForVideo` de MediaPipe maneja timestamps monotónicos. Si el frame es igual al anterior (RAF muy rápido), `createImageBitmap` retorna el mismo bitmap; `detectForVideo` requiere timestamp incremental (ya lo hace `nextTimestamp()` en `RealMediaPipeVisionEngine`).

**Frame accumulator por reto**: `Map<ActiveChallenge, number>` — cuenta cuántos frames consecutivos superaron el threshold. Al romper consecutividad, se resetea a 0. Cuando llega al mínimo (`FRAMES_MIN`), se dispara `resolverReto`.

**Cleanup**: `useRef<number>` con el handle de RAF; en `useEffect` cleanup y al terminar la fase, se cancela con `cancelAnimationFrame`.

### D-4: Embedding real desde landmarks

Al completar todos los retos, `procesarCaptura` toma el último `FaceMeshSignal` disponible (cacheado del último frame del loop) y llama:

```typescript
const embedding = embeddingFromLandmarks(lastLandmarks);
```

`embeddingFromLandmarks` vive en `MediaPipeVisionEngine.ts:97-110` — pura, determinista, sin efectos secundarios. Produce un vector de 3×N floats (N = nro de landmarks) normalizado por la norma euclidiana. Para 468 landmarks produce 1404 valores, no 128 — el backend debe aceptar el tamaño real. Si el backend espera exactamente 128, el design nota el riesgo (ver D-7).

### D-5: Fullscreen en móvil — requestFullscreen + fallback iOS

**Detección de móvil/touch**:
```typescript
const isMobileOrTouch = () =>
  window.innerWidth < 768 || ('ontouchstart' in window) || navigator.maxTouchPoints > 0;
```

**Flujo al iniciar captura**:
```
iniciarCaptura()
  │
  ├─ Si isMobileOrTouch()
  │    ├─ containerRef.current.requestFullscreen?.()
  │    │    └─ Si rechaza (iOS Safari) → setFullscreenFallback(true)
  │    └─ Si requestFullscreen no existe → setFullscreenFallback(true)
  │
  └─ setFase('capturando')
```

**Fallback `fullscreenFallback`**: cuando `true`, el contenedor de captura recibe clases `position: fixed; inset: 0; z-index: 50; background: black` vía Tailwind (`fixed inset-0 z-50 bg-black`). Efecto visual idéntico al fullscreen real pero implementado en CSS. El botón de cancelar sigue siendo accesible.

**Salida de fullscreen**:
- Al completar (`fase === 'completado'`): `document.exitFullscreen?.()` + `setFullscreenFallback(false)`.
- Al cancelar (botón): ídem.
- Listener `document.fullscreenchange`: sincroniza el estado interno si el usuario sale con el botón nativo del browser.

**Caveats de iOS Safari**:
- `requestFullscreen` en elementos arbitrarios NO está soportado en iOS Safari. Solo funciona en `<video>` con el atributo `webkit-playsinline`. Este caveat es conocido y documentado; el fallback CSS es la solución.
- iOS 16.4+ soporta `requestFullscreen` solo en páginas instaladas como PWA (homescreen). Para browser normal, el fallback es el camino.

### D-6: Spinner de carga del motor

Mientras el motor carga (antes de que `loadEnrollmentEngine()` resuelva), el botón "Iniciar captura" muestra un spinner con "Preparando verificación…" (similar al patrón de C-32). Si la carga falla, se muestra un mensaje de error con opción de retry y un botón "Continuar sin detección" que activa el modo fallback manual.

### D-7: Tamaño del embedding — riesgo de contrato

`embeddingFromLandmarks(468 landmarks)` produce 1404 valores, no 128. El campo `embedding` de `api.guardarReferenciaBiometrica` en el mock actual acepta `number[]` sin validación de longitud. Para la demo este no es un problema. Para producción, el backend debe definir el tamaño canónico (128 PCA-comprimido vs. 1404 raw) — esto es una decisión de C-09 backend, fuera del scope de este change.

**Mitigación para demo**: se documenta en el código y en el design que el embedding de este change es el vector raw de `embeddingFromLandmarks`, y que el backend de producción comprimirá via PCA o una capa densa a 128 dims.

---

## Risks / Trade-offs

| Riesgo | Mitigación |
|--------|-----------|
| **iOS Safari no soporta `requestFullscreen`** | Fallback CSS `fixed inset-0` — experiencia visual equivalente. Documentado con caveat explícito en el código. |
| **Performance en móvil low-end**: el loop RAF + FaceMesh puede calentar el CPU. | El motor corre en el mismo thread (sin Worker en el enrollment, a diferencia del harness). Riesgo aceptable para demo/enrollment (~5-10s). Si el frame tarda > 100ms, el RAF se auto-throttle porque el callback se llama solo cuando el motor resuelve. |
| **Motor no disponible (WebGL ausente)**: `loadEnrollmentEngine()` rechaza. | Fallback manual visible solo cuando el motor no cargó — el usuario puede tocar el botón del reto. UX degradada honesta (L2.5 no se rompe). |
| **Tamaño del embedding**: 1404 floats vs. 128 esperados. | Mock API acepta cualquier longitud. Para producción: decisión de C-09 backend (PCA/dense layer). Documentado en código y este design. |
| **Interferencia con el harness**: dos loaders singleton en módulos distintos cargan el mismo WASM. | `harnessEngineLoader` y `enrollmentEngineLoader` son módulos independientes. Si ambas rutas están activas simultáneamente (admin y perfil abiertos en dos tabs del mismo origin), comparten el módulo WASM del runtime de MediaPipe — esto es comportamiento normal del browser (módulo JS singleton por origin). No hay conflicto de instancias porque el motor es stateful y cada loader mantiene su propia instancia. |
| **Threshold de detección demasiado estricto/laxo**: un umbral incorrecto hace que el reto no se detecte o se dispare en falso. | Los umbrales de D-2 son calibrados para condiciones normales (buena iluminación, cara centrada). Se documentan como constantes exportadas para ajuste sin re-deploy. El fallback manual sirve como válvula de escape para test. |

---

## Migration Plan

Este change es aditivo-funcional: no cambia contratos ni rutas de API. No requiere migración de datos ni de backend.

1. Crear `enrollmentEngineLoader.ts` (patrón de `harnessEngineLoader.ts`).
2. Refactorizar `EnrollmentBiometricStep.tsx`: agregar loop RAF, evaluador de retos, fullscreen.
3. Agregar constantes de detección en un módulo `enrollmentChallengeDetector.ts` (o inline en el step).
4. Verificar con `tsc --noEmit` (cero errores).
5. Testear manualmente en desktop (Chrome) y en móvil (Chrome Android / iOS Safari fallback).

Rollback: si el motor no carga, el fallback manual garantiza que el enrollment sigue funcionando. No hay cambios de backend que revertir.

---

## Open Questions

- **OQ-1**: ¿El backend de producción (C-09) espera el embedding en 128 dims o puede aceptar el vector raw de 1404? → No bloquea este change (mock API acepta cualquier longitud); es una decisión de C-09.
- **OQ-2**: ¿Agregar el `<video>` con `requestFullscreen` nativo en iOS como workaround? → Explorar en `/opsx:apply` si el fallback CSS es insuficiente para el tester en iOS.
- **OQ-3**: ¿El loader del enrollment debería reusar la instancia cacheada del harness si ya está inicializada? → No: ciclos de vida independientes. El harness puede estar activo o no; el enrollment no debe depender de eso.
