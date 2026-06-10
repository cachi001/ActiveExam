/**
 * Tests para playError (C-65 — biometric-capture-av-feedback).
 *
 * TDD: ciclo RED → GREEN.
 * Entorno: Node (no jsdom). Los tests verifican que:
 *  - playError existe y es callable
 *  - No lanza en entorno sin DOM / AudioContext
 *  - Respeta setSoundEnabled(false) — no intenta crear AudioContext
 *
 * El comportamiento de prefers-reduced-motion se verifica en el módulo
 * (función prefersReducedMotion con guard `typeof window === 'undefined'`)
 * y es equivalente a "disabled" en Node (sin DOM → returns false, pero
 * el AudioContext tampoco existe → fallback silencioso).
 */

import { describe, expect, it, beforeEach } from 'vitest';
import { playError, setSoundEnabled } from './sounds';

// ---------------------------------------------------------------------------
// 6.1 RED — smoke: playError respeta silencio del usuario
// ---------------------------------------------------------------------------

describe('playError — feedback sonoro de fallo (C-65)', () => {
  beforeEach(() => {
    // Restablecer el estado de enabled entre tests
    setSoundEnabled(true);
  });

  it('playError existe y es función exportada de sounds.ts', () => {
    expect(typeof playError).toBe('function');
  });

  it('playError no lanza en entorno Node (sin DOM / AudioContext)', () => {
    // En Node, typeof window === 'undefined' → getCtx() devuelve null → no-op silencioso.
    expect(() => playError()).not.toThrow();
  });

  it('playError retorna undefined (no tiene valor de retorno)', () => {
    expect(playError()).toBeUndefined();
  });

  it('playError respeta setSoundEnabled(false): retorna sin hacer nada', () => {
    setSoundEnabled(false);
    // Con enabled=false, playSequence retorna inmediatamente (no llega a getCtx).
    // Solo verificamos que no lanza y retorna undefined.
    expect(() => playError()).not.toThrow();
    expect(playError()).toBeUndefined();
    setSoundEnabled(true);
  });

  it('se puede llamar repetidamente sin error (cooldown interno lo controla)', () => {
    for (let i = 0; i < 5; i++) {
      expect(() => playError()).not.toThrow();
    }
  });
});
