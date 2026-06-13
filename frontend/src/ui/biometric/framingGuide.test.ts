/**
 * Tests para isHintBloqueante (C-65 — biometric-capture-framing-gate).
 *
 * TDD: ciclo RED → GREEN → TRIANGULATE.
 * Especificación (C-65 ajuste post-prueba): TODA advertencia de encuadre es
 * bloqueante — sin_rostro, multiples_rostros, poca_luz, mucha_luz, lejos, cerca
 * y descentrado. El óvalo es referencia dura: estar fuera de él (descentrado)
 * también detiene la evaluación del reto.
 * Sólo null (encuadre correcto) es no-bloqueante.
 */

import { describe, expect, it } from 'vitest';
import { isHintBloqueante, evaluateFraming, isFrontal, headYawAsymmetry } from './framingGuide';
import type { FramingHint, FramingSignals } from './framingGuide';

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

  // ── descentrado ahora BLOQUEA (el óvalo es referencia dura) ───────────────
  it('descentrado → true (bloqueante: fuera del óvalo no avanza)', () => {
    expect(isHintBloqueante('descentrado')).toBe(true);
  });

  // ── no_frontal BLOQUEA (mirá de frente) ───────────────────────────────────
  it('no_frontal → true (bloqueante: cabeza girada no avanza)', () => {
    expect(isHintBloqueante('no_frontal')).toBe(true);
  });

  // ── null → no bloqueante (único caso que deja avanzar) ────────────────────
  it('null → false (sin hint, encuadre correcto, no bloquea)', () => {
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
    'descentrado',
    'no_frontal',
  ];

  // Sólo null (encuadre correcto) deja avanzar el reto.
  const INFORMATIVOS: Array<FramingHint | null> = [null];

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

// ---------------------------------------------------------------------------
// C-67: umbrales RELAJADOS (los de C-65 falseaban: pedían recentrar/acercar aun
// estando bien). Centrado: |0.5-cx| > 0.16 (x) o |0.5-cy| > 0.20 (y) → descentrado.
// Tamaño: bbox < 0.22 → lejos; bbox > 0.72 → cerca.
// Estos tests FIJAN la nueva calibración.
// ---------------------------------------------------------------------------

describe('evaluateFraming — umbrales relajados (centrado + tamaño)', () => {
  // Señal base con todo OK; cada test pisa sólo lo que quiere probar.
  const ok: FramingSignals = {
    faceCount: 1,
    luminanceAvg: 120, // luz OK (entre 48 y 238)
    faceBboxWidth: 0.4, // tamaño OK (entre 0.22 y 0.72)
    faceCenterX: 0.5,
    faceCenterY: 0.5,
  };

  // ── Centrado horizontal ────────────────────────────────────────────────
  it('cx 0.20 fuera de centro (>0.16) → descentrado', () => {
    expect(evaluateFraming({ ...ok, faceCenterX: 0.5 + 0.20 })).toBe('descentrado');
  });

  it('cx 0.12 fuera de centro (<0.16) → null (centrado aceptable)', () => {
    expect(evaluateFraming({ ...ok, faceCenterX: 0.5 + 0.12 })).toBeNull();
  });

  // ── Centrado vertical ──────────────────────────────────────────────────
  it('cy 0.25 fuera de centro (>0.20) → descentrado', () => {
    expect(evaluateFraming({ ...ok, faceCenterY: 0.5 + 0.25 })).toBe('descentrado');
  });

  it('cy 0.13 fuera de centro (<0.20) → null (centrado aceptable)', () => {
    expect(evaluateFraming({ ...ok, faceCenterY: 0.5 + 0.13 })).toBeNull();
  });

  // ── Tamaño (llenar el óvalo) ───────────────────────────────────────────
  it('bbox 0.18 (<0.22) → lejos (la cara no llena el óvalo)', () => {
    expect(evaluateFraming({ ...ok, faceBboxWidth: 0.18 })).toBe('lejos');
  });

  it('bbox 0.4 (entre 0.22 y 0.72) → null (encuadre cómodo)', () => {
    expect(evaluateFraming({ ...ok, faceBboxWidth: 0.4 })).toBeNull();
  });

  it('bbox 0.78 (>0.72) → cerca (demasiado cerca)', () => {
    expect(evaluateFraming({ ...ok, faceBboxWidth: 0.78 })).toBe('cerca');
  });
});

// ---------------------------------------------------------------------------
// C-65: frontalidad = CABEZA DERECHA (pose), NO mirada de ojos. Se mide por la
// asimetría horizontal de la nariz (landmark 1) respecto a las comisuras externas
// de los ojos (33 y 263): ~0 = cabeza de frente. Independiente de a dónde apunten
// los ojos — el alumno mira la PANTALLA, no la cámara, y eso es válido.
// ---------------------------------------------------------------------------

describe('headYawAsymmetry — giro de cabeza por geometría', () => {
  it('nariz centrada entre los ojos → asimetría ~0 (de frente)', () => {
    expect(headYawAsymmetry(0.5, 0.35, 0.65)).toBeCloseTo(0, 5);
  });

  it('nariz corrida hacia un ojo → asimetría alta (cabeza girada)', () => {
    // nariz 0.62, ojos 0.3/0.7 → dA=0.32, dB=0.08 → (0.32-0.08)/0.40 = 0.6
    expect(Math.abs(headYawAsymmetry(0.62, 0.3, 0.7))).toBeGreaterThan(0.3);
  });

  it('es simétrica al lado del giro (signo según dirección)', () => {
    const izq = headYawAsymmetry(0.4, 0.35, 0.65);
    const der = headYawAsymmetry(0.6, 0.35, 0.65);
    expect(Math.sign(izq)).not.toBe(Math.sign(der));
  });
});

describe('isFrontal — cabeza derecha (no mirada)', () => {
  // Construye un array de landmarks con sólo los índices que isFrontal usa (1,33,263).
  const mk = (noseX: number, eyeAX: number, eyeBX: number) => {
    const a: Array<{ x: number }> = new Array(264).fill({ x: 0.5 });
    a[1] = { x: noseX };
    a[33] = { x: eyeAX };
    a[263] = { x: eyeBX };
    return a;
  };

  it('cabeza derecha (nariz centrada) → true, mires donde mires con los ojos', () => {
    expect(isFrontal(mk(0.5, 0.35, 0.65))).toBe(true);
  });

  it('giro leve (tolerante) → true (no forzamos rigidez)', () => {
    // nariz 0.54 → asym ≈ 0.27, dentro del umbral lene
    expect(isFrontal(mk(0.54, 0.35, 0.65))).toBe(true);
  });

  it('cabeza claramente girada → false', () => {
    // nariz 0.62 → asym = 0.8
    expect(isFrontal(mk(0.62, 0.35, 0.65))).toBe(false);
  });

  it('landmarks insuficientes → true (no bloquear por frontalidad sin datos)', () => {
    expect(isFrontal([{ x: 0.5 }])).toBe(true);
  });
});
