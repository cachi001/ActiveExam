/**
 * framingGuide — heurística pura que decide qué hint mostrarle al alumno antes
 * y durante la captura biométrica.
 *
 * Recibe señales crudas del frame (luminancia, bbox del rostro, conteo de caras
 * normalizado al frame) y devuelve un único hint priorizado o `null` si todo
 * está en orden. Mantener el orden por prioridad: el primero que matchea, gana.
 *
 * Función PURA: sin DOM, sin estado, sin efectos. Re-entrante en cada frame.
 */

export type FramingHint =
  | 'sin_rostro'
  | 'multiples_rostros'
  | 'poca_luz'
  | 'mucha_luz'
  | 'lejos'
  | 'cerca'
  | 'descentrado'
  | 'no_frontal';

export interface FramingSignals {
  /** Cantidad de rostros detectados por el motor en el frame actual. */
  faceCount: number;
  /**
   * Luminancia promedio del frame en [0..255]. Calculada como (0.299·R + 0.587·G + 0.114·B).
   * Si no se pudo medir, pasar `null` y el detector la ignora.
   */
  luminanceAvg: number | null;
  /** Ancho de la bounding box del rostro relativo al ancho del frame (0..1). */
  faceBboxWidth: number | null;
  /** Coordenada x del centroide del rostro en [0..1]. */
  faceCenterX: number | null;
  /** Coordenada y del centroide del rostro en [0..1]. */
  faceCenterY: number | null;
}

// Umbrales calibrados a ojo razonable. Si se ajustan, mover acá (D-2 del C-34).
// C-65 ajuste post-prueba: óvalo tipo app bancaria — centrado y tamaño APRETADOS
// para forzar una referencia consistente (cara grande, centrada, con margen del
// borde del frame). NO es por corrección del embedding (face-api re-alinea), sino
// guardarraíl de CALIDAD/consistencia de la captura.
// C-67: umbrales RELAJADOS. Los de C-65 ("tipo banco", apretados) falseaban:
// pedían recentrar/acercar/alejar aunque el rostro estuviera bien. Se aflojan a
// una ventana cómoda — siguen siendo guardarraíl de calidad, sin nitpicking.
const LUM_LOW = 48;     // < 48 sobre 255 = penumbra real → "más luz" (antes 55)
const LUM_HIGH = 238;   // > 238 = contraluz/saturado (antes 230)
const BBOX_FAR = 0.22;  // rostro < 22% del frame → "acercate" (antes 0.30)
const BBOX_NEAR = 0.72; // rostro > 72% del frame → "alejate" (antes 0.58)
const OFFCENTER = 0.16; // |0.5 - cx| > 0.16 → "centrá" (antes 0.08, demasiado estricto)
const OFFCENTER_Y = 0.20; // |0.5 - cy| > 0.20 → "centrá" (antes 0.10)

// Frontalidad (C-65) = CABEZA DERECHA, NO mirada de ojos. Se mide por la asimetría
// horizontal de la nariz respecto a las comisuras externas de los ojos (yaw de
// la cabeza). NO usa gaze/iris: el alumno mira la PANTALLA (no la cámara), así que
// exigir que el iris apunte a la lente sería antinatural. Umbral LENE: sólo
// bloquea cuando la cabeza está claramente girada, no por mirar de reojo.
const YAW_MAX = 0.30;

/**
 * Devuelve el hint dominante para el frame actual, en orden de prioridad:
 *  1. Sin rostro o múltiples rostros: no hay nada útil que decir más.
 *  2. Luz: si no se ve bien, los demás chequeos no son confiables.
 *  3. Distancia: si está mal escalado, el liveness no va a triggerear bien.
 *  4. Centrado: la heurística más permisiva, se evalúa al final.
 *
 * Devuelve `null` cuando el encuadre es razonable y puede arrancar el reto.
 */
export function evaluateFraming(s: FramingSignals): FramingHint | null {
  if (s.faceCount === 0) return 'sin_rostro';
  if (s.faceCount > 1) return 'multiples_rostros';

  if (s.luminanceAvg !== null) {
    if (s.luminanceAvg < LUM_LOW) return 'poca_luz';
    if (s.luminanceAvg > LUM_HIGH) return 'mucha_luz';
  }

  if (s.faceBboxWidth !== null) {
    if (s.faceBboxWidth < BBOX_FAR) return 'lejos';
    if (s.faceBboxWidth > BBOX_NEAR) return 'cerca';
  }

  if (s.faceCenterX !== null && s.faceCenterY !== null) {
    if (Math.abs(0.5 - s.faceCenterX) > OFFCENTER) return 'descentrado';
    if (Math.abs(0.5 - s.faceCenterY) > OFFCENTER_Y) return 'descentrado';
  }

  return null;
}

/**
 * Asimetría horizontal de la nariz respecto a las comisuras externas de los ojos.
 * Devuelve un valor en [-1, 1]: 0 = nariz centrada entre los ojos (cabeza de
 * frente); el signo indica el lado del giro. Invariante a escala y a la posición
 * absoluta de la cara en el frame (sólo mide la geometría del giro).
 *
 * Función PURA.
 */
export function headYawAsymmetry(noseX: number, eyeOuterAX: number, eyeOuterBX: number): number {
  const dA = Math.abs(noseX - eyeOuterAX);
  const dB = Math.abs(eyeOuterBX - noseX);
  const sum = dA + dB;
  if (sum === 0) return 0;
  return (dA - dB) / sum;
}

/**
 * Retorna true si la CABEZA está derecha (de frente), mirando la pantalla con la
 * cara recta — independiente de a dónde apunten los OJOS. Usa los landmarks de
 * Face Mesh: nariz (1) y comisuras externas de los ojos (33, 263). NO usa gaze.
 *
 * Sirve para exigir pose frontal al capturar la referencia (baseline neutral) y
 * en retos que no sean de giro; el caller DEBE suprimir esta exigencia durante el
 * reto girar_cabeza. Si no hay landmarks suficientes, retorna true (no bloquea por
 * frontalidad sin datos — otros hints ya cubren "sin rostro").
 *
 * Función PURA: sin DOM, sin estado, sin efectos.
 */
export function isFrontal(landmarks: ReadonlyArray<{ x: number }>): boolean {
  if (!landmarks || landmarks.length < 264) return true;
  const nose = landmarks[1];
  const eyeA = landmarks[33];
  const eyeB = landmarks[263];
  if (!nose || !eyeA || !eyeB) return true;
  return Math.abs(headYawAsymmetry(nose.x, eyeA.x, eyeB.x)) <= YAW_MAX;
}

// ---------------------------------------------------------------------------
// C-65: Clasificación bloqueante / informativo (biometric-capture-framing-gate)
// ---------------------------------------------------------------------------

/**
 * Set de hints que BLOQUEAN la evaluación del reto activo mientras estén activos.
 * C-65 (ajuste post-prueba): el óvalo es referencia DURA — `descentrado` también
 * bloquea. Cualquier advertencia de encuadre (luz, distancia, centrado, rostro)
 * detiene el avance del reto. Sólo `null` (encuadre correcto) deja progresar.
 */
export const BLOCKING_HINTS = new Set<FramingHint>([
  'sin_rostro',
  'multiples_rostros',
  'poca_luz',
  'mucha_luz',
  'lejos',
  'cerca',
  'descentrado',
  'no_frontal',
]);

/**
 * Retorna true si el hint es BLOQUEANTE (debe detener la evaluación del reto activo).
 * Con el ajuste de C-65, TODO hint no-null es bloqueante; sólo `null` (encuadre
 * correcto) retorna false.
 *
 * Función PURA: sin DOM, sin estado, sin efectos.
 */
export function isHintBloqueante(hint: FramingHint | null): boolean {
  if (hint === null) return false;
  return BLOCKING_HINTS.has(hint);
}

/** Copy humano por hint — el componente lo lee tal cual y lo muestra. */
export const FRAMING_COPY: Record<FramingHint, { titulo: string; sub: string }> = {
  sin_rostro: {
    titulo: 'No te vemos en el óvalo',
    sub: 'Acomodate frente a la cámara, con la cara visible.',
  },
  multiples_rostros: {
    titulo: 'Tiene que haber una sola persona',
    sub: 'Pediles a las demás que salgan del cuadro y volvé al óvalo.',
  },
  poca_luz: {
    titulo: 'Poca luz en tu rostro',
    sub: 'Acercate a una ventana o prendé otra lámpara antes de seguir.',
  },
  mucha_luz: {
    titulo: 'Hay demasiada luz a contraluz',
    sub: 'Movete para que la luz fuerte no esté detrás tuyo.',
  },
  lejos: {
    titulo: 'Estás un poco lejos',
    sub: 'Acercate hasta que tu rostro llene el óvalo.',
  },
  cerca: {
    titulo: 'Estás muy cerca',
    sub: 'Alejate un poco hasta que tu rostro entre cómodo en el óvalo.',
  },
  descentrado: {
    titulo: 'Centrá tu rostro',
    sub: 'Movete despacio hasta quedar en el medio del óvalo.',
  },
  no_frontal: {
    titulo: 'Mirá de frente',
    sub: 'Poné la cabeza derecha y mirá a la cámara, sin girar la cara.',
  },
};
