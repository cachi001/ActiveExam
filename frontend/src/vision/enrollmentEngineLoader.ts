/**
 * enrollmentEngineLoader — cargador lazy del motor real MediaPipe para el
 * enrollment biométrico del perfil del alumno (C-34, D-1).
 *
 * Mismo patrón singleton que `harnessEngineLoader.ts` (C-30/C-32), pero con
 * variables de módulo SEPARADAS para un ciclo de vida INDEPENDIENTE. El harness
 * admin y el enrollment pueden coexistir sin interferir entre sí: el harness se
 * monta en /admin/detection-test; el enrollment en /perfil. Cada loader mantiene
 * su propia instancia.
 *
 * D-1: NO se importa desde `harnessEngineLoader.ts` ni se generaliza ese módulo.
 * Razón: evitar cascada de cambios en specs de C-30/C-32; ciclos de vida
 * independientes; alineación con la restricción de no tocar el harness.
 *
 * Garantía de bundle: `await import('./RealMediaPipeVisionEngine')` hace que
 * Vite emita @mediapipe/tasks-vision en un chunk lazy separado, NUNCA en el
 * bundle inicial (< 500 KB, RD-8).
 *
 * Fallback honesto: si init() falla (WebGL ausente, 404 del modelo), la
 * promesa se rechaza con el error original. NUNCA swallow silencioso.
 * El componente muestra el error y ofrece modo de resolución manual.
 */

import type { VisionEngine } from "./VisionEngine";

// C-34 Task 1.1: variables privadas de módulo separadas del harness.
// _cachedEnrollmentEngine: instancia ya inicializada, lista para usar.
// _enrollmentInitPromise: promesa en vuelo durante la primera carga (evita
//   doble init si dos llamadas concurrentes llegan antes de que la primera
//   resuelva).
let _cachedEnrollmentEngine: VisionEngine | null = null;
let _enrollmentInitPromise: Promise<VisionEngine> | null = null;

/**
 * C-34 Task 1.2: carga dinámicamente RealMediaPipeVisionEngine, lo instancia
 * y llama init(). Devuelve la instancia lista para procesar frames.
 *
 * Flujo con cache (tres pasos):
 * 1. Cache hit  → devuelve `_cachedEnrollmentEngine` (sin re-init).
 * 2. En vuelo   → espera `_enrollmentInitPromise` (evita doble init).
 * 3. Nueva carga → inicia la carga, asigna `_enrollmentInitPromise`, ejecuta init().
 * 4. Si falla   → limpia `_enrollmentInitPromise`; NO asigna `_cachedEnrollmentEngine`.
 *
 * C-34 Task 1.5: el dynamic import es `await import('./RealMediaPipeVisionEngine')`
 * (sin import estático) para que Vite emita chunk separado.
 */
export async function loadEnrollmentEngine(): Promise<VisionEngine> {
  // Task 1.2 — paso 1: devolver instancia ya cacheada
  if (_cachedEnrollmentEngine !== null) {
    return _cachedEnrollmentEngine;
  }

  // Task 1.2 — paso 2: esperar promesa en vuelo para evitar doble init
  if (_enrollmentInitPromise !== null) {
    return _enrollmentInitPromise;
  }

  // Task 1.2 — paso 3: iniciar nueva carga
  _enrollmentInitPromise = (async () => {
    try {
      // C-34 Task 1.5: Dynamic import — Vite emitirá un chunk separado.
      // @mediapipe/tasks-vision NO entra en el bundle inicial (RD-8).
      const { RealMediaPipeVisionEngine } = await import("./RealMediaPipeVisionEngine");

      const engine = new RealMediaPipeVisionEngine();

      // init() puede lanzar si WebGL no está disponible, el modelo .task
      // no se encuentra (404) o hay error de red al cargar el WASM.
      // No capturamos — la promesa se rechaza con el error original.
      await engine.init();

      // Éxito: guardar en cache
      _cachedEnrollmentEngine = engine;

      // Limpiar _enrollmentInitPromise al resolver para no bloquear futuras
      // llamadas (ver C-32 Task 1.3 en harnessEngineLoader como referencia).
      _enrollmentInitPromise = null;

      return engine;
    } catch (err) {
      // C-34 Task 1.3: limpiar _enrollmentInitPromise en fallo;
      // NO asignar _cachedEnrollmentEngine; propagar el error original.
      _enrollmentInitPromise = null;
      throw err;
    }
  })();

  return _enrollmentInitPromise;
}

/**
 * C-34 Task 1.4: libera el motor de enrollment cacheado explícitamente.
 *
 * Llama `dispose()` sobre la instancia cacheada (si existe), pone ambas
 * variables de módulo en `null`, y resuelve sin lanzar si no hay cache.
 * Diseñado para ser llamado en el `useEffect` cleanup del componente
 * (desmontaje de EnrollmentBiometricStep) o ante un error irrecuperable.
 *
 * Error en dispose silenciado intencionalmente: no debe hacer lanzar al caller.
 */
export async function disposeEnrollmentEngine(): Promise<void> {
  // Cancelar cualquier promesa en vuelo (el resultado se descartará)
  _enrollmentInitPromise = null;

  if (_cachedEnrollmentEngine !== null) {
    await _cachedEnrollmentEngine.dispose().catch(() => {
      // dispose no debe hacer lanzar al caller; error silenciado intencionalmente
    });
    _cachedEnrollmentEngine = null;
  }
}
