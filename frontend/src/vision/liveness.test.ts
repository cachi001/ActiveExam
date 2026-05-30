/**
 * Tests de la logica de liveness hibrido del cliente (C-09, DD-18).
 *
 * Formato Vitest (stack Vite). Cubre: retos aleatorios (cantidad/aleatoriedad),
 * gate de liveness (pasa/falla, camara virtual), deteccion de camara virtual y
 * derivacion de senales pasivas (foto plana no pasa).
 */

import { describe, expect, it } from "vitest";

import {
  ACTIVE_CHALLENGES,
  aggregateFaceCount,
  clientLivenessOk,
  derivePassiveSignals,
  detectVirtualCamera,
  MAX_ACTIVE_CHALLENGES,
  passivePassed,
  pickActiveChallenges,
} from "./liveness";

const PASSIVE_OK = {
  parpadeo_detectado: true,
  micro_movimientos: true,
  profundidad_3d_coherente: true,
};

describe("retos activos aleatorios", () => {
  it("elige entre 1 y 2 retos del catalogo", () => {
    const chosen = pickActiveChallenges(2);
    expect(chosen.length).toBeGreaterThanOrEqual(1);
    expect(chosen.length).toBeLessThanOrEqual(MAX_ACTIVE_CHALLENGES);
    for (const c of chosen) expect(ACTIVE_CHALLENGES).toContain(c);
  });

  it("no repite retos en un mismo intento", () => {
    const chosen = pickActiveChallenges(2, mkRng([0, 0]));
    expect(new Set(chosen).size).toBe(chosen.length);
  });

  it("es aleatorio: distinto rng -> distinta seleccion", () => {
    const a = pickActiveChallenges(1, mkRng([0]));
    const b = pickActiveChallenges(1, mkRng([0.99]));
    expect(a[0]).not.toBe(b[0]);
  });
});

describe("gate de liveness del cliente", () => {
  it("pasa con pasivo OK y reto resuelto", () => {
    expect(
      clientLivenessOk({
        passive: PASSIVE_OK,
        requested: ["parpadear"],
        solved: ["parpadear"],
        virtualCameraDetected: false,
      }),
    ).toBe(true);
  });

  it("falla si el reto no fue resuelto", () => {
    expect(
      clientLivenessOk({
        passive: PASSIVE_OK,
        requested: ["girar_izquierda"],
        solved: [],
        virtualCameraDetected: false,
      }),
    ).toBe(false);
  });

  it("falla si se detecta camara virtual (capa de defensa, DD-18)", () => {
    expect(
      clientLivenessOk({
        passive: PASSIVE_OK,
        requested: ["parpadear"],
        solved: ["parpadear"],
        virtualCameraDetected: true,
      }),
    ).toBe(false);
  });
});

describe("senales pasivas", () => {
  it("una foto plana (varianza ~0, sin profundidad) no pasa el pasivo", () => {
    const signals = derivePassiveSignals({
      blinkVariance: 0,
      motionVariance: 0,
      depthRange: 0,
    });
    expect(passivePassed(signals)).toBe(false);
  });

  it("una persona viva (varianza y profundidad reales) pasa el pasivo", () => {
    const signals = derivePassiveSignals({
      blinkVariance: 0.05,
      motionVariance: 0.002,
      depthRange: 0.1,
    });
    expect(passivePassed(signals)).toBe(true);
  });
});

describe("deteccion de camara virtual", () => {
  it("detecta un feed loop demasiado estable", () => {
    expect(
      detectVirtualCamera({
        interFramePixelVariance: 0,
        frameRateJitter: 0,
        faceCountStability: 1,
      }),
    ).toBe(true);
  });

  it("no marca una camara fisica con jitter normal", () => {
    expect(
      detectVirtualCamera({
        interFramePixelVariance: 0.3,
        frameRateJitter: 0.02,
        faceCountStability: 0.8,
      }),
    ).toBe(false);
  });
});

describe("conteo de rostros", () => {
  it("toma el maximo de rostros del clip (multiples rostros)", () => {
    expect(
      aggregateFaceCount([
        { landmarks: [], face_count: 1 },
        { landmarks: [], face_count: 2 },
      ]),
    ).toBe(2);
  });
});

/** RNG determinista a partir de una lista de valores. */
function mkRng(values: number[]): () => number {
  let i = 0;
  return () => values[i++ % values.length];
}
