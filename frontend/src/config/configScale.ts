/**
 * configScale — capa de presentación para la Configuración del Sistema.
 *
 * Convierte BIDIRECCIONAL entre las unidades internas del backend (ms, 0–1, frames)
 * y las unidades amigables para el administrador (segundos, sensibilidad baja/media/alta,
 * número de detecciones). La conversión es PURA (sin efectos laterales, sin red).
 *
 * REGLA DURA (D6): la UI nunca envía la escala amigable al backend — convierte a
 * unidad interna ANTES del PATCH. Este módulo centraliza esa conversión.
 *
 * Escala de sensibilidad (gaze_deviation_threshold, gaze_fixation_tolerance):
 *   interna 0–1   → amigable "baja" / "media" / "alta"
 *   "baja"  = valor alto (0.35+): el motor tolera mucho → pocas alertas → sensibilidad BAJA
 *   "media" = valor medio (0.20–0.34)
 *   "alta"  = valor bajo (< 0.20): el motor se dispara fácil → sensibilidad ALTA
 *
 * Escala de tiempo (face_absent_ms, gaze_sustained_ms):
 *   ms → segundos (÷1000); segundos → ms (×1000, round).
 *
 * Escala de frames (multiple_faces_frames):
 *   interno = frames consecutivos; amigable = mismo número ("N detecciones seguidas").
 */

export type SensibilidadLabel = 'baja' | 'media' | 'alta';

// ---------------------------------------------------------------------------
// Thresholds de sensibilidad (umbrales de buckets)
// ---------------------------------------------------------------------------

// Para gaze_deviation_threshold (qué tan lejos puede mirar antes de "desviado"):
//   valor interno alto → tolera más → sensibilidad BAJA
//   valor interno bajo → se dispara fácil → sensibilidad ALTA
const GAZE_DEV_HIGH = 0.35;  // >= ALTA...no, ver abajo
const GAZE_DEV_LOW  = 0.20;  // <= baja/media límite

/**
 * Convierte gaze_deviation_threshold (0–1) a label amigable.
 * < 0.20 → "alta" (muy sensible)
 * 0.20 – 0.349 → "media"
 * >= 0.35 → "baja" (tolerante)
 */
export function gazeDeviationToLabel(value: number): SensibilidadLabel {
  if (value >= GAZE_DEV_HIGH) return 'baja';
  if (value >= GAZE_DEV_LOW)  return 'media';
  return 'alta';
}

/**
 * Convierte label amigable a gaze_deviation_threshold (valor representativo del bucket).
 */
export function labelToGazeDeviation(label: SensibilidadLabel): number {
  if (label === 'baja')  return 0.40;
  if (label === 'media') return 0.25;
  return 0.15; // alta
}

// Para gaze_fixation_tolerance (cuánto puede variar la mirada para considerarla "fija"):
//   valor alto → acepta más variación → sensibilidad BAJA (menos estricto para fijar)
//   valor bajo → exige más precisión → sensibilidad ALTA
const GAZE_TOL_HIGH = 0.30;
const GAZE_TOL_LOW  = 0.15;

/**
 * Convierte gaze_fixation_tolerance (0–1) a label amigable.
 * >= 0.30 → "baja" (tolerante — acepta variación)
 * 0.15 – 0.299 → "media"
 * < 0.15 → "alta" (exigente — poca variación)
 */
export function gazeFixationToLabel(value: number): SensibilidadLabel {
  if (value >= GAZE_TOL_HIGH) return 'baja';
  if (value >= GAZE_TOL_LOW)  return 'media';
  return 'alta';
}

/**
 * Convierte label amigable a gaze_fixation_tolerance.
 */
export function labelToGazeFixation(label: SensibilidadLabel): number {
  if (label === 'baja')  return 0.35;
  if (label === 'media') return 0.22;
  return 0.10; // alta
}

// ---------------------------------------------------------------------------
// Conversiones de tiempo (ms ↔ segundos)
// ---------------------------------------------------------------------------

/**
 * Convierte milisegundos a segundos (para mostrar en UI).
 * msToSeg(3000) → 3
 */
export function msToSeg(ms: number): number {
  return ms / 1000;
}

/**
 * Convierte segundos a milisegundos (para enviar al backend).
 * segToMs(3) → 3000
 */
export function segToMs(seg: number): number {
  return Math.round(seg * 1000);
}

// ---------------------------------------------------------------------------
// Frames (sin conversión — el número es intuitivo en contexto de UI)
// ---------------------------------------------------------------------------

/** Devuelve los frames tal cual (el label "N detecciones seguidas" es suficiente). */
export function framesToDisplay(frames: number): number {
  return frames;
}

// ---------------------------------------------------------------------------
// Conversión completa: ConfigEfectiva → campos de formulario amigables
// ---------------------------------------------------------------------------

/**
 * Campos que la UI de admin edita en formato amigable.
 * Nótese: el umbral_cola_revision (0–100) ya es intuitivo, no necesita conversión.
 */
export interface ConfigFriendly {
  /** Tiempo sin rostro para alertar, en segundos. */
  face_absent_seg: number;
  /** Detecciones consecutivas de múltiples rostros. Igual que los frames internos. */
  multiple_faces_display: number;
  /** Sensibilidad de mirada desviada (baja/media/alta). */
  gaze_deviation_label: SensibilidadLabel;
  /** Tiempo de mirada desviada para alertar, en segundos. */
  gaze_sustained_seg: number;
  /** Tolerancia de fijación de mirada (baja/media/alta). */
  gaze_fixation_label: SensibilidadLabel;
  /** Umbral de cola de revisión (0–100, ya intuitivo). */
  umbral_cola_revision: number;
  /** Retención de evidencia en días. */
  retencion_dias_default: number;
}

/**
 * Config interna (subset de ConfigEfectiva relevante para los umbrales de detección).
 */
export interface ConfigInternal {
  face_absent_ms: number;
  multiple_faces_frames: number;
  gaze_deviation_threshold: number;
  gaze_sustained_ms: number;
  gaze_fixation_tolerance: number;
  umbral_cola_revision: number;
  retencion_dias_default: number;
}

/**
 * Convierte la config interna del backend a valores amigables para la UI.
 */
export function toFriendly(cfg: ConfigInternal): ConfigFriendly {
  return {
    face_absent_seg: msToSeg(cfg.face_absent_ms),
    multiple_faces_display: framesToDisplay(cfg.multiple_faces_frames),
    gaze_deviation_label: gazeDeviationToLabel(cfg.gaze_deviation_threshold),
    gaze_sustained_seg: msToSeg(cfg.gaze_sustained_ms),
    gaze_fixation_label: gazeFixationToLabel(cfg.gaze_fixation_tolerance),
    umbral_cola_revision: cfg.umbral_cola_revision,
    retencion_dias_default: cfg.retencion_dias_default,
  };
}

/**
 * Convierte los valores amigables de la UI a la config interna del backend.
 * La UI NUNCA envía la escala amigable; convierte antes del PATCH.
 */
export function toInternal(friendly: ConfigFriendly): ConfigInternal {
  return {
    face_absent_ms: segToMs(friendly.face_absent_seg),
    multiple_faces_frames: friendly.multiple_faces_display,
    gaze_deviation_threshold: labelToGazeDeviation(friendly.gaze_deviation_label),
    gaze_sustained_ms: segToMs(friendly.gaze_sustained_seg),
    gaze_fixation_tolerance: labelToGazeFixation(friendly.gaze_fixation_label),
    umbral_cola_revision: friendly.umbral_cola_revision,
    retencion_dias_default: friendly.retencion_dias_default,
  };
}

// ---------------------------------------------------------------------------
// Labels de UI
// ---------------------------------------------------------------------------

export const SENSIBILIDAD_OPTIONS: { value: SensibilidadLabel; label: string; desc: string }[] = [
  { value: 'alta',  label: 'Alta',  desc: 'Más alertas — menor tolerancia' },
  { value: 'media', label: 'Media', desc: 'Balance recomendado (default)' },
  { value: 'baja',  label: 'Baja',  desc: 'Menos alertas — mayor tolerancia' },
];
