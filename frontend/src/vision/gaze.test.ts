/**
 * Tests de la estimacion de mirada desde el iris (C-11). Formato Vitest.
 */

import { describe, expect, it } from "vitest";

import { gazeFromIris } from "./MediaPipeVisionEngine";

describe("gazeFromIris", () => {
  it("iris centrado entre las esquinas de los ojos -> mirada al frente (0,0)", () => {
    const g = gazeFromIris({ x: 0.5, y: 0.5 }, { x: 0.4, y: 0.5 }, { x: 0.6, y: 0.5 });
    expect(g.x).toBeCloseTo(0, 6);
    expect(g.y).toBeCloseTo(0, 6);
  });

  it("iris desplazado a la derecha -> gaze.x positivo", () => {
    const g = gazeFromIris({ x: 0.58, y: 0.5 }, { x: 0.4, y: 0.5 }, { x: 0.6, y: 0.5 });
    expect(g.x).toBeGreaterThan(0);
  });

  it("clampea a -1..1 ante desplazamientos extremos", () => {
    const g = gazeFromIris({ x: 2, y: -2 }, { x: 0.4, y: 0.5 }, { x: 0.6, y: 0.5 });
    expect(g.x).toBeLessThanOrEqual(1);
    expect(g.y).toBeGreaterThanOrEqual(-1);
  });
});
