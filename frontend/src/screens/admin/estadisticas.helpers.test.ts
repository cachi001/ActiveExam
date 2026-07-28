/**
 * TDD: RED → GREEN → TRIANGULATE
 * Helpers puros de la página de estadísticas institucionales (C-20).
 *
 * Matemática del gráfico de distribución + tasas derivadas. Puras (sin red, sin
 * DOM): son las que triangulamos con varios casos. El "en riesgo" es una señal
 * de PRIORIZACIÓN (L2.5, RN-SC-01), nunca un veredicto — acá solo se ordena y
 * escala para dibujar barras.
 */

import { describe, expect, it } from 'vitest';
import {
  alturasRelativas,
  distribucionBuckets,
  donutSegmentos,
  pctSobreTotal,
  segmentosDonut,
} from './estadisticas.helpers';

describe('distribucionBuckets', () => {
  it('ordena los buckets canónicamente y escala la altura al máximo', () => {
    const bars = distribucionBuckets(
      { '0-24': 18, '25-49': 6, '50-69': 3, '70-100': 3 },
      70,
    );
    expect(bars.map((b) => b.rango)).toEqual(['0-24', '25-49', '50-69', '70-100']);
    // El bucket máximo (18) es la barra más alta (100%); el resto es proporcional.
    expect(bars[0].pct).toBe(100);
    expect(bars[1].pct).toBeCloseTo((6 / 18) * 100, 5);
    // El umbral 70 marca SOLO el rango 70-100 como banda de riesgo.
    expect(bars.map((b) => b.enRiesgo)).toEqual([false, false, false, true]);
  });

  it('con un umbral más bajo (50) marca dos rangos como riesgo', () => {
    const bars = distribucionBuckets(
      { '0-24': 1, '25-49': 1, '50-69': 2, '70-100': 4 },
      50,
    );
    expect(bars.map((b) => b.enRiesgo)).toEqual([false, false, true, true]);
    // Máximo = 4 → barra 70-100 al 100%.
    expect(bars[3].pct).toBe(100);
  });

  it('respeta las bandas que manda el backend cuando el umbral no es 70', () => {
    // BUG: con bandas fijas ('70-100'), un umbral de 80 no marcaba NINGUNA banda
    // como riesgo (70 >= 80 = false) mientras la tarjeta contaba sesiones en
    // riesgo. El backend ahora arranca la última banda EN el umbral.
    const bars = distribucionBuckets(
      { '0-24': 1, '25-49': 1, '50-79': 2, '80-100': 1 },
      80,
    );
    expect(bars.map((b) => b.rango)).toEqual(['0-24', '25-49', '50-79', '80-100']);
    expect(bars.map((b) => b.enRiesgo)).toEqual([false, false, false, true]);
  });

  it('todo en cero → pct 0 (no NaN por división por cero)', () => {
    const bars = distribucionBuckets(
      { '0-24': 0, '25-49': 0, '50-69': 0, '70-100': 0 },
      70,
    );
    expect(bars.every((b) => b.pct === 0)).toBe(true);
    expect(bars.every((b) => Number.isFinite(b.pct))).toBe(true);
  });
});

describe('donutSegmentos', () => {
  it('reparte el total en fracciones acumuladas para la rosca', () => {
    const segs = donutSegmentos(
      { '0-24': 18, '25-49': 6, '50-69': 3, '70-100': 3 },
      70,
    );
    expect(segs.map((s) => s.rango)).toEqual(['0-24', '25-49', '50-69', '70-100']);
    // Total = 30 → fracciones 0.6 / 0.2 / 0.1 / 0.1.
    expect(segs.map((s) => s.fraccion)).toEqual([0.6, 0.2, 0.1, 0.1]);
    // Porcentaje redondeado por segmento.
    expect(segs.map((s) => s.pct)).toEqual([60, 20, 10, 10]);
    // Arranque acumulado (donde empieza cada arco en la circunferencia).
    expect(segs.map((s) => s.inicio)).toEqual([0, 0.6, 0.8, 0.9]);
    // Umbral 70 → solo el último rango es banda de riesgo.
    expect(segs.map((s) => s.enRiesgo)).toEqual([false, false, false, true]);
  });

  it('con umbral 50 marca dos rangos como riesgo', () => {
    const segs = donutSegmentos(
      { '0-24': 2, '25-49': 2, '50-69': 4, '70-100': 2 },
      50,
    );
    expect(segs.map((s) => s.enRiesgo)).toEqual([false, false, true, true]);
  });

  it('con umbral 80 la última banda (80-100) es la única de riesgo', () => {
    const segs = donutSegmentos(
      { '0-24': 1, '25-49': 1, '50-79': 2, '80-100': 1 },
      80,
    );
    expect(segs.map((s) => s.rango)).toEqual(['0-24', '25-49', '50-79', '80-100']);
    expect(segs.map((s) => s.enRiesgo)).toEqual([false, false, false, true]);
    // Total = 5 → la banda de riesgo es 1/5 de la rosca.
    expect(segs[3].fraccion).toBe(0.2);
  });

  it('todo en cero → fracción y pct 0, sin NaN', () => {
    const segs = donutSegmentos(
      { '0-24': 0, '25-49': 0, '50-69': 0, '70-100': 0 },
      70,
    );
    expect(segs.every((s) => s.fraccion === 0 && s.pct === 0)).toBe(true);
    expect(segs.every((s) => Number.isFinite(s.fraccion) && Number.isFinite(s.inicio))).toBe(true);
  });
});

describe('alturasRelativas', () => {
  it('escala cada valor respecto al máximo (0..100)', () => {
    const h = alturasRelativas([6, 4, 3, 3]);
    expect(h[0]).toBe(100);
    expect(h[1]).toBeCloseTo((4 / 6) * 100, 5);
    expect(h[2]).toBe(50);
  });

  it('todo en cero → 0 (no NaN)', () => {
    const h = alturasRelativas([0, 0, 0]);
    expect(h).toEqual([0, 0, 0]);
  });
});

describe('segmentosDonut', () => {
  it('reparte en fracciones acumuladas para la rosca genérica', () => {
    const segs = segmentosDonut([
      { clave: 'a', valor: 6 },
      { clave: 'b', valor: 4 },
      { clave: 'c', valor: 3 },
      { clave: 'd', valor: 3 },
    ]);
    expect(segs.map((s) => s.fraccion)).toEqual([0.375, 0.25, 0.1875, 0.1875]);
    expect(segs.map((s) => s.inicio)).toEqual([0, 0.375, 0.625, 0.8125]);
    expect(segs.map((s) => s.pct)).toEqual([38, 25, 19, 19]);
  });

  it('total 0 → fracciones y pct 0 (sin NaN)', () => {
    const segs = segmentosDonut([{ clave: 'x', valor: 0 }, { clave: 'y', valor: 0 }]);
    expect(segs.every((s) => s.fraccion === 0 && s.pct === 0)).toBe(true);
  });
});

describe('pctSobreTotal', () => {
  it('devuelve el porcentaje redondeado', () => {
    expect(pctSobreTotal(25, 30)).toBe(83);
  });

  it('total 0 → 0 (no NaN)', () => {
    expect(pctSobreTotal(0, 0)).toBe(0);
  });
});
