import { describe, it, expect } from 'vitest';
import { esIdInstitucionalSintetico, legajoVisible } from './legajo';

describe('legajo', () => {
  it('detecta el id sintético del JIT LTI', () => {
    expect(esIdInstitucionalSintetico('lti:1:8')).toBe(true);
    expect(esIdInstitucionalSintetico('lti:deploy-xyz:sub-123')).toBe(true);
  });

  it('un legajo real no es sintético', () => {
    expect(esIdInstitucionalSintetico('LEG-4521')).toBe(false);
    expect(esIdInstitucionalSintetico('12345')).toBe(false);
  });

  it('legajoVisible oculta el id sintético y vacío', () => {
    expect(legajoVisible('lti:1:8')).toBeNull();
    expect(legajoVisible('')).toBeNull();
    expect(legajoVisible(null)).toBeNull();
    expect(legajoVisible(undefined)).toBeNull();
  });

  it('legajoVisible devuelve el legajo real tal cual', () => {
    expect(legajoVisible('LEG-4521')).toBe('LEG-4521');
  });
});
