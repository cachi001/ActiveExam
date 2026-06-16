/**
 * Tests de helpers.ts — foco en la lógica de umbral alto sembrable (FIX C-68).
 *
 * TDD cycle:
 *  RED  → tests escritos para getUmbralAlto/seedUmbralAlto/nivelRiesgo antes de impl.
 *  GREEN → implementación mínima: let _umbralAlto + seedUmbralAlto + getUmbralAlto.
 *  TRIANGULATE → casos con umbral default, umbral sembrado, y bordes exactos.
 *  REFACTOR → helpers ya limpios.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import {
  getUmbralAlto,
  seedUmbralAlto,
  resetUmbralAlto,
  nivelRiesgo,
  SCORE_UMBRAL_MEDIO,
} from './helpers';

describe('getUmbralAlto / seedUmbralAlto', () => {
  beforeEach(() => {
    resetUmbralAlto();
  });

  // --- Default ---

  it('devuelve 70 por defecto (antes de sembrar)', () => {
    expect(getUmbralAlto()).toBe(70);
  });

  // Triangulación: llamar dos veces sin sembrar sigue devolviendo 70
  it('es estable: múltiples calls sin sembrar devuelven 70', () => {
    expect(getUmbralAlto()).toBe(70);
    expect(getUmbralAlto()).toBe(70);
  });

  // --- Sembrar un valor ---

  it('devuelve el valor sembrado por seedUmbralAlto', () => {
    seedUmbralAlto(80);
    expect(getUmbralAlto()).toBe(80);
  });

  // Triangulación: otro valor sembrado
  it('funciona con cualquier valor sembrado', () => {
    seedUmbralAlto(50);
    expect(getUmbralAlto()).toBe(50);
  });

  // --- Idempotencia: sobrescribir ---

  it('una segunda siembra sobrescribe la primera', () => {
    seedUmbralAlto(80);
    seedUmbralAlto(60);
    expect(getUmbralAlto()).toBe(60);
  });

  // --- Reset ---

  it('resetUmbralAlto vuelve al default 70', () => {
    seedUmbralAlto(90);
    resetUmbralAlto();
    expect(getUmbralAlto()).toBe(70);
  });
});

describe('nivelRiesgo usa getUmbralAlto (umbral vivo, no fijo)', () => {
  beforeEach(() => {
    resetUmbralAlto();
  });

  // Con umbral default 70

  it('score igual al umbral (70) → alto', () => {
    expect(nivelRiesgo(70)).toBe('alto');
  });

  it('score por encima del umbral (71) → alto', () => {
    expect(nivelRiesgo(71)).toBe('alto');
  });

  it('score por debajo del umbral (69) → medio (si ≥ SCORE_UMBRAL_MEDIO)', () => {
    expect(nivelRiesgo(69)).toBe('medio');
  });

  it('score menor al umbral medio → bajo', () => {
    expect(nivelRiesgo(SCORE_UMBRAL_MEDIO - 1)).toBe('bajo');
  });

  // Con umbral sembrado desde config (ej. 60)

  it('con umbral sembrado en 60, score 60 → alto', () => {
    seedUmbralAlto(60);
    expect(nivelRiesgo(60)).toBe('alto');
  });

  it('con umbral sembrado en 60, score 59 → medio', () => {
    seedUmbralAlto(60);
    expect(nivelRiesgo(59)).toBe('medio');
  });

  // Triangulación: umbral sembrado en 85

  it('con umbral sembrado en 85, score 84 no es alto', () => {
    seedUmbralAlto(85);
    expect(nivelRiesgo(84)).toBe('medio');
  });

  it('con umbral sembrado en 85, score 85 → alto', () => {
    seedUmbralAlto(85);
    expect(nivelRiesgo(85)).toBe('alto');
  });
});
