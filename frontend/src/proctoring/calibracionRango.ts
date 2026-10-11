/**
 * El rectángulo real de la pantalla, medido en el espacio de la mirada.
 *
 * Calibrar mirando un solo punto (el centro) da un CERO, pero no dice nada de
 * cuánto se mueve el vector de iris de punta a punta de la pantalla — esa
 * escala se adivinaba con un factor fijo (`VERTICAL_TOLERANCE_FACTOR = 2.5` en
 * `stateTransitionRules.ts`). Midiendo las 4 ESQUINAS se puede calcular en vez
 * de adivinar: el rango de cada eje es literalmente el ancho/alto de la
 * pantalla en unidades de gaze.
 */

export type Esquina = 'arriba_izquierda' | 'arriba_derecha' | 'abajo_derecha' | 'abajo_izquierda';

/** Orden de presentación: un recorrido en sentido horario, no saltos en diagonal. */
export const ESQUINAS: readonly Esquina[] = [
  'arriba_izquierda',
  'arriba_derecha',
  'abajo_derecha',
  'abajo_izquierda',
];

export const ESQUINA_LABEL: Record<Esquina, string> = {
  arriba_izquierda: 'arriba a la izquierda',
  arriba_derecha: 'arriba a la derecha',
  abajo_derecha: 'abajo a la derecha',
  abajo_izquierda: 'abajo a la izquierda',
};

export interface PuntoGaze {
  x: number;
  y: number;
}

export interface RangoCalibracion {
  centro: PuntoGaze;
  rangoX: [number, number];
  rangoY: [number, number];
  muestrasPorPunto: number;
}

/**
 * Centro (promedio) y rango [min, max] de cada eje a partir de las 4 esquinas.
 *
 * `null` si falta alguna: una calibración de 4 puntos a medias no describe un
 * rectángulo, describe una figura arbitraria — mejor pedir que se repita
 * entera que guardar un rango torcido y confiar en él durante todo el examen.
 */
export function calcularRangoCalibracion(
  puntos: Record<Esquina, PuntoGaze | null>,
  muestrasPorPunto: number,
): RangoCalibracion | null {
  const valores = ESQUINAS.map((e) => puntos[e]);
  if (valores.some((v) => v === null)) return null;
  const completos = valores as PuntoGaze[];
  const xs = completos.map((v) => v.x);
  const ys = completos.map((v) => v.y);
  const suma = (arr: number[]) => arr.reduce((a, b) => a + b, 0);
  return {
    centro: { x: suma(xs) / xs.length, y: suma(ys) / ys.length },
    rangoX: [Math.min(...xs), Math.max(...xs)],
    rangoY: [Math.min(...ys), Math.max(...ys)],
    muestrasPorPunto,
  };
}
