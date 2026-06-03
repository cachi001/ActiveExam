/**
 * enrollmentChallengeDetector — evaluador puro de retos de liveness para el
 * enrollment biométrico del perfil del alumno (C-34, D-2).
 *
 * Lógica PURA: sin DOM, sin estado, sin efectos secundarios. Recibe los datos
 * de un frame (landmarks, gaze, bbox) y retorna si el frame actual cumple el
 * threshold del reto. La acumulación de frames consecutivos es responsabilidad
 * del componente (Map<ActiveChallenge, number>).
 *
 * Umbrales exportados como constantes para ajuste sin re-deploy (D-2 — Risks).
 * Los índices de landmarks corresponden al FaceLandmarker de @mediapipe/tasks-vision
 * (468 landmarks de Face Mesh; iris en 468+).
 *
 * D-2 — Tabla de mapeo reto → métrica:
 * ┌──────────────────┬────────────────────────────────────────────────┬───────────┐
 * │ Reto             │ Métrica (eje X invertido por espejo selfie)    │ Frames    │
 * ├──────────────────┼────────────────────────────────────────────────┼───────────┤
 * │ girar_izquierda  │ gaze.x > +0.18  (coherente con el óvalo espejado)│ 2       │
 * │ girar_derecha    │ gaze.x < -0.18  (coherente con el óvalo espejado)│ 2       │
 * │ parpadear        │ |lm[159].y - lm[145].y| < 0.018               │ 1         │
 * │ acercarse        │ bbox.width > 0.48 (normalizado al frame)       │ 2         │
 * │ sonreír          │ |lm[291].x - lm[61].x| > 0.10 (normalizado)   │ 2         │
 * └──────────────────┴────────────────────────────────────────────────┴───────────┘
 *
 * Índices de landmarks usados:
 * - Ojo izquierdo superior: 159, inferior: 145 (apertura vertical — parpadeo).
 * - Comisura boca izquierda: 61, derecha: 291 (ancho de boca — sonrisa).
 * - Gaze: vía gazeFromIris() con iris izquierdo; ya calculado por el motor.
 */

import type { FaceLandmark } from "./VisionEngine";
import type { ActiveChallenge } from "./liveness";

// ---------------------------------------------------------------------------
// Constantes de threshold (C-34 Task 2.1) — exportadas para ajuste externo
// ---------------------------------------------------------------------------

/**
 * Desplazamiento mínimo del iris respecto al centro del ojo para detectar giro.
 * Bajado de 0.25 → 0.18 para que un giro de cabeza normal lo registre sin exigir
 * un giro exagerado. Sigue requiriendo un gesto claro (no ruido), pero es usable.
 */
export const GAZE_TURN_THRESHOLD = 0.18;

/**
 * Apertura máxima del ojo (distancia vertical entre landmark superior e inferior)
 * para considerar que el ojo está cerrado (parpadeo).
 * Coordenadas normalizadas de FaceLandmarker (0..1 relativo al frame).
 */
export const BLINK_CLOSE_THRESHOLD = 0.018;

/**
 * Ancho mínimo del bounding box del rostro (normalizado al ancho del frame)
 * para considerar que el alumno se acercó lo suficiente.
 */
export const FACE_APPROACH_THRESHOLD = 0.48;

/**
 * Ancho mínimo de la boca (distancia horizontal entre comisuras, normalizada)
 * para detectar sonrisa.
 */
export const SMILE_WIDTH_THRESHOLD = 0.10;

// Frames consecutivos mínimos para confirmar cada reto.
// Reducidos respecto al original (3/2/3/3) para que un gesto natural lo registre
// sin tener que sostenerlo de forma antinatural. Siguen exigiendo varios frames
// consecutivos → el liveness sigue requiriendo el gesto (no se dispara con un
// frame espurio), pero la captura es usable.
export const FRAMES_MIN_TURN = 2;
export const FRAMES_MIN_BLINK = 1;
export const FRAMES_MIN_APPROACH = 2;
export const FRAMES_MIN_SMILE = 2;

/** Devuelve el número mínimo de frames consecutivos requeridos para el reto dado. */
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

// ---------------------------------------------------------------------------
// Evaluador puro (C-34 Task 2.2)
// ---------------------------------------------------------------------------

/**
 * Evalúa si el frame actual cumple el threshold del reto dado.
 *
 * Retorna `true` si el frame cumple la condición; `false` si no la cumple o
 * si faltan datos (landmarks insuficientes, bbox null para `acercarse`).
 *
 * SIN lógica de acumulación — eso es responsabilidad del componente.
 *
 * @param challenge  - Reto a evaluar.
 * @param landmarks  - Array de 468+ landmarks del FaceLandmarker.
 * @param gaze       - Dirección de mirada normalizada (-1..1) del gazeFromIris().
 * @param bbox       - Bounding box del rostro normalizado (0..1), o null si no se detectó rostro.
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
    // desplazan hacia la DERECHA de la imagen → gaze.x > 0. El usuario, en cambio,
    // ve el óvalo espejado (como un espejo real), así que el label "Girar a la
    // izquierda" debe matchear el movimiento que él PERCIBE. Para que el reto sea
    // coherente con lo que ve en pantalla, invertimos el eje X respecto del frame
    // crudo: "izquierda" (lo que el usuario percibe) ⇒ gaze.x > +threshold en crudo.
    case "girar_izquierda":
      return gaze.x > GAZE_TURN_THRESHOLD;

    case "girar_derecha":
      return gaze.x < -GAZE_TURN_THRESHOLD;

    // C-34 Task 2.5: parpadear — ojo cerrado (landmark superior e inferior del ojo izquierdo)
    // Landmark 159: párpado superior; 145: párpado inferior.
    // Si landmarks.length < 160, no hay datos suficientes → false.
    case "parpadear": {
      if (landmarks.length < 160) return false;
      const upper = landmarks[159];
      const lower = landmarks[145];
      const openness = Math.abs(upper.y - lower.y);
      return openness < BLINK_CLOSE_THRESHOLD;
    }

    // C-34 Task 2.6: acercarse — bounding box suficientemente ancho
    case "acercarse":
      return bbox !== null && bbox.width > FACE_APPROACH_THRESHOLD;

    // C-34 Task 2.7: sonreír — comisuras de boca separadas horizontalmente
    // Landmark 61: comisura izquierda; 291: comisura derecha.
    // Si landmarks.length < 292, no hay datos suficientes → false.
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
