/**
 * Interpretación de la calibración de cámara en Test de detección (27/8/2026).
 *
 * POR QUÉ IMPORTA: si la webcam está físicamente descentrada (arriba del monitor,
 * a un costado, en un notebook con la pantalla inclinada), el vector de iris tiene
 * magnitud alta respecto del centro del FRAME aunque el alumno esté mirando bien
 * al examen. Sin calibrar, eso dispara "mirada desviada sostenida" por leer
 * normalmente: un falso positivo contra alguien que no hizo nada.
 *
 * La calibración ya existe y corre al inicio del examen, pero ahí el docente NO la
 * ve: es un overlay de tres segundos en la pantalla del alumno. Test de detección
 * es justamente la pantalla donde se comprueba que el motor detecta bien ANTES de
 * un examen real, y no tenía forma de medir esto.
 *
 * Estas funciones traducen el baseline crudo a algo accionable: cuán descentrada
 * está la cámara y si conviene moverla antes del examen.
 */
import { describe, expect, it } from 'vitest';
import { interpretarCalibracion, DESVIO_LEVE, DESVIO_MARCADO } from './calibracionCamara';

describe('interpretarCalibracion', () => {
  it('sin baseline el estado es "no se pudo", no un cero silencioso', () => {
    // Devolver {0,0} ante un fallo diría "cámara perfectamente centrada", que es
    // la conclusión más equivocada posible: taparía justo el problema a detectar.
    const r = interpretarCalibracion(null);
    expect(r.estado).toBe('fallida');
  });

  it('una cámara centrada da desvío casi nulo', () => {
    const r = interpretarCalibracion({ x: 0.01, y: -0.02 });
    expect(r.estado).toBe('lista');
    if (r.estado !== 'lista') return;
    expect(r.nivel).toBe('centrada');
    expect(r.desvio).toBeCloseTo(0.022, 2);
  });

  it('calcula el desvío como la distancia al centro, no como la suma de ejes', () => {
    // Pitágoras: 0,06 y 0,08 dan 0,10, no 0,14. Sumar los ejes exageraría el
    // desvío y mandaría a mover cámaras que están bien.
    const r = interpretarCalibracion({ x: 0.06, y: 0.08 });
    expect(r.estado).toBe('lista');
    if (r.estado !== 'lista') return;
    expect(r.desvio).toBeCloseTo(0.1, 5);
  });

  it('un desvío intermedio se marca como leve', () => {
    const r = interpretarCalibracion({ x: DESVIO_LEVE + 0.01, y: 0 });
    expect(r.estado).toBe('lista');
    if (r.estado !== 'lista') return;
    expect(r.nivel).toBe('leve');
  });

  it('un desvío grande se marca como marcado y recomienda mover la cámara', () => {
    const r = interpretarCalibracion({ x: DESVIO_MARCADO + 0.05, y: 0 });
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
    const derecha = interpretarCalibracion({ x: 0.12, y: 0 });
    const izquierda = interpretarCalibracion({ x: -0.12, y: 0 });
    expect(derecha.estado).toBe('lista');
    expect(izquierda.estado).toBe('lista');
    if (derecha.estado !== 'lista' || izquierda.estado !== 'lista') return;
    expect(derecha.desvio).toBeCloseTo(izquierda.desvio, 10);
    expect(derecha.nivel).toBe(izquierda.nivel);
  });

  it('dice hacia dónde está corrida, para saber qué mover', () => {
    const r = interpretarCalibracion({ x: 0.15, y: -0.03 });
    expect(r.estado).toBe('lista');
    if (r.estado !== 'lista') return;
    expect(r.direccion).toBe('derecha');
  });

  it('cuando el eje vertical domina, nombra arriba o abajo', () => {
    const arriba = interpretarCalibracion({ x: 0.01, y: -0.15 });
    const abajo = interpretarCalibracion({ x: 0.01, y: 0.15 });
    expect(arriba.estado).toBe('lista');
    expect(abajo.estado).toBe('lista');
    if (arriba.estado !== 'lista' || abajo.estado !== 'lista') return;
    expect(arriba.direccion).toBe('arriba');
    expect(abajo.direccion).toBe('abajo');
  });

  it('una cámara centrada no nombra ninguna dirección', () => {
    const r = interpretarCalibracion({ x: 0.005, y: 0.005 });
    expect(r.estado).toBe('lista');
    if (r.estado !== 'lista') return;
    expect(r.direccion).toBeNull();
  });
});
