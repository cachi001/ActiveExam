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
import type { RangoCalibracion } from '../../proctoring/calibracionRango';

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
  /** No se pudo medir las 4 esquinas: rostro ausente en alguna, cámara tapada,
   *  motor sin mesh, o se salió de pantalla completa a mitad de camino. */
  | { estado: 'fallida' }
  | {
      estado: 'lista';
      baseline: { x: number; y: number };
      /** Distancia del baseline al centro del frame. */
      desvio: number;
      nivel: NivelDesvio;
      direccion: DireccionDesvio;
      consejo: string;
      /** Proporción vertical/horizontal MEDIDA en las 4 esquinas — reemplaza al
       *  factor fijo (2.5) que `stateTransitionRules.ts` usa cuando no hay esta
       *  medición (ver `calibrarGaze`). Sin clamp: acá interesa el valor real
       *  medido, el clamp de seguridad vive en la detección, no en el diagnóstico. */
      factorVerticalMedido: number | null;
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
 * Traduce el rango de 4 esquinas capturado a un diagnóstico.
 *
 * `null` (que es lo que devuelve `CalibracionCuatroPuntos` cuando no pudo medir
 * alguna esquina, o se salió de pantalla completa) se reporta como fallida,
 * NUNCA como {0,0}: un cero diría "cámara perfectamente centrada", que es justo
 * la conclusión opuesta a la realidad.
 */
export function interpretarCalibracion(rango: RangoCalibracion | null): ResultadoCalibracion {
  if (rango === null) return { estado: 'fallida' };
  const baseline = rango.centro;
  // Distancia euclídea: sumar los ejes exageraría el desvío de una cámara corrida
  // en diagonal y mandaría a mover cámaras que están bien.
  const desvio = Math.hypot(baseline.x, baseline.y);
  const nivel = nivelDe(desvio);
  const anchoX = rango.rangoX[1] - rango.rangoX[0];
  const altoY = rango.rangoY[1] - rango.rangoY[0];
  return {
    estado: 'lista',
    baseline,
    desvio,
    nivel,
    direccion: direccionDe(baseline, nivel),
    consejo: CONSEJO[nivel],
    factorVerticalMedido: anchoX > 0 ? altoY / anchoX : null,
  };
}
