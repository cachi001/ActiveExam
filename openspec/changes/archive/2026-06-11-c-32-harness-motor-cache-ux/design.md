## Context

El harness de diagnóstico `/admin/detection-test` usa `loadRealEngine()` (C-30, `harnessEngineLoader.ts:29`) que en cada invocación crea una nueva instancia de `RealMediaPipeVisionEngine` y llama `init()`, lo cual recarga y compila los modelos WASM (~25–50 MB) desde cero. El flujo actual en `startHarness()` llama `loadRealEngine()` cada vez que el usuario presiona "Iniciar cámara", incluyendo al reiniciar después de un stop. El motor previo se hace `dispose()` en `stopHarness()` y `engineRef.current` queda en `null`, forzando una nueva carga completa en el próximo inicio.

Adicionalmente: (a) el banner de estado `'loading'` usa jerga técnica ("WASM", "MB", "MediaPipe") inapropiada para personal no técnico; (b) el panel de configuración de umbrales muestra claves de código puro (`face_absent_ms`, `gaze_deviation_threshold`, etc.) sin traducción al usuario; (c) la detección de monitores múltiples (`detectExtraMonitor`) no solicita el permiso `window-management` activamente — silencia el error y devuelve `null`, dejando la señal como "no determinable" incluso cuando el navegador sí soporta la API.

Stack relevante: React + Vite + Zustand + Tailwind (frontend puro). Sin backend involucrado. Componentes existentes: `<Term>` (C-28, `frontend/src/ui/Term.tsx`), `<Icon>`, `<Button>`, `<Card>`. Motor: `RealMediaPipeVisionEngine` (C-30), loader: `harnessEngineLoader.ts`.

## Goals / Non-Goals

**Goals:**
- El motor WASM se inicializa UNA sola vez por sesión de página; los ciclos "Iniciar → Detener → Iniciar" posteriores reutilizan la instancia ya lista.
- El estado de carga muestra un spinner visual + mensaje en lenguaje claro, sin términos técnicos.
- Los cinco umbrales configurables tienen nombres en español comprensible; la clave técnica queda como referencia secundaria.
- El harness ofrece un botón para solicitar el permiso `window-management` al usuario, con mensajería clara según el resultado.
- Sin cambios de backend, contratos de API, ni lógica de detección/scoring.

**Non-Goals:**
- Implementar cache del motor en el flujo de examen real (solo harness admin).
- Cambiar la semántica de detección o los umbrales por defecto.
- Reemplazar `<Term>` por otro componente de tooltip.
- Cachear el stream de video o el pipeline; solo el motor WASM.
- Persistir el cache entre recargas de página (solo memoria de módulo JS).

## Decisions

### D-1: Cache singleton a nivel módulo en `harnessEngineLoader.ts`

**Problema**: `startHarness()` llama `loadRealEngine()` → nueva instancia + `init()` en cada ciclo.

**Decisión**: Mantener dos variables privadas a nivel módulo en `harnessEngineLoader.ts`:
- `_cachedEngine: VisionEngine | null` — instancia lista para usar.
- `_initPromise: Promise<VisionEngine> | null` — promesa en vuelo durante la primera carga (evita race condition si dos llamadas concurrentes lo invocan antes de que el primero resuelva).

Flujo de `loadRealEngine()`:
1. Si `_cachedEngine !== null` → devolver directamente (sin re-import, sin `init()`).
2. Si `_initPromise !== null` → esperar la promesa ya en vuelo (evita doble init).
3. Si ambos son `null` → crear la promesa de carga, asignarla a `_initPromise`, ejecutar el import dinámico + `new RealMediaPipeVisionEngine()` + `init()`, asignar resultado a `_cachedEngine`, devolver.
4. Si `init()` falla → limpiar `_initPromise` (pero no `_cachedEngine`); propagar el error al llamador. El cache permanece vacío; una re-llamada futura reintentará.

`disposeRealEngine()`: llama `_cachedEngine.dispose()`, pone ambas variables en `null`. Diseñado para ser llamado en el `useEffect` cleanup del componente si el administrador navega fuera de la página, o ante un error irrecuperable que requiera reiniciar el motor.

**Alternativa descartada**: Cache en un `useRef` dentro de `AdminDetectionHarness`. Descartado porque el ref vive con el componente; si el componente se desmonta y remonta (navegación SPA), se perdería el cache. El nivel módulo sobrevive a remounts.

**Alternativa descartada**: Cache en Zustand store. Innecesario — el motor no es estado de UI, no necesita reactividad, y el store global no debe cargar dependencias de visión.

### D-2: `stopHarness()` llama `dispose()` solo bajo condición — estrategia "keep-alive"

**Problema**: El ciclo "Iniciar → Detener → Iniciar" hace `dispose()` en `stopHarness()` (línea 585), lo que invalida el cache.

**Decisión**: `stopHarness()` ya NO llama `engineRef.current.dispose()` directamente. En cambio, libera el stream de video y detiene el frame loop, pero mantiene el motor WASM vivo (en cache). El `engineRef.current` se limpia (→ `null`) pero el singleton del módulo permanece intacto. `disposeRealEngine()` se llamará solo al desmontar el componente (`useEffect` cleanup) y ante error de `load-error` irrecuperable donde el usuario elija "Reintentar".

**Riesgo aceptado**: GPU/WASM memory no se libera entre sesiones de diagnóstico dentro de la misma visita a la página. Para un tool de diagnóstico admin (uso poco frecuente, sesiones cortas), este trade-off es aceptable. El admin que navegue a otra página sí libera recursos via cleanup del componente.

### D-3: Spinner amigable para el estado `'loading'`

**Contexto**: El banner actual (línea ~699 de `AdminDetectionHarness.tsx`) muestra `"CARGANDO MOTOR MEDIAPIPE… Descargando modelos y compilando WASM (~25–50 MB, solo la primera vez)"`.

**Decisión**: Reemplazar por:
- Icono `<Icon name="progress_activity">` con clase `animate-spin` (patrón M3 existente en el codebase).
- Título: `"Preparando la cámara…"` (sin tecnicismos).
- Subtítulo (solo en la primera carga — detectable porque `_cachedEngine === null` antes de la llamada): `"Esto puede tardar unos segundos la primera vez."`. En recargas con cache ya listo, el estado `'loading'` dura milisegundos (no se notará, pero si se muestra, no confunde).

**Alternativa descartada**: Spinner propio con CSS animation. El `animate-spin` de Tailwind + `<Icon>` ya se usa en otros lugares del harness (hourglass_top actual); mantener consistencia.

### D-4: Labels en lenguaje claro para los cinco umbrales

**Mapeo de etiquetas**:

| Clave técnica | Nombre claro | Unidad visualizada |
|---|---|---|
| `face_absent_ms` | Segundos sin rostro para alertar | ms → se muestra en ms, hint dice "milisegundos" |
| `multiple_faces_frames` | Fotogramas con varios rostros | frames |
| `gaze_deviation_threshold` | Sensibilidad de mirada desviada | 0..1 |
| `gaze_sustained_ms` | Tiempo de mirada desviada para alertar | ms |
| `gaze_fixation_tolerance` | Tolerancia de fijación de mirada | 0..1 |

**Implementación**: El label principal del `<label>` mostrará el nombre claro. La clave técnica se agrega como texto secundario (tamaño pequeño, color `text-on-surface-variant`) o envuelta en `<Term>` si existe la entrada en el glosario (C-28). El hint de una línea sigue siendo el mismo, ajustado para no usar jerga.

**Decisión**: No agregar entradas nuevas al glosario para estas claves — son parámetros de configuración del harness, no terminología del dominio de proctoring. Solo texto secundario sin `<Term>`.

### D-5: Flujo de permiso Window Management en el harness

**Contexto**: `detectExtraMonitor` (C-25, líneas 163–174) recibe un `provider` inyectable. En el harness, si `window.getScreenDetails` no está disponible → `provider = undefined` → devuelve `null`. Si está disponible pero el usuario no dio permiso → la llamada lanza → `catch` devuelve `null`. En ambos casos la señal queda "no determinable".

**Decisión de API en `contextDetectors.ts`**:
Agregar función `requestAndDetectExtraMonitor(): Promise<ScreenPermissionResult>` que:
1. Detecta si `window.getScreenDetails` existe en el navegador.
2. Si no existe → devuelve `{ status: 'unsupported' }`.
3. Si existe → llama `window.getScreenDetails()` directamente (requiere gesto del usuario = click en botón).
4. Si el usuario deniega → `status: 'denied'`.
5. Si el usuario acepta → `status: 'granted', extra_monitor: boolean`.

```ts
export type ScreenPermissionResult =
  | { status: 'unsupported' }
  | { status: 'denied' }
  | { status: 'granted'; extra_monitor: boolean };
```

La función `detectExtraMonitor` existente (polling pasivo) permanece sin cambios para no romper el contrato de C-25.

**Decisión de UX en `AdminDetectionHarness.tsx`**:
- El panel de señales de entorno muestra una tarjeta para "Monitores adicionales".
- Estado inicial: si `getScreenDetails` no existe en el navegador → muestra mensaje "Tu navegador no soporta detección de pantallas (requiere Chrome o Edge sobre HTTPS)" con ícono info.
- Si existe pero aún no se pidió permiso → botón "Detectar pantallas" (icono `monitor`). Al hacer click llama `requestAndDetectExtraMonitor()` con gesto de usuario.
- Resultado `'denied'` → texto "Permiso denegado. Podés intentarlo de nuevo." + botón "Reintentar".
- Resultado `'granted'` → muestra `extra_monitor: true/false` como el resto de señales. El polling pasivo toma el relevo (el permiso ya fue concedido para esa sesión).
- El polling existente (`pollMonitor` en el `useEffect`) continúa como estaba para actualizar la señal durante la sesión una vez que el permiso fue concedido.

**Estado nuevo en el componente**: `monitorPermission: 'idle' | 'requesting' | 'granted' | 'denied' | 'unsupported'`, inicializado en `'idle'` (o `'unsupported'` si la API no existe, detectable en `startHarness`).

**Alternativa descartada**: Pedir el permiso automáticamente al iniciar el harness (sin gesto del usuario). Las APIs de `window-management` requieren gesto del usuario; sin él, el navegador lanza `SecurityError`. Además, pedir permisos sin que el usuario los entienda viola el espíritu de privacidad por diseño (KB 13).

## Risks / Trade-offs

- **[Risk] Motor cacheado puede quedar en estado corrupto si hubo un error parcial durante `init()`** → Mitigación: si `loadRealEngine()` falla, `_cachedEngine` permanece `null` y `_initPromise` se limpia; la siguiente llamada reintenta desde cero. No hay cache de un motor roto.
- **[Risk] Múltiples instancias del harness en la misma pestaña (edge case de tests)** → Mitigación: el harness es ruta protegida admin, una única instancia a la vez. El singleton es seguro.
- **[Risk] `disposeRealEngine()` llamado mientras `_initPromise` está en vuelo** → Mitigación: `disposeRealEngine()` también cancela `_initPromise` (pone a `null`). La promesa en vuelo continuará su ejecución en background pero el resultado se descartará ya que `_cachedEngine` quedó `null`.
- **[Risk] El usuario puede no entender por qué "Detectar pantallas" solicita permiso del navegador** → Mitigación: texto explicativo breve antes del botón ("Para detectar si hay más de un monitor conectado, el navegador necesita tu permiso.").
- **[Risk] `window-management` permission requiere HTTPS o localhost** → Mitigación: el harness es herramienta admin que corre sobre el mismo servidor que el resto del sistema (HTTPS ya requerido por KB 08). Si corre en HTTP → `getScreenDetails` no estará disponible → el flujo cae al caso `'unsupported'` con mensaje claro.

## Open Questions

- ¿Debe `disposeRealEngine()` llamarse al navegar fuera del harness (cleanup de ruta) o solo al recargar la página? La implementación propuesta lo llama en el cleanup del `useEffect`, que se ejecuta al desmontar el componente = al navegar fuera. Esto libera memoria GPU. ¿Es preferible mantener el motor vivo entre visitas al harness en la misma sesión de página? (Decisión diferida al implementador; el default propuesto es liberar al desmontar, ya que el harness es poco frecuente.)
