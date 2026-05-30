/**
 * Tests del backoff exponencial + jitter 20% (C-14, RN-HB-05). Formato Vitest.
 *
 * Verifica: intervalos crecientes (exponencial acotado), jitter +-20% acotado y
 * distribuido, saturacion en el techo. ``random`` inyectado para determinismo.
 */

import { describe, expect, it } from "vitest";

import {
  backoffBounds,
  backoffDelayMs,
  DEFAULT_MAX_DELAY_MS,
  JITTER_FRACTION,
} from "./reconnectBackoff";

describe("intervalos crecientes (exponencial)", () => {
  it("crece exponencialmente intento a intento (sin jitter, random=0.5)", () => {
    const opts = { baseDelayMs: 1000, maxDelayMs: 1_000_000, random: () => 0.5 };
    // random=0.5 -> factor = 1 (jitter neutro) -> retardo nominal exacto
    expect(backoffDelayMs(0, opts)).toBe(1000);
    expect(backoffDelayMs(1, opts)).toBe(2000);
    expect(backoffDelayMs(2, opts)).toBe(4000);
    expect(backoffDelayMs(3, opts)).toBe(8000);
  });

  it("satura en el techo maxDelayMs", () => {
    const opts = { baseDelayMs: 1000, maxDelayMs: 5000, random: () => 0.5 };
    expect(backoffDelayMs(10, opts)).toBe(5000);
  });

  it("usa el techo por defecto de 30s", () => {
    expect(DEFAULT_MAX_DELAY_MS).toBe(30_000);
    const v = backoffDelayMs(20, { random: () => 0.5 });
    expect(v).toBe(30_000);
  });
});

describe("jitter del 20%", () => {
  it("aplica el jitter minimo con random=0 (-20%)", () => {
    const v = backoffDelayMs(2, { baseDelayMs: 1000, maxDelayMs: 1e9, random: () => 0 });
    expect(v).toBe(Math.round(4000 * (1 - JITTER_FRACTION))); // 3200
  });

  it("aplica el jitter maximo con random cercano a 1 (+20%)", () => {
    const v = backoffDelayMs(2, { baseDelayMs: 1000, maxDelayMs: 1e9, random: () => 0.999999 });
    expect(v).toBeCloseTo(4000 * (1 + JITTER_FRACTION), -1); // ~4800
  });

  it("todos los retardos caen dentro de los bounds +-20%", () => {
    const opts = { baseDelayMs: 1000, maxDelayMs: 1e9 };
    for (let attempt = 0; attempt < 6; attempt++) {
      const { min, max } = backoffBounds(attempt, opts);
      for (let i = 0; i < 50; i++) {
        const v = backoffDelayMs(attempt, { ...opts, random: Math.random });
        expect(v).toBeGreaterThanOrEqual(min);
        expect(v).toBeLessThanOrEqual(max + 1);
      }
    }
  });

  it("distribuye: muchos clientes no obtienen el mismo retardo (no thundering herd)", () => {
    const opts = { baseDelayMs: 1000, maxDelayMs: 1e9, random: Math.random };
    const values = new Set<number>();
    for (let i = 0; i < 200; i++) values.add(backoffDelayMs(3, opts));
    // con jitter real, la dispersion produce muchos valores distintos
    expect(values.size).toBeGreaterThan(50);
  });
});

describe("robustez", () => {
  it("nunca devuelve negativo y trata attempt<0 como 0", () => {
    expect(backoffDelayMs(-5, { random: () => 0 })).toBeGreaterThanOrEqual(0);
    expect(backoffDelayMs(-5, { random: () => 0.5 })).toBe(backoffDelayMs(0, { random: () => 0.5 }));
  });
});
