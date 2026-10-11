import { describe, expect, it } from 'vitest';
import { calcularRangoCalibracion, type Esquina, type PuntoGaze } from './calibracionRango';

const CUATRO_ESQUINAS: Record<Esquina, PuntoGaze> = {
  arriba_izquierda: { x: -0.2, y: -0.5 },
  arriba_derecha: { x: 0.22, y: -0.48 },
  abajo_derecha: { x: 0.24, y: 0.52 },
  abajo_izquierda: { x: -0.18, y: 0.5 },
};

describe('calcularRangoCalibracion', () => {
  it('el centro es el promedio de las 4 esquinas', () => {
    const rango = calcularRangoCalibracion(CUATRO_ESQUINAS, 13);
    expect(rango).not.toBeNull();
    expect(rango!.centro.x).toBeCloseTo((-0.2 + 0.22 + 0.24 - 0.18) / 4, 6);
    expect(rango!.centro.y).toBeCloseTo((-0.5 - 0.48 + 0.52 + 0.5) / 4, 6);
  });

  it('el rango de cada eje es el min/max real de las 4 esquinas', () => {
    const rango = calcularRangoCalibracion(CUATRO_ESQUINAS, 13);
    expect(rango!.rangoX).toEqual([-0.2, 0.24]);
    expect(rango!.rangoY).toEqual([-0.5, 0.52]);
  });

  it('conserva muestrasPorPunto tal cual se lo pasaron', () => {
    const rango = calcularRangoCalibracion(CUATRO_ESQUINAS, 27);
    expect(rango!.muestrasPorPunto).toBe(27);
  });

  it('null si falta una esquina — no arma un rectángulo con 3 puntos', () => {
    const incompleto = { ...CUATRO_ESQUINAS, abajo_izquierda: null };
    expect(calcularRangoCalibracion(incompleto, 13)).toBeNull();
  });

  it('null si TODAS las esquinas faltan (cámara nunca detectó nada)', () => {
    const nada: Record<Esquina, PuntoGaze | null> = {
      arriba_izquierda: null,
      arriba_derecha: null,
      abajo_derecha: null,
      abajo_izquierda: null,
    };
    expect(calcularRangoCalibracion(nada, 0)).toBeNull();
  });
});
