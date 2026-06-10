/**
 * Tests para isHintBloqueante (C-65 — biometric-capture-framing-gate).
 *
 * TDD: ciclo RED → GREEN → TRIANGULATE.
 * Especificación: los hints bloqueantes son sin_rostro, multiples_rostros,
 * poca_luz, mucha_luz, lejos, cerca.
 * El hint informativo es descentrado.
 * null también es no-bloqueante.
 */

import { describe, expect, it } from 'vitest';
import { isHintBloqueante } from './framingGuide';
import type { FramingHint } from './framingGuide';

// ---------------------------------------------------------------------------
// 2.1 RED — tests escritos antes de la implementación
// ---------------------------------------------------------------------------

describe('isHintBloqueante', () => {
  // ── Hints bloqueantes ─────────────────────────────────────────────────────
  it('sin_rostro → true (bloqueante)', () => {
    expect(isHintBloqueante('sin_rostro')).toBe(true);
  });

  it('multiples_rostros → true (bloqueante)', () => {
    expect(isHintBloqueante('multiples_rostros')).toBe(true);
  });

  it('poca_luz → true (bloqueante)', () => {
    expect(isHintBloqueante('poca_luz')).toBe(true);
  });

  it('mucha_luz → true (bloqueante)', () => {
    expect(isHintBloqueante('mucha_luz')).toBe(true);
  });

  it('lejos → true (bloqueante)', () => {
    expect(isHintBloqueante('lejos')).toBe(true);
  });

  it('cerca → true (bloqueante)', () => {
    expect(isHintBloqueante('cerca')).toBe(true);
  });

  // ── Hints informativos (no bloqueantes) ───────────────────────────────────
  it('descentrado → false (informativo, no bloqueante)', () => {
    expect(isHintBloqueante('descentrado')).toBe(false);
  });

  // ── null → no bloqueante ──────────────────────────────────────────────────
  it('null → false (sin hint, no bloquea)', () => {
    expect(isHintBloqueante(null)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 2.3 TRIANGULATE — tabla completa de todos los hints + null
// ---------------------------------------------------------------------------

describe('isHintBloqueante — tabla completa', () => {
  const BLOQUEANTES: FramingHint[] = [
    'sin_rostro',
    'multiples_rostros',
    'poca_luz',
    'mucha_luz',
    'lejos',
    'cerca',
  ];

  const INFORMATIVOS: Array<FramingHint | null> = ['descentrado', null];

  for (const hint of BLOQUEANTES) {
    it(`${hint} es bloqueante → true`, () => {
      expect(isHintBloqueante(hint)).toBe(true);
    });
  }

  for (const hint of INFORMATIVOS) {
    it(`${String(hint)} es informativo/null → false`, () => {
      expect(isHintBloqueante(hint)).toBe(false);
    });
  }
});
