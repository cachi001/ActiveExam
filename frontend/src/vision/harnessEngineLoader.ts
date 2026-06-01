/**
 * harnessEngineLoader — cargador lazy del motor real MediaPipe (C-30, D-2).
 *
 * Exporta `loadRealEngine()` que carga `RealMediaPipeVisionEngine` con dynamic
 * import, garantizando que @mediapipe/tasks-vision quede en un chunk separado
 * del bundle inicial de Vite (RD-8, bundle < 500 KB).
 *
 * C-32: cache singleton a nivel módulo. Una vez inicializado, `loadRealEngine()`
 * devuelve la instancia cacheada sin llamar `init()` de nuevo. El motor WASM se
 * descarga y compila UNA sola vez por sesión de página. `disposeRealEngine()`
 * libera el cache explícitamente (useEffect cleanup al desmontar el harness).
 *
 * Solo debe ser invocado desde la ruta del harness admin (/admin/detection-test).
 * El resto del código de producción usa MediaPipeVisionEngine (stub).
 *
 * Fallback honesto (D-6): si init() falla, la promesa se rechaza con el error
 * original. NUNCA swallow, NUNCA fallback silencioso a simulación.
 */

import type { VisionEngine } from "./VisionEngine";

// C-32 (Task 1.1): variables privadas de módulo para el singleton.
// _cachedEngine: instancia ya inicializada lista para usar.
// _initPromise: promesa en vuelo durante la primera carga (evita doble init si
//   dos llamadas concurrentes llegan antes de que la primera resuelva).
let _cachedEngine: VisionEngine | null = null;
let _initPromise: Promise<VisionEngine> | null = null;

/**
 * Carga dinámicamente RealMediaPipeVisionEngine, lo instancia y llama init().
 * Devuelve una instancia lista para procesar frames.
 *
 * C-32 — Flujo con cache:
 * 1. Si `_cachedEngine !== null` → devuelve la instancia cacheada (sin re-init).
 * 2. Si `_initPromise !== null` → espera la promesa en vuelo (evita doble init).
 * 3. Si ambos son null → inicia la carga, asigna `_initPromise`, ejecuta init().
 * 4. Si init() falla → limpia `_initPromise` (no `_cachedEngine`); propaga error.
 *
 * Si init() falla (WebGL ausente, modelo no encontrado, timeout), la promesa
 * se rechaza con el error original para que el harness pueda mostrarlo en la UI.
 */
export async function loadRealEngine(): Promise<VisionEngine> {
  // C-32 Task 1.2 — paso 1: devolver instancia ya cacheada
  if (_cachedEngine !== null) {
    return _cachedEngine;
  }

  // C-32 Task 1.2 — paso 2: esperar promesa en vuelo para evitar doble init
  if (_initPromise !== null) {
    return _initPromise;
  }

  // C-32 Task 1.2 — paso 3: iniciar nueva carga
  _initPromise = (async () => {
    try {
      // Dynamic import — Vite emitirá un chunk separado para este módulo
      // y NO incluirá @mediapipe/tasks-vision en el bundle inicial.
      const { RealMediaPipeVisionEngine } = await import("./RealMediaPipeVisionEngine");

      const engine = new RealMediaPipeVisionEngine();

      // init() puede lanzar si:
      // - WebGL no disponible
      // - modelo .task no encontrado (404)
      // - error de red al cargar el WASM
      // No capturamos — la promesa se rechaza con el error original (D-6).
      await engine.init();

      // Éxito: guardar en cache
      _cachedEngine = engine;

      // C-32 Task 1.3: limpiar _initPromise al resolver para no bloquear futuras llamadas
      _initPromise = null;

      return engine;
    } catch (err) {
      // C-32 Task 1.3 + 1.4: limpiar _initPromise en fallo; NO asignar _cachedEngine;
      // propagar el error original sin cambios (comportamiento D-6 conservado).
      _initPromise = null;
      throw err;
    }
  })();

  return _initPromise;
}

/**
 * C-32 Task 1.5: libera el motor cacheado explícitamente.
 *
 * Llama `dispose()` sobre la instancia cacheada (si existe), pone ambas
 * variables de módulo en `null`, y resuelve sin lanzar si no hay cache.
 * Diseñado para ser llamado en el `useEffect` cleanup del componente
 * (desmontaje del harness) o ante un error irrecuperable.
 */
export async function disposeRealEngine(): Promise<void> {
  // Cancelar cualquier promesa en vuelo (el resultado se descartará)
  _initPromise = null;

  if (_cachedEngine !== null) {
    await _cachedEngine.dispose().catch(() => {
      // dispose no debe hacer lanzar al caller; error silenciado intencionalmente
    });
    _cachedEngine = null;
  }
}
