/**
 * enrollmentChallengeDetector — evaluador puro de retos de liveness para el
 * enrollment biometrico del perfil del alumno (C-34, D-2).
 *
 * Logica PURA: sin DOM, sin estado, sin efectos secundarios. Recibe los datos
 * de un frame (landmarks, gaze, bbox) y retorna si el frame actual cumple el
 * threshold del reto. La acumulacion de frames consecutivos es responsabilidad
 * del componente (Map<ActiveChallenge, number>).
 *
 * C-54: agrega evaluacion por delta relativo al baseline neutral del alumno,
 * reto girar_cabeza direccional, y funciones de validacion de baseline.
 *
 * Umbrales exportados como constantes para ajuste sin re-deploy (D-2 — Risks).
 * Los indices de landmarks corresponden al FaceLandmarker de @mediapipe/tasks-vision
 * (468 landmarks de Face Mesh; iris en 468+).
 *
 * D-2 — Tabla de mapeo reto → metrica (legacy):
 * ┌──────────────────┬────────────────────────────────────────────────┬───────────┐
 * │ Reto             │ Metrica (eje X invertido por espejo selfie)    │ Frames    │
 * ├──────────────────┼────────────────────────────────────────────────┼───────────┤
 * │ girar_izquierda  │ gaze.x > +0.18  (coherente con el ovalo espejado)│ 2      │
 * │ girar_derecha    │ gaze.x < -0.18  (coherente con el ovalo espejado)│ 2      │
 * │ parpadear        │ |lm[159].y - lm[145].y| < 0.018               │ 1         │
 * │ acercarse        │ bbox.width > 0.48 (normalizado al frame)       │ 2         │
 * │ sonreir          │ |lm[291].x - lm[61].x| > 0.10 (normalizado)   │ 2         │
 * └──────────────────┴────────────────────────────────────────────────┴───────────┘
 *
 * C-54 — Tabla de mapeo reto → metrica RELATIVA:
 * ┌──────────────────┬────────────────────────────────────────────────────────────┐
 * │ Reto             │ Condicion (relativa al baseline neutral del alumno)        │
 * ├──────────────────┼────────────────────────────────────────────────────────────┤
 * │ parpadear        │ openness < baseline.blinkOpenness * 0.45                   │
 * │ girar_cabeza     │ izquierda: gaze.x > +0.22 | derecha: gaze.x < -0.22       │
 * │ sonreir          │ smileWidth > baseline.smileWidth * 1.25                    │
 * └──────────────────┴────────────────────────────────────────────────────────────┘
 *
 * Indices de landmarks usados:
 * - Ojo izquierdo superior: 159, inferior: 145 (apertura vertical — parpadeo).
 * - Comisura boca izquierda: 61, derecha: 291 (ancho de boca — sonrisa).
 * - Nariz (centroide): 1 (varianza para estabilidad del baseline).
 * - Gaze: via gazeFromIris() con iris izquierdo; ya calculado por el motor.
 */

import type { FaceLandmark } from "./VisionEngine";
import type { ActiveChallenge, BaselineMetrics, SequentialChallenge, TurnDirection } from "./liveness";

// ---------------------------------------------------------------------------
// Constantes de threshold legacy (C-34) — exportadas para compatibilidad
// ---------------------------------------------------------------------------

/**
 * Desplazamiento minimo del iris respecto al centro del ojo para detectar giro.
 * @deprecated Usar GAZE_TURN_THRESHOLD_ADJUSTED para el flujo secuencial (C-54).
 */
export const GAZE_TURN_THRESHOLD = 0.18;

/**
 * Apertura maxima del ojo para considerar que el ojo esta cerrado (parpadeo).
 * @deprecated Usar evaluateChallengeRelative() con baseline (C-54).
 */
export const BLINK_CLOSE_THRESHOLD = 0.018;

/**
 * Ancho minimo del bounding box del rostro para considerar que el alumno se acerco.
 * @deprecated El reto "acercarse" se elimino del catalogo secuencial (C-54).
 */
export const FACE_APPROACH_THRESHOLD = 0.48;

/**
 * Ancho minimo de la boca (distancia horizontal entre comisuras) para sonrisa.
 * @deprecated Usar evaluateChallengeRelative() con baseline (C-54).
 */
export const SMILE_WIDTH_THRESHOLD = 0.10;

// Frames consecutivos minimos para confirmar cada reto (legacy).
export const FRAMES_MIN_TURN = 2;
export const FRAMES_MIN_BLINK = 1;
export const FRAMES_MIN_APPROACH = 2;
export const FRAMES_MIN_SMILE = 2;

// ---------------------------------------------------------------------------
// C-54: Constantes de evaluacion relativa (Task 2.1, 2.2)
// ---------------------------------------------------------------------------

/**
 * Factor relativo para parpadeo: el ojo debe cerrarse al menos al 45 % de
 * su apertura en reposo (baseline.blinkOpenness).
 */
export const BLINK_RELATIVE_FACTOR = 0.45;

/**
 * Factor relativo para sonrisa: la boca debe abrirse al menos un 25 % mas
 * que en reposo (baseline.smileWidth).
 */
export const SMILE_RELATIVE_FACTOR = 1.25;

/**
 * Umbral absoluto ajustado para detectar giro de cabeza (C-54).
 * Subido de 0.18 -> 0.22 para mayor robustez contra ruido de iris.
 * El giro ya es relativo a la posicion del iris (no usa baseline).
 */
export const GAZE_TURN_THRESHOLD_ADJUSTED = 0.22;

/** Frames minimos consecutivos para confirmar parpadeo (C-54). */
export const FRAMES_MIN_BLINK_SEQ = 3;

/** Frames minimos consecutivos para confirmar giro de cabeza (C-54). */
export const FRAMES_MIN_TURN_SEQ = 4;

/** Frames minimos consecutivos para confirmar sonrisa (C-54). */
export const FRAMES_MIN_SMILE_SEQ = 4;

/** Umbral maximo de smileWidth en el baseline para considerarlo valido. */
const BASELINE_SMILE_MAX = 0.14;

// ---------------------------------------------------------------------------
// C-54: Funciones nuevas — evaluacion relativa al baseline (Task 2.3, 2.4)
// ---------------------------------------------------------------------------

/**
 * Evalua si el frame actual cumple el threshold RELATIVO del reto secuencial dado.
 *
 * Para el reto `girar_cabeza`, usa un umbral absoluto ajustado (el giro es
 * relativo al iris, que ya es una medida relativa al ojo — no usa baseline).
 * Para `parpadear` y `sonreír`, evalua el CAMBIO relativo al baseline neutral.
 *
 * Retorna `false` si:
 * - No hay baseline disponible (null) y el reto lo requiere.
 * - No hay suficientes landmarks.
 * - No hay turnDirection para girar_cabeza.
 *
 * SIN logica de acumulacion — eso es responsabilidad del componente.
 *
 * @param challenge     - Reto secuencial a evaluar.
 * @param landmarks     - Array de 468+ landmarks del FaceLandmarker.
 * @param gaze          - Direccion de mirada normalizada (-1..1).
 * @param baseline      - Metricas del baseline neutral del alumno, o null.
 * @param turnDirection - Direccion de giro elegida al azar (para girar_cabeza).
 */
export function evaluateChallengeRelative(
  challenge: SequentialChallenge,
  landmarks: FaceLandmark[],
  gaze: { x: number; y: number },
  baseline: BaselineMetrics | null,
  turnDirection?: TurnDirection,
): boolean {
  switch (challenge) {
    // parpadear — openness < baseline.blinkOpenness * BLINK_RELATIVE_FACTOR
    case "parpadear": {
      if (!baseline) return false;
      if (landmarks.length < 160) return false;
      const upper = landmarks[159];
      const lower = landmarks[145];
      const openness = Math.abs(upper.y - lower.y);
      return openness < baseline.blinkOpenness * BLINK_RELATIVE_FACTOR;
    }

    // girar_cabeza — DIRECCIONAL: izquierda -> gaze.x > +threshold | derecha -> gaze.x < -threshold
    // Convencion de espejo selfie (coherente con girar_izquierda/girar_derecha legacy):
    // El <video> esta espejado (CSS scaleX(-1)), pero los landmarks vienen del frame REAL.
    // Cuando el alumno gira hacia SU izquierda (lo que ve en el espejo), gaze.x > 0 en raw.
    case "girar_cabeza": {
      if (!turnDirection) return false;
      if (turnDirection === "izquierda") {
        return gaze.x > GAZE_TURN_THRESHOLD_ADJUSTED;
      } else {
        return gaze.x < -GAZE_TURN_THRESHOLD_ADJUSTED;
      }
    }

    // sonreír — smileWidth > baseline.smileWidth * SMILE_RELATIVE_FACTOR
    case "sonreír": {
      if (!baseline) return false;
      if (landmarks.length < 292) return false;
      const left  = landmarks[61];
      const right = landmarks[291];
      const width = Math.abs(right.x - left.x);
      return width > baseline.smileWidth * SMILE_RELATIVE_FACTOR;
    }

    default:
      return false;
  }
}

/**
 * Retorna el numero minimo de frames consecutivos requeridos para confirmar
 * el reto secuencial dado (C-54, D-6).
 */
export function framesMinForChallengeSeq(challenge: SequentialChallenge): number {
  switch (challenge) {
    case "parpadear":    return FRAMES_MIN_BLINK_SEQ;
    case "girar_cabeza": return FRAMES_MIN_TURN_SEQ;
    case "sonreír":      return FRAMES_MIN_SMILE_SEQ;
    default:             return FRAMES_MIN_TURN_SEQ;
  }
}

// ---------------------------------------------------------------------------
// C-54: Funciones puras de validacion del baseline (Task 11.5)
// ---------------------------------------------------------------------------

/** Frame acumulado durante la fase baseline. */
export interface BaselineFrame {
  blinkOpenness: number;
  smileWidth: number;
  gazeX: number;
}

/**
 * Valida que el smileWidth del baseline no supere el maximo permitido.
 * Si el alumno ya estaba sonriendo al capturar el baseline, el threshold
 * de sonrisa sera incorrecto.
 *
 * @param smileWidth - Ancho de boca promedio en el baseline.
 * @returns true si el smileWidth es valido (alumno no estaba sonriendo).
 */
export function isBaselineSmileValid(smileWidth: number): boolean {
  return smileWidth < BASELINE_SMILE_MAX;
}

/**
 * Calcula el BaselineMetrics a partir del acumulador de frames del baseline.
 * Retorna null si:
 * - El acumulador tiene menos de 12 frames (insuficientes para declarar baseline estable).
 * - El smileWidth promedio supera BASELINE_SMILE_MAX (alumno sonreia en reposo).
 *
 * @param accumulator - Frames acumulados durante la fase baseline.
 * @returns BaselineMetrics | null
 */
export function computeBaselineFromAccumulator(accumulator: BaselineFrame[]): BaselineMetrics | null {
  if (accumulator.length < 12) return null;

  const n = accumulator.length;
  const blinkOpenness = accumulator.reduce((s, f) => s + f.blinkOpenness, 0) / n;
  const smileWidth    = accumulator.reduce((s, f) => s + f.smileWidth, 0) / n;
  const gazeX         = accumulator.reduce((s, f) => s + f.gazeX, 0) / n;

  // Validar que el alumno no estaba sonriendo al baseline
  if (!isBaselineSmileValid(smileWidth)) return null;

  return { blinkOpenness, smileWidth, gazeX };
}

// ---------------------------------------------------------------------------
// C-54: Fisher-Yates shuffle (Task 11.6)
// ---------------------------------------------------------------------------

/**
 * Baraja un array usando el algoritmo Fisher-Yates (C-54, D-4).
 * `Math.random()` es aceptable en este contexto client-side de liveness.
 * La funcion muta el array recibido (para eficiencia) y lo retorna.
 *
 * @param arr - Array a barajar (se muta in-place).
 * @returns El mismo array barajado.
 */
export function fisherYatesShuffle<T>(arr: T[]): T[] {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    const tmp = arr[i];
    arr[i] = arr[j];
    arr[j] = tmp;
  }
  return arr;
}

// ---------------------------------------------------------------------------
// C-65: Confirmación de gesto por tiempo sostenido (biometric-gesture-hold-timing)
// ---------------------------------------------------------------------------

/**
 * Milisegundos que el alumno debe sostener el gesto para que el reto se confirme.
 * Constante exportada y ajustable sin re-deploy (design D2).
 * Default ~500 ms — independiente del framerate (D2).
 */
export const GESTURE_HOLD_MS = 500;

/**
 * Input del helper puro de hold temporal.
 */
export interface GestureHoldInput {
  /** Timestamp monótono actual (performance.now()). */
  now: number;
  /** Timestamp del primer frame en que el alumno cumplió el gesto, o null si no empezó. */
  holdStart: number | null;
  /** ¿El frame actual cumple la condición del reto? */
  cumple: boolean;
}

/**
 * Output del helper de hold.
 */
export interface GestureHoldOutput {
  /** Nuevo holdStart: null si se reinició, valor original si sigue, now si acaba de iniciar. */
  holdStart: number | null;
  /** true si el gesto se sostuvo >= GESTURE_HOLD_MS. */
  confirmado: boolean;
}

/**
 * Helper PURO de confirmación temporal: gestiona el hold del gesto activo.
 *
 * - Si `cumple` es false: resetea holdStart a null (interrupción del gesto).
 * - Si `cumple` es true y holdStart es null: inicia el hold (holdStart = now).
 * - Si `cumple` es true y holdStart tiene valor: evalúa si elapsed >= GESTURE_HOLD_MS.
 *
 * SIN efectos secundarios. El componente es el responsable de la integración.
 */
export function gestureHold({ now, holdStart, cumple }: GestureHoldInput): GestureHoldOutput {
  if (!cumple) {
    return { holdStart: null, confirmado: false };
  }

  if (holdStart === null) {
    // Primera vez que cumple: iniciar el hold
    return { holdStart: now, confirmado: false };
  }

  const elapsed = now - holdStart;
  if (elapsed >= GESTURE_HOLD_MS) {
    return { holdStart, confirmado: true };
  }

  return { holdStart, confirmado: false };
}

// ---------------------------------------------------------------------------
// API legacy (C-34) — mantenida para compatibilidad hacia atras (Task 2.5)
// ---------------------------------------------------------------------------

/**
 * Devuelve el numero minimo de frames consecutivos requeridos para el reto dado.
 * @deprecated Usar framesMinForChallengeSeq() para el flujo secuencial (C-54).
 */
export function framesMinForChallenge(challenge: ActiveChallenge): number {
  switch (challenge) {
    case "parpadear":    return FRAMES_MIN_BLINK;
    case "acercarse":   return FRAMES_MIN_APPROACH;
    case "sonreir":     return FRAMES_MIN_SMILE;
    case "girar_izquierda":
    case "girar_derecha":
    default:            return FRAMES_MIN_TURN;
  }
}

/**
 * Evalua si el frame actual cumple el threshold del reto dado (evaluacion ABSOLUTA).
 *
 * Retorna `true` si el frame cumple la condicion; `false` si no la cumple o
 * si faltan datos (landmarks insuficientes, bbox null para `acercarse`).
 *
 * SIN logica de acumulacion — eso es responsabilidad del componente.
 *
 * @deprecated Usar evaluateChallengeRelative() con baseline para el flujo secuencial (C-54).
 */
export function evaluateChallenge(
  challenge: ActiveChallenge,
  landmarks: FaceLandmark[],
  gaze: { x: number; y: number },
  bbox: { width: number } | null,
): boolean {
  switch (challenge) {
    // girar_izquierda / girar_derecha — coherencia con el ESPEJO.
    //
    // El <video> se muestra espejado (CSS `transform: scaleX(-1)`, vista selfie),
    // pero los landmarks de MediaPipe vienen del frame REAL (sin espejar): en el
    // frame crudo, cuando el usuario gira hacia SU izquierda, sus rasgos se
    // desplazan hacia la DERECHA de la imagen -> gaze.x > 0. El usuario, en cambio,
    // ve el ovalo espejado (como un espejo real), asi que el label "Girar a la
    // izquierda" debe matchear el movimiento que el PERCIBE. Para que el reto sea
    // coherente con lo que ve en pantalla, invertimos el eje X respecto del frame
    // crudo: "izquierda" (lo que el usuario percibe) => gaze.x > +threshold en crudo.
    case "girar_izquierda":
      return gaze.x > GAZE_TURN_THRESHOLD;

    case "girar_derecha":
      return gaze.x < -GAZE_TURN_THRESHOLD;

    // parpadear — ojo cerrado (landmark superior e inferior del ojo izquierdo)
    case "parpadear": {
      if (landmarks.length < 160) return false;
      const upper = landmarks[159];
      const lower = landmarks[145];
      const openness = Math.abs(upper.y - lower.y);
      return openness < BLINK_CLOSE_THRESHOLD;
    }

    // acercarse — bounding box suficientemente ancho
    case "acercarse":
      return bbox !== null && bbox.width > FACE_APPROACH_THRESHOLD;

    // sonreir — comisuras de boca separadas horizontalmente
    case "sonreir": {
      if (landmarks.length < 292) return false;
      const left  = landmarks[61];
      const right = landmarks[291];
      const width = Math.abs(right.x - left.x);
      return width > SMILE_WIDTH_THRESHOLD;
    }

    default:
      return false;
  }
}
