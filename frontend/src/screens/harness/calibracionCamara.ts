/**
 * Qué tan descentrada está la cámara, en términos que sirvan para hacer algo.
 *
 * El baseline de mirada es el promedio del vector de iris mientras la persona mira
 * al centro de la pantalla (ver `capturarBaselineGaze`). Si la cámara estuviera
 * perfectamente alineada con el centro de la pantalla, ese promedio daría cerca de
 * (0,0). Cuanto más lejos, más corrida está físicamente la cámara.
 *
 * Importa porque el sistema evalúa "mirada desviada" contra ese baseline: con una
 * cámara muy descentrada y sin calibrar, alguien que lee normalmente el examen
 * arranca ya pasado del umbral. Es un falso positivo contra quien no hizo nada.
 */

/** Desde acá el desvío ya se nota, pero todavía no compromete la detección. */
export const DESVIO_LEVE = 0.08;

/**
 * Desde acá conviene mover la cámara antes del examen. Se queda por debajo del
 * `gaze_deviation_threshold` por defecto (0,20) a propósito: avisar recién al
 * llegar a ese valor sería avisar cuando el problema ya está.
 */
export const DESVIO_MARCADO = 0.15;

export type NivelDesvio = 'centrada' | 'leve' | 'marcada';
export type DireccionDesvio = 'izquierda' | 'derecha' | 'arriba' | 'abajo' | null;

export type ResultadoCalibracion =
  | { estado: 'sin_calibrar' }
  | { estado: 'calibrando' }
  /** No se pudo capturar ninguna muestra: rostro ausente, cámara tapada o motor sin mesh. */
  | { estado: 'fallida' }
  | {
      estado: 'lista';
      baseline: { x: number; y: number };
      /** Distancia del baseline al centro del frame. */
      desvio: number;
      nivel: NivelDesvio;
      direccion: DireccionDesvio;
      consejo: string;
    };

const CONSEJO: Record<NivelDesvio, string> = {
  centrada:
    'La cámara está bien alineada con la pantalla. La detección de mirada va a medir sobre una base limpia.',
  leve: 'La cámara está algo corrida. Funciona igual, pero centrarla un poco mejora la precisión.',
  marcada:
    'La cámara está bastante corrida respecto de la pantalla. Movéla antes del examen: así como está, alguien que mira el examen normalmente puede dar mirada desviada.',
};

function nivelDe(desvio: number): NivelDesvio {
  if (desvio >= DESVIO_MARCADO) return 'marcada';
  if (desvio >= DESVIO_LEVE) return 'leve';
  return 'centrada';
}

/** Hacia dónde está corrida, según el eje que más pesa. `null` si está centrada. */
function direccionDe(
  baseline: { x: number; y: number },
  nivel: NivelDesvio,
): DireccionDesvio {
  if (nivel === 'centrada') return null;
  if (Math.abs(baseline.x) >= Math.abs(baseline.y)) {
    return baseline.x > 0 ? 'derecha' : 'izquierda';
  }
  // El eje Y del frame crece hacia abajo.
  return baseline.y > 0 ? 'abajo' : 'arriba';
}

/**
 * Traduce el baseline capturado a un diagnóstico.
 *
 * `null` (que es lo que devuelve `capturarBaselineGaze` cuando no juntó ninguna
 * muestra) se reporta como fallida, NUNCA como {0,0}: un cero diría "cámara
 * perfectamente centrada", que es justo la conclusión opuesta a la realidad.
 */
export function interpretarCalibracion(
  baseline: { x: number; y: number } | null,
): ResultadoCalibracion {
  if (baseline === null) return { estado: 'fallida' };
  // Distancia euclídea: sumar los ejes exageraría el desvío de una cámara corrida
  // en diagonal y mandaría a mover cámaras que están bien.
  const desvio = Math.hypot(baseline.x, baseline.y);
  const nivel = nivelDe(desvio);
  return {
    estado: 'lista',
    baseline,
    desvio,
    nivel,
    direccion: direccionDe(baseline, nivel),
    consejo: CONSEJO[nivel],
  };
}
