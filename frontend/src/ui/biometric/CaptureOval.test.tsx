/**
 * Tests para CaptureOval — anillo de progreso sobre el borde del óvalo (C-67).
 *
 * TDD. Verifica que el <ellipse> de progreso va EXACTO sobre el borde del óvalo
 * (mismos radios que el clip del video) para que NO se salga del viewBox 100×130
 * y NO se recorte en las esquinas, y que el strokeWidth es fino/minimalista.
 *
 * No monta el componente (happy-dom no tiene SVG geometry API): verifica las
 * CONSTANTES exportadas, que son la fuente de verdad de la geometría.
 */

import { describe, expect, it } from 'vitest';

import {
  OVAL_RX,
  OVAL_RY,
  PROGRESS_RX,
  PROGRESS_RY,
  PROGRESS_STROKE_WIDTH,
  TRACK_STROKE_WIDTH,
} from './CaptureOval';

describe('CaptureOval — anillo sobre el borde (C-67)', () => {
  it('PROGRESS_RX coincide con el borde del óvalo (no se sale del clip)', () => {
    expect(PROGRESS_RX).toBe(OVAL_RX);
  });

  it('PROGRESS_RY coincide con el borde del óvalo (no se sale del clip)', () => {
    expect(PROGRESS_RY).toBe(OVAL_RY);
  });

  it('el anillo NO excede el viewBox (rx ≤ 50, ry ≤ 65) → no se recorta en las esquinas', () => {
    // viewBox = 100×130, centro en (50,65). rx ≤ 50 y ry ≤ 65 mantienen el anillo dentro.
    expect(PROGRESS_RX).toBeLessThanOrEqual(50);
    expect(PROGRESS_RY).toBeLessThanOrEqual(65);
  });

  it('PROGRESS_STROKE_WIDTH < 2.0 (trazo fino/minimalista)', () => {
    expect(PROGRESS_STROKE_WIDTH).toBeLessThan(2.0);
  });

  it('TRACK_STROKE_WIDTH < 2.0 (track también fino)', () => {
    expect(TRACK_STROKE_WIDTH).toBeLessThan(2.0);
  });

  it('valores base del clip: OVAL_RX = 50, OVAL_RY = 65', () => {
    expect(OVAL_RX).toBe(50);
    expect(OVAL_RY).toBe(65);
  });
});
