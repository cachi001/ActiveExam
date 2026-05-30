/**
 * Tests del calculo de embedding desde landmarks (C-09, embedding-computation).
 * Formato Vitest.
 */

import { describe, expect, it } from "vitest";

import { embeddingFromLandmarks } from "./MediaPipeVisionEngine";

describe("embedding desde landmarks", () => {
  it("devuelve un vector normalizado (norma ~1) y 3 valores por landmark", () => {
    const emb = embeddingFromLandmarks([
      { x: 0.1, y: 0.2, z: 0.0 },
      { x: 0.4, y: 0.5, z: 0.1 },
    ]);
    expect(emb.length).toBe(6); // 2 landmarks * 3 coords
    const norm = Math.sqrt(emb.reduce((s, v) => s + v * v, 0));
    expect(norm).toBeCloseTo(1, 6);
  });

  it("es invariante a la traslacion (centra la geometria)", () => {
    const a = embeddingFromLandmarks([
      { x: 0, y: 0, z: 0 },
      { x: 1, y: 0, z: 0 },
    ]);
    const b = embeddingFromLandmarks([
      { x: 10, y: 10, z: 5 },
      { x: 11, y: 10, z: 5 },
    ]);
    for (let i = 0; i < a.length; i += 1) {
      expect(a[i]).toBeCloseTo(b[i], 6);
    }
  });

  it("sin landmarks devuelve vector vacio", () => {
    expect(embeddingFromLandmarks([])).toEqual([]);
  });
});
