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
  | 'descentrado';

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
const LUM_LOW = 55;     // < 55 sobre 255 = penumbra → "más luz"
const LUM_HIGH = 230;   // > 230 = contraluz/saturado → "menos luz / contraluz"
const BBOX_FAR = 0.22;  // rostro < 22% del frame → "acercate"
const BBOX_NEAR = 0.58; // rostro > 58% del frame → "alejate un poco"
const OFFCENTER = 0.20; // |0.5 - cx| > 0.20 o |0.5 - cy| > 0.22 → "centrá"
const OFFCENTER_Y = 0.22;

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
};
