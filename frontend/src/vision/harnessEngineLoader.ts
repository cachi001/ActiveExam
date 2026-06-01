/**
 * harnessEngineLoader — cargador lazy del motor real MediaPipe (C-30, D-2).
 *
 * Exporta `loadRealEngine()` que carga `RealMediaPipeVisionEngine` con dynamic
 * import, garantizando que @mediapipe/tasks-vision quede en un chunk separado
 * del bundle inicial de Vite (RD-8, bundle < 500 KB).
 *
 * Solo debe ser invocado desde la ruta del harness admin (/admin/detection-test).
 * El resto del código de producción usa MediaPipeVisionEngine (stub).
 *
 * Fallback honesto (D-6): si init() falla, la promesa se rechaza con el error
 * original. NUNCA swallow, NUNCA fallback silencioso a simulación.
 */

import type { VisionEngine } from "./VisionEngine";

/**
 * Carga dinámicamente RealMediaPipeVisionEngine, lo instancia y llama init().
 * Devuelve una instancia lista para procesar frames.
 *
 * Si init() falla (WebGL ausente, modelo no encontrado, timeout), la promesa
 * se rechaza con el error original para que el harness pueda mostrarlo en la UI.
 */
export async function loadRealEngine(): Promise<VisionEngine> {
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

  return engine;
}
