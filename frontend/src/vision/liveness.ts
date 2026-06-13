/**
 * Liveness hibrido del cliente: pasivo + retos activos aleatorios (C-09, DD-18).
 *
 * Logica PURA (sin DOM ni MediaPipe) para que sea testeable y reusable. El motor
 * de vision provee los landmarks/senales; aqui se decide el gate de liveness y se
 * eligen los retos activos AL AZAR (RN-BIO-05). Es la primera capa de defensa; el
 * backend RE-INFIERE sobre el clip y decide la habilitacion (RN-GLB-01).
 *
 * Espeja el dominio del backend (``app.domain.biometrics.liveness``): mismos retos
 * y mismo criterio de exito, para que la re-inferencia server-side sea coherente.
 *
 * C-54: agrega motor de retos secuenciales (baseline neutral + evaluacion relativa).
 */

import type { FrameResult, PassiveSignals } from "./VisionEngine";

// ---------------------------------------------------------------------------
// C-54: Catalogo secuencial de retos (Task 1.1, 1.4, 1.2, 1.3)
// ---------------------------------------------------------------------------

/**
 * Catalogo de retos secuenciales de liveness (C-54, D-4).
 * Excluye "acercarse" (falsos positivos, no estandar ISO/IEC 30107-3).
 * El orden se baraja con Fisher-Yates al iniciar cada intento.
 */
export const SEQUENTIAL_CHALLENGES = [
  "parpadear",
  "girar_cabeza",
  "sonreír",
] as const;

/** Tipo derivado del catalogo secuencial. */
export type SequentialChallenge = (typeof SEQUENTIAL_CHALLENGES)[number];

/**
 * Direccion de giro para el reto `girar_cabeza` (D-4).
 * Se elige al azar al montar el componente y permanece fija durante el intento.
 * Convencion de espejo selfie (coherente con enrollmentChallengeDetector.ts):
 * - 'izquierda' -> gaze.x > +threshold (lo que el alumno percibe como su izquierda)
 * - 'derecha'   -> gaze.x < -threshold (lo que el alumno percibe como su derecha)
 */
export type TurnDirection = "izquierda" | "derecha";

/**
 * Estado de la maquina de estados del motor de retos secuenciales (C-54, D-1).
 * - idle:      estado inicial antes de iniciar la captura
 * - baseline:  acumulando metricas neutrales del alumno (pre-retos)
 * - challenge: evaluando el reto activo (challengeIndex)
 * - cooldown:  confirmacion visual del paso completado (350 ms)
 * - done:      todos los retos completados
 */
export type ChallengeState = "idle" | "baseline" | "challenge" | "cooldown" | "done";

/**
 * Metricas neutrales del alumno capturadas durante la fase baseline (C-54, D-2).
 * Se usan como referencia para la evaluacion por delta relativo.
 *
 * @field blinkOpenness  Apertura vertical media del ojo izquierdo en reposo
 *                       (|lm[159].y - lm[145].y|). La evaluacion pide que
 *                       baje al 45 % de este valor para detectar parpadeo.
 * @field smileWidth     Ancho de boca medio en reposo (|lm[291].x - lm[61].x|).
 *                       La evaluacion pide que suba al 125 % para detectar sonrisa.
 * @field gazeX          Posicion horizontal media del iris en reposo (referencia
 *                       de frente). No se usa directamente en la evaluacion actual
 *                       (el giro usa umbral absoluto ajustado), pero se captura
 *                       para posible uso futuro.
 */
export interface BaselineMetrics {
  blinkOpenness: number;
  smileWidth: number;
  gazeX: number;
  /**
   * C-67: Posición Y promedio de las comisuras de la boca en reposo.
   * Landmarks 61 (izquierda) y 291 (derecha): avgCornerY = (lm[61].y + lm[291].y) / 2.
   * Cuando el alumno sonríe, las comisuras suben (y disminuye en coordenadas de imagen).
   * Usado por la métrica compuesta de sonrisa (elevación + ancho).
   * Opcional: undefined si el baseline se computó antes de C-67 (backward compatible).
   */
  smileCornerY?: number;
}

// ---------------------------------------------------------------------------
// Catalogo legacy (C-09) — mantenido para compatibilidad hacia atras
// ---------------------------------------------------------------------------

/**
 * Retos activos del catalogo legacy (mismos valores que el backend).
 * @deprecated Usar SEQUENTIAL_CHALLENGES para el flujo de enrollment (C-54).
 */
export const ACTIVE_CHALLENGES = [
  "girar_izquierda",
  "girar_derecha",
  "parpadear",
  "acercarse",
  "sonreir",
] as const;

export type ActiveChallenge = (typeof ACTIVE_CHALLENGES)[number];

export const MIN_ACTIVE_CHALLENGES = 1;
export const MAX_ACTIVE_CHALLENGES = 2;

/**
 * Elige 1-2 retos activos AL AZAR (RN-BIO-05). ``rng`` inyectable para tests
 * deterministas (default ``Math.random``).
 * @deprecated Usar SEQUENTIAL_CHALLENGES + barajado Fisher-Yates en BiometricCapture (C-54).
 */
export function pickActiveChallenges(
  count = 2,
  rng: () => number = Math.random,
): ActiveChallenge[] {
  const n = Math.max(MIN_ACTIVE_CHALLENGES, Math.min(MAX_ACTIVE_CHALLENGES, count));
  const pool = [...ACTIVE_CHALLENGES];
  const chosen: ActiveChallenge[] = [];
  for (let i = 0; i < n && pool.length > 0; i += 1) {
    const idx = Math.floor(rng() * pool.length);
    chosen.push(pool.splice(idx, 1)[0]);
  }
  return chosen;
}

/**
 * Deriva las senales pasivas de liveness a partir de la secuencia de frames del
 * clip. Heuristica de cliente (no fuente de verdad):
 * - parpadeo: la apertura de ojos varia entre frames (no estatica como una foto).
 * - micro-movimientos: la posicion de los landmarks varia sutilmente.
 * - profundidad 3D coherente: el rango de ``z`` indica volumen (no un plano).
 *
 * ``blinkOpenness``/``motion``/``depthRange`` se calculan del motor; aqui se
 * aplican los umbrales del cliente. Una foto/video plano da varianza ~0 y z ~0.
 */
export function derivePassiveSignals(metrics: {
  blinkVariance: number;
  motionVariance: number;
  depthRange: number;
}): PassiveSignals {
  return {
    parpadeo_detectado: metrics.blinkVariance > 0.01,
    micro_movimientos: metrics.motionVariance > 0.0005,
    profundidad_3d_coherente: metrics.depthRange > 0.02,
  };
}

/** El pasivo pasa solo si las TRES senales son positivas (defensa estricta). */
export function passivePassed(signals: PassiveSignals): boolean {
  return (
    signals.parpadeo_detectado &&
    signals.micro_movimientos &&
    signals.profundidad_3d_coherente
  );
}

/**
 * Gate de liveness del cliente: pasivo OK + todos los retos resueltos + sin camara
 * virtual. Espeja ``liveness_exitoso`` del backend. NO es el veredicto final: el
 * backend re-infiere (RN-GLB-01).
 */
export function clientLivenessOk(args: {
  passive: PassiveSignals;
  requested: ActiveChallenge[];
  solved: ActiveChallenge[];
  virtualCameraDetected: boolean;
}): boolean {
  if (args.virtualCameraDetected) return false;
  if (!passivePassed(args.passive)) return false;
  const solved = new Set(args.solved);
  return args.requested.every((c) => solved.has(c));
}

/**
 * Heuristica de integridad para detectar CAMARA VIRTUAL / inyeccion de pipeline
 * (DD-18). Senales tipicas de un feed sintetico inyectado:
 * - varianza de pixeles anormalmente baja entre frames consecutivos (feed loop).
 * - ausencia total de micro-movimientos junto con face_count estable perfecto.
 * - frameRate sospechosamente constante (sin jitter de camara fisica).
 *
 * Es UNA capa, no el veredicto unico (DD-18): se REPORTA al backend.
 */
export function detectVirtualCamera(signals: {
  interFramePixelVariance: number;
  frameRateJitter: number;
  faceCountStability: number;
}): boolean {
  const feedLoopLike = signals.interFramePixelVariance < 1e-6;
  const noJitter = signals.frameRateJitter < 1e-6;
  const tooStable = signals.faceCountStability >= 0.999;
  return (feedLoopLike && tooStable) || (noJitter && tooStable);
}

/** Conteo de rostros agregado del clip: util para reportar multiples rostros. */
export function aggregateFaceCount(frames: FrameResult[]): number {
  if (frames.length === 0) return 0;
  return Math.max(...frames.map((f) => f.face_count));
}
