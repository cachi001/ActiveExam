import { beforeEach, describe, expect, it } from 'vitest';

import {
  DESVIO_LATERAL_MINIMO,
  baselineGazeGuardado,
  posicionDeLaCamara,
  debeCalibrarEnElExamen,
  guardarBaselineGaze,
  olvidarBaselineGaze,
  rangoGazeGuardado,
} from './baselineGaze';

beforeEach(() => olvidarBaselineGaze());

describe('baseline de mirada del paso de calibración', () => {
  it('sin calibrar no hay baseline', () => {
    expect(baselineGazeGuardado()).toBeNull();
  });

  it('guarda lo que midió el paso previo', () => {
    guardarBaselineGaze({ x: 0.12, y: -0.05 });
    expect(baselineGazeGuardado()).toEqual({ x: 0.12, y: -0.05 });
  });

  it('el examen NO recalibra si la sala ya calibró', () => {
    // Es el punto del cambio: la calibración deja de comerle tiempo al examen.
    guardarBaselineGaze({ x: 0, y: 0 });
    expect(debeCalibrarEnElExamen()).toBe(false);
  });

  it('el examen SÍ calibra si no hay baseline (respaldo)', () => {
    // Recarga a mitad de examen, o entrada por una ruta que se saltea la sala:
    // el alumno nunca puede quedarse sin calibrar.
    expect(debeCalibrarEnElExamen()).toBe(true);
  });

  it('un baseline en el origen es válido, no "sin calibrar"', () => {
    // {0,0} es un resultado legítimo (alumno mirando justo al centro). Si se
    // tratara como falsy, el examen recalibraría al pedo.
    guardarBaselineGaze({ x: 0, y: 0 });
    expect(baselineGazeGuardado()).toEqual({ x: 0, y: 0 });
    expect(debeCalibrarEnElExamen()).toBe(false);
  });

  it('guardar null vuelve a "sin calibrar": la calibración pudo fallar', () => {
    guardarBaselineGaze({ x: 1, y: 1 });
    guardarBaselineGaze(null);
    expect(debeCalibrarEnElExamen()).toBe(true);
  });
});

describe('rango de 4 esquinas guardado junto al baseline', () => {
  it('sin calibrar no hay rango', () => {
    expect(rangoGazeGuardado()).toBeNull();
  });

  it('un baseline de un solo punto (respaldo) no trae rango', () => {
    guardarBaselineGaze({ x: 0.1, y: 0 });
    expect(rangoGazeGuardado()).toBeNull();
  });

  it('la calibración de 4 esquinas guarda el rango junto al baseline', () => {
    const rangoValor = { rangoX: [-0.2, 0.2] as [number, number], rangoY: [-0.5, 0.5] as [number, number] };
    guardarBaselineGaze({ x: 0, y: 0 }, rangoValor);
    expect(rangoGazeGuardado()).toEqual(rangoValor);
  });

  it('guardar null como baseline descarta el rango, aunque se pase uno', () => {
    guardarBaselineGaze({ x: 0, y: 0 }, { rangoX: [-0.2, 0.2], rangoY: [-0.5, 0.5] });
    guardarBaselineGaze(null, { rangoX: [-0.1, 0.1], rangoY: [-0.1, 0.1] });
    expect(rangoGazeGuardado()).toBeNull();
  });

  it('olvidarBaselineGaze descarta el rango junto con el baseline', () => {
    guardarBaselineGaze({ x: 0, y: 0 }, { rangoX: [-0.2, 0.2], rangoY: [-0.5, 0.5] });
    olvidarBaselineGaze();
    expect(rangoGazeGuardado()).toBeNull();
  });
});

describe('posición de la cámara según lo calibrado', () => {
  it('sin calibrar no dice nada', () => {
    expect(posicionDeLaCamara(null)).toBeNull();
  });

  it('mirada casi al frente = cámara centrada', () => {
    expect(posicionDeLaCamara({ x: 0.02, y: 0 })).toBe('centrada');
  });

  it('desvío chico sigue siendo centrada: es ruido de medición', () => {
    expect(posicionDeLaCamara({ x: DESVIO_LATERAL_MINIMO - 0.01, y: 0 })).toBe('centrada');
  });

  it('mirada hacia la derecha del encuadre = cámara a la izquierda', () => {
    expect(posicionDeLaCamara({ x: 0.4, y: 0 })).toBe('izquierda');
  });

  it('y al revés', () => {
    expect(posicionDeLaCamara({ x: -0.4, y: 0 })).toBe('derecha');
  });

  it('la altura no cambia el lado', () => {
    // Solo la componente horizontal dice de qué lado quedó la cámara.
    expect(posicionDeLaCamara({ x: 0.02, y: 0.9 })).toBe('centrada');
  });
});
