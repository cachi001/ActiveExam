/**
 * Degradacion graceful ante hardware insuficiente (C-11, RN-GLB-02, RN-GLB-03).
 *
 * El dispositivo del estudiante NO se controla. Ante capacidad de computo
 * insuficiente, el pipeline degrada EN ORDEN: primero baja Pose, luego Face Mesh;
 * solo si sigue siendo insuficiente ESCALA A UN PROCTOR. NUNCA aborta el examen de
 * forma silenciosa (penalizaria a quien tiene hardware modesto).
 *
 * Tambien ajusta los fps objetivo de los detectores segun la capacidad detectada al
 * inicio. Logica PURA: la capacidad entra como senal medida (fps efectivos), no se
 * lee del entorno.
 */

import type { DetectorKind } from "../vision/VisionEngine";

/** fps objetivo por detector (rangos del dominio, 11_ia_y_vision.md). */
export interface FpsTargets {
  face_detection: number;
  face_mesh: number;
  pose: number;
}

export const DEFAULT_FPS: FpsTargets = {
  face_detection: 8,
  face_mesh: 8,
  pose: 3,
};

/** Estado del pipeline tras evaluar la capacidad. */
export interface DegradationState {
  /** Detectores actualmente activos. */
  active: DetectorKind[];
  /** fps ajustados por detector activo. */
  fps: Partial<FpsTargets>;
  /** True si se escalo a un proctor (degradacion agotada). NUNCA implica abortar. */
  escalated_to_proctor: boolean;
  /** Nivel de degradacion aplicado (0 = ninguno, 1 = sin Pose, 2 = sin Face Mesh). */
  level: 0 | 1 | 2;
}

/**
 * Capacidad medida del dispositivo: cuantos detectores sostiene a sus fps minimos.
 * ``sustainable_detectors`` = numero de detectores que el hardware sostiene
 * (3 = todos, 2 = baja Pose, 1 = baja tambien Face Mesh, 0 = ni Face Detection).
 */
export interface Capacity {
  sustainable_detectors: 0 | 1 | 2 | 3;
  /** Factor de ajuste de fps (1.0 = pleno; <1 baja la frecuencia). */
  fps_scale?: number;
}

const ORDER_FROM_TOP: DetectorKind[] = ["face_detection", "face_mesh", "pose"];

/**
 * Calcula el estado de degradacion a partir de la capacidad medida. Escalonado:
 * 3 -> los tres; 2 -> baja Pose; 1 -> baja Pose y Face Mesh; 0 -> escala a proctor
 * (no quedan detectores utiles) SIN abortar.
 */
export function degrade(cap: Capacity, fps: FpsTargets = DEFAULT_FPS): DegradationState {
  const n = cap.sustainable_detectors;
  const scale = cap.fps_scale ?? 1;
  const active = ORDER_FROM_TOP.slice(0, n);
  const scaledFps: Partial<FpsTargets> = {};
  for (const d of active) scaledFps[d] = Math.max(1, Math.round(fps[d] * scale));

  let level: 0 | 1 | 2 = 0;
  if (n <= 1) level = 2;
  else if (n === 2) level = 1;

  return {
    active,
    fps: scaledFps,
    // Solo se escala a proctor cuando NO queda capacidad util (n === 0).
    escalated_to_proctor: n === 0,
    level,
  };
}
