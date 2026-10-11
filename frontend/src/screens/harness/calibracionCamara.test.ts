/**
 * Interpretación de la calibración de cámara en Test de detección (27/8/2026,
 * actualizado a la calibración de 4 esquinas el 9/9/2026).
 *
 * POR QUÉ IMPORTA: si la webcam está físicamente descentrada (arriba del monitor,
 * a un costado, en un notebook con la pantalla inclinada), el vector de iris tiene
 * magnitud alta respecto del centro del FRAME aunque el alumno esté mirando bien
 * al examen. Sin calibrar, eso dispara "mirada desviada sostenida" por leer
 * normalmente: un falso positivo contra alguien que no hizo nada.
 *
 * La calibración corre en el mismo componente que usa el alumno
 * (`CalibracionCuatroPuntos`) — antes esta pantalla no la reproducía, tenía su
 * propia captura de UN punto con constantes propias.
 *
 * Estas funciones traducen el RANGO de 4 esquinas a algo accionable: cuán
 * descentrada está la cámara, si conviene moverla, y qué proporción
 * vertical/horizontal midió (reemplaza al factor fijo de `stateTransitionRules.ts`).
 */
import { describe, expect, it } from 'vitest';
import { interpretarCalibracion, DESVIO_LEVE, DESVIO_MARCADO } from './calibracionCamara';
import type { RangoCalibracion } from '../../proctoring/calibracionRango';

/** Envuelve un centro en un RangoCalibracion con un rango parejo (±0,25 en
 *  ambos ejes) — para los tests que solo les importa el CENTRO, no el rango. */
function conCentro(x: number, y: number): RangoCalibracion {
  return {
    centro: { x, y },
    rangoX: [x - 0.25, x + 0.25],
    rangoY: [y - 0.25, y + 0.25],
    muestrasPorPunto: 13,
  };
}

describe('interpretarCalibracion', () => {
  it('sin rango el estado es "no se pudo", no un cero silencioso', () => {
    // Devolver {0,0} ante un fallo diría "cámara perfectamente centrada", que es
    // la conclusión más equivocada posible: taparía justo el problema a detectar.
    const r = interpretarCalibracion(null);
    expect(r.estado).toBe('fallida');
  });

  it('una cámara centrada da desvío casi nulo', () => {
    const r = interpretarCalibracion(conCentro(0.01, -0.02));
    expect(r.estado).toBe('lista');
    if (r.estado !== 'lista') return;
    expect(r.nivel).toBe('centrada');
    expect(r.desvio).toBeCloseTo(0.022, 2);
  });

  it('calcula el desvío como la distancia al centro, no como la suma de ejes', () => {
    // Pitágoras: 0,06 y 0,08 dan 0,10, no 0,14. Sumar los ejes exageraría el
    // desvío y mandaría a mover cámaras que están bien.
    const r = interpretarCalibracion(conCentro(0.06, 0.08));
    expect(r.estado).toBe('lista');
    if (r.estado !== 'lista') return;
    expect(r.desvio).toBeCloseTo(0.1, 5);
  });

  it('un desvío intermedio se marca como leve', () => {
    const r = interpretarCalibracion(conCentro(DESVIO_LEVE + 0.01, 0));
    expect(r.estado).toBe('lista');
    if (r.estado !== 'lista') return;
    expect(r.nivel).toBe('leve');
  });

  it('un desvío grande se marca como marcado y recomienda mover la cámara', () => {
    const r = interpretarCalibracion(conCentro(DESVIO_MARCADO + 0.05, 0));
    expect(r.estado).toBe('lista');
    if (r.estado !== 'lista') return;
    expect(r.nivel).toBe('marcada');
    expect(r.consejo).toMatch(/mov[ée]/i);
  });

  it('el umbral de desvío marcado no supera el umbral de mirada desviada', () => {
    // Si la cámara está descentrada MÁS de lo que el sistema tolera como mirada
    // desviada (0,20 por defecto), el alumno arranca el examen ya en falta. Avisar
    // recién pasado ese punto llegaría tarde.
    expect(DESVIO_MARCADO).toBeLessThanOrEqual(0.2);
    expect(DESVIO_LEVE).toBeLessThan(DESVIO_MARCADO);
  });

  it('el desvío no depende del signo: da igual para qué lado esté corrida', () => {
    const derecha = interpretarCalibracion(conCentro(0.12, 0));
    const izquierda = interpretarCalibracion(conCentro(-0.12, 0));
    expect(derecha.estado).toBe('lista');
    expect(izquierda.estado).toBe('lista');
    if (derecha.estado !== 'lista' || izquierda.estado !== 'lista') return;
    expect(derecha.desvio).toBeCloseTo(izquierda.desvio, 10);
    expect(derecha.nivel).toBe(izquierda.nivel);
  });

  it('dice hacia dónde está corrida, para saber qué mover', () => {
    const r = interpretarCalibracion(conCentro(0.15, -0.03));
    expect(r.estado).toBe('lista');
    if (r.estado !== 'lista') return;
    expect(r.direccion).toBe('derecha');
  });

  it('cuando el eje vertical domina, nombra arriba o abajo', () => {
    const arriba = interpretarCalibracion(conCentro(0.01, -0.15));
    const abajo = interpretarCalibracion(conCentro(0.01, 0.15));
    expect(arriba.estado).toBe('lista');
    expect(abajo.estado).toBe('lista');
    if (arriba.estado !== 'lista' || abajo.estado !== 'lista') return;
    expect(arriba.direccion).toBe('arriba');
    expect(abajo.direccion).toBe('abajo');
  });

  it('una cámara centrada no nombra ninguna dirección', () => {
    const r = interpretarCalibracion(conCentro(0.005, 0.005));
    expect(r.estado).toBe('lista');
    if (r.estado !== 'lista') return;
    expect(r.direccion).toBeNull();
  });

  describe('factor vertical MEDIDO (reemplaza al factor fijo de stateTransitionRules.ts)', () => {
    it('un rango parejo entre ejes da un factor cercano a 1', () => {
      const r = interpretarCalibracion({
        centro: { x: 0, y: 0 },
        rangoX: [-0.2, 0.2],
        rangoY: [-0.22, 0.22],
        muestrasPorPunto: 13,
      });
      expect(r.estado).toBe('lista');
      if (r.estado !== 'lista') return;
      expect(r.factorVerticalMedido).toBeCloseTo(1.1, 5);
    });

    it('un rango vertical más ancho que el horizontal da un factor > 1, sin clampear', () => {
      // El diagnóstico muestra el valor REAL medido — el clamp de seguridad
      // (FACTOR_VERTICAL_MINIMO/MAXIMO) vive en la detección, no acá.
      const r = interpretarCalibracion({
        centro: { x: 0, y: 0 },
        rangoX: [-0.05, 0.05],
        rangoY: [-0.5, 0.5],
        muestrasPorPunto: 13,
      });
      expect(r.estado).toBe('lista');
      if (r.estado !== 'lista') return;
      expect(r.factorVerticalMedido).toBeCloseTo(10, 5);
    });

    it('rangoX de ancho cero (degenerado) da factorVerticalMedido null, no Infinity', () => {
      const r = interpretarCalibracion({
        centro: { x: 0, y: 0 },
        rangoX: [0, 0],
        rangoY: [-0.5, 0.5],
        muestrasPorPunto: 13,
      });
      expect(r.estado).toBe('lista');
      if (r.estado !== 'lista') return;
      expect(r.factorVerticalMedido).toBeNull();
    });
  });
});
