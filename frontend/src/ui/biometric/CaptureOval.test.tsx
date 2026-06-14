/**
 * Tests para CaptureOval — anillo de progreso SOBRE LA BANDA BLANCA del óvalo (C-67).
 *
 * TDD. Tras el feedback del dueño, el anillo ya NO va pegado al borde interno del
 * video, sino centrado en la banda blanca que rodea al óvalo (entre el borde del
 * video y el borde externo del marco). Verificamos las CONSTANTES exportadas, que
 * son la fuente de verdad de la geometría (happy-dom no tiene SVG geometry API).
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

describe('CaptureOval — anillo sobre la banda blanca (C-67)', () => {
  it('el anillo va ADENTRO del borde externo (sobre la banda), no en el borde mismo', () => {
    expect(PROGRESS_RX).toBeLessThan(OVAL_RX);
    expect(PROGRESS_RY).toBeLessThan(OVAL_RY);
  });

  it('el anillo NO se mete tan adentro como el borde del video (~4% de banda)', () => {
    // El video queda ~4 unidades (rx) y ~3.9 (ry) adentro del borde externo.
    // El anillo debe quedar ENTRE el borde del video y el externo (en la banda).
    expect(PROGRESS_RX).toBeGreaterThan(OVAL_RX - 4);
    expect(PROGRESS_RY).toBeGreaterThan(OVAL_RY - 4);
  });

  it('el trazo del progreso es marcado (visible) pero no exagerado', () => {
    expect(PROGRESS_STROKE_WIDTH).toBeGreaterThanOrEqual(2);
    expect(PROGRESS_STROKE_WIDTH).toBeLessThanOrEqual(4);
  });

  it('el track tiene el mismo ancho que el progreso (la banda se llena parejo)', () => {
    expect(TRACK_STROKE_WIDTH).toBe(PROGRESS_STROKE_WIDTH);
  });

  it('valores base del borde externo: OVAL_RX = 50, OVAL_RY = 65', () => {
    expect(OVAL_RX).toBe(50);
    expect(OVAL_RY).toBe(65);
  });
});
