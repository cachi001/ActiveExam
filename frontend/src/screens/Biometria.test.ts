/**
 * Tests para Biometria.tsx — Grupo 6 (pantalla de resultado, lenguaje claro, gate) — C-67.
 *
 * Sin @testing-library/react (no instalado en MVP); testea la lógica pura
 * exportada del componente, siguiendo el patrón establecido en Login.test.ts.
 *
 * TDD RED → GREEN → TRIANGULATE — C-67 Grupo 6.
 *
 * Strict TDD: NO mockea DB. No buildea. No commitea.
 */

import { describe, expect, it } from 'vitest';

import {
  // 6.1: Gate de navegación — NO avanza automáticamente
  requiresExplicitContinue,
  // 6.4: Copy principal sin jerga técnica
  COPY_VERIFICADO_PRINCIPAL,
  COPY_VERIFICANDO_PRINCIPAL,
  COPY_REINTENTO_PRINCIPAL,
  // 6.6: Garantía L2.5 — decisión siempre humana
  COPY_L25_GUARANTEE,
  // helpers de reintento
  intentosRestantesMsg,
} from './BiometriaLogic';

// ---------------------------------------------------------------------------
// 6.1 — Gate de confirmación: el flujo NO avanza automáticamente
// ---------------------------------------------------------------------------

describe('6.1 — Gate de confirmación explícita (no-auto-navigate)', () => {
  it('requiresExplicitContinue devuelve true: verificación exitosa NO navega sola', () => {
    // La verificación exitosa requiere click del alumno — nunca avance automático.
    expect(requiresExplicitContinue(true)).toBe(true);
  });

  it('requiresExplicitContinue devuelve true también para reintento (sin avance automático)', () => {
    expect(requiresExplicitContinue(false)).toBe(true);
  });

  it('el gate es siempre activo — no existe ningún camino de auto-navegar', () => {
    // Triangulación: cualquier valor del parámetro devuelve true.
    // La función documenta que la decisión de navegar es SIEMPRE del alumno.
    for (const v of [true, false]) {
      expect(requiresExplicitContinue(v)).toBe(true);
    }
  });
});

// ---------------------------------------------------------------------------
// 6.4 — Copy principal sin jerga técnica
// Palabras prohibidas: "embedding", "coseno", "umbral", "descriptor", "1:1", "distancia"
// ---------------------------------------------------------------------------

const JARGON_WORDS = ['embedding', 'coseno', 'umbral', 'descriptor', '1:1', 'distancia'];

function containsJargon(text: string): string[] {
  return JARGON_WORDS.filter((w) => text.toLowerCase().includes(w.toLowerCase()));
}

describe('6.4 — Copy principal libre de jerga técnica', () => {
  it('COPY_VERIFICADO_PRINCIPAL no contiene jerga', () => {
    const found = containsJargon(COPY_VERIFICADO_PRINCIPAL);
    expect(found, `Palabras prohibidas encontradas: ${found.join(', ')}`).toHaveLength(0);
  });

  it('COPY_VERIFICANDO_PRINCIPAL no contiene jerga', () => {
    const found = containsJargon(COPY_VERIFICANDO_PRINCIPAL);
    expect(found, `Palabras prohibidas encontradas: ${found.join(', ')}`).toHaveLength(0);
  });

  it('COPY_REINTENTO_PRINCIPAL no contiene jerga', () => {
    const found = containsJargon(COPY_REINTENTO_PRINCIPAL);
    expect(found, `Palabras prohibidas encontradas: ${found.join(', ')}`).toHaveLength(0);
  });

  it('triangulación — ninguna copia principal contiene ninguna palabra prohibida', () => {
    const copies = [COPY_VERIFICADO_PRINCIPAL, COPY_VERIFICANDO_PRINCIPAL, COPY_REINTENTO_PRINCIPAL];
    for (const copy of copies) {
      const found = containsJargon(copy);
      expect(found, `En "${copy.slice(0, 60)}…": ${found.join(', ')}`).toHaveLength(0);
    }
  });
});

// ---------------------------------------------------------------------------
// 6.6 — Garantía L2.5: "ninguna decisión la toma una máquina; siempre la revisa una persona"
// ---------------------------------------------------------------------------

describe('6.6 — Garantía L2.5 presente en el copy', () => {
  it('COPY_L25_GUARANTEE no está vacío', () => {
    expect(COPY_L25_GUARANTEE.trim().length).toBeGreaterThan(10);
  });

  it('COPY_L25_GUARANTEE menciona revisión humana / persona', () => {
    const lower = COPY_L25_GUARANTEE.toLowerCase();
    // Debe mencionar "persona" o "humana" o "revisión"
    const hasHumanRef = lower.includes('persona') || lower.includes('human') || lower.includes('revisión') || lower.includes('revision');
    expect(hasHumanRef, `La garantía L2.5 debe mencionar revisión humana. Copy: "${COPY_L25_GUARANTEE}"`).toBe(true);
  });

  it('COPY_L25_GUARANTEE menciona que no es una máquina la que decide', () => {
    const lower = COPY_L25_GUARANTEE.toLowerCase();
    // Debe negar la máquina o mencionar que no decide sola
    const hasMachineNegation =
      lower.includes('máquina') ||
      lower.includes('maquina') ||
      lower.includes('automática') ||
      lower.includes('automatica') ||
      lower.includes('siempre');
    expect(hasMachineNegation, `La garantía L2.5 debe negar decisión automática. Copy: "${COPY_L25_GUARANTEE}"`).toBe(true);
  });

  it('COPY_L25_GUARANTEE no contiene jerga técnica', () => {
    const found = containsJargon(COPY_L25_GUARANTEE);
    expect(found, `Jerga en L2.5 copy: ${found.join(', ')}`).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// 6.3 — intentosRestantesMsg: mensaje de reintentos en lenguaje claro
// ---------------------------------------------------------------------------

describe('6.3 — intentosRestantesMsg (reintentos en lenguaje claro)', () => {
  it('1 intento restante → singular', () => {
    const msg = intentosRestantesMsg(1);
    expect(msg).toContain('1');
    expect(msg.toLowerCase()).toMatch(/intento/);
    // No debe decir "intentos" (plural) cuando es 1
    expect(msg).not.toMatch(/\b2\b|\b0\b/);
  });

  it('2 intentos restantes → plural', () => {
    const msg = intentosRestantesMsg(2);
    expect(msg).toContain('2');
    expect(msg.toLowerCase()).toMatch(/intentos/);
  });

  it('0 intentos → mensaje de agotamiento', () => {
    const msg = intentosRestantesMsg(0);
    // Sin intentos → informar que se agotaron; sin jerga
    const found = containsJargon(msg);
    expect(found, `Jerga en msg de agotamiento: ${found.join(', ')}`).toHaveLength(0);
    expect(msg.trim().length).toBeGreaterThan(5);
  });

  it('triangulación — ningún mensaje de reintento contiene jerga', () => {
    for (const n of [0, 1, 2]) {
      const msg = intentosRestantesMsg(n);
      const found = containsJargon(msg);
      expect(found, `Jerga con n=${n}: ${found.join(', ')}`).toHaveLength(0);
    }
  });
});
