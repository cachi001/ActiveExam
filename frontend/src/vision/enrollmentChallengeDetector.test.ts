/**
 * Tests del motor de evaluacion relativa de retos secuenciales (C-54).
 *
 * TDD: estos tests se escriben ANTES de la implementacion.
 * Cubren: evaluateChallengeRelative(), framesMinForChallengeSeq(),
 *         validacion del baseline y aleatorización Fisher-Yates.
 *
 * Task 11.1 — evaluateChallengeRelative: parpadear
 * Task 11.2 — evaluateChallengeRelative: sonreir
 * Task 11.3 — evaluateChallengeRelative: girar_cabeza DIRECCIONAL
 * Task 11.4 — framesMinForChallengeSeq
 * Task 11.5 — validacion del baseline
 * Task 11.6 — aleatorización Fisher-Yates
 */

import { describe, expect, it } from "vitest";

import {
  evaluateChallengeRelative,
  framesMinForChallengeSeq,
  BLINK_RELATIVE_FACTOR,
  SMILE_RELATIVE_FACTOR,
  GAZE_TURN_THRESHOLD_ADJUSTED,
  FRAMES_MIN_BLINK_SEQ,
  FRAMES_MIN_TURN_SEQ,
  FRAMES_MIN_SMILE_SEQ,
} from "./enrollmentChallengeDetector";

import type { BaselineMetrics, TurnDirection } from "./liveness";
import type { FaceLandmark } from "./VisionEngine";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Crea un array de landmarks minimo para los tests.
 * Inicializa todos los landmarks necesarios a 0, luego sobreescribe los indices dados.
 */
function makeLandmarks(overrides: Record<number, Partial<FaceLandmark>>): FaceLandmark[] {
  const lm: FaceLandmark[] = Array.from({ length: 468 }, () => ({ x: 0, y: 0, z: 0 }));
  for (const [idx, vals] of Object.entries(overrides)) {
    lm[Number(idx)] = { x: 0, y: 0, z: 0, ...vals };
  }
  return lm;
}

const BASE_GAZE = { x: 0, y: 0 };

/** Baseline neutral de referencia para los tests. */
const BASELINE_NEUTRAL: BaselineMetrics = {
  blinkOpenness: 0.060, // apertura normal del ojo en reposo
  smileWidth: 0.10,     // ancho de boca en reposo
  gazeX: 0,
};

// ---------------------------------------------------------------------------
// Task 11.1: evaluateChallengeRelative — parpadear
// ---------------------------------------------------------------------------

describe("evaluateChallengeRelative — parpadear (Task 11.1)", () => {
  it("caso positivo: ojo bien cerrado sobre baseline -> true", () => {
    // baselineBlinkOpenness = 0.060
    // Para parpadear: openness < 0.060 * 0.45 = 0.027
    // openness = |lm[159].y - lm[145].y| = |0.020 - 0| = 0.020 < 0.027 -> true
    const lm = makeLandmarks({
      159: { y: 0.020 }, // párpado superior
      145: { y: 0 },     // párpado inferior
    });
    expect(evaluateChallengeRelative("parpadear", lm, BASE_GAZE, BASELINE_NEUTRAL)).toBe(true);
  });

  it("caso negativo: variacion natural (ojo casi abierto) -> false", () => {
    // openness = 0.050, threshold = 0.060 * 0.45 = 0.027 -> 0.050 > 0.027 -> false
    const lm = makeLandmarks({
      159: { y: 0.050 },
      145: { y: 0 },
    });
    expect(evaluateChallengeRelative("parpadear", lm, BASE_GAZE, BASELINE_NEUTRAL)).toBe(false);
  });

  it("caso limite: exactamente en el threshold -> false (no cumple <)", () => {
    // openness = 0.027, threshold = 0.027 -> 0.027 < 0.027 es false
    const lm = makeLandmarks({
      159: { y: 0.027 },
      145: { y: 0 },
    });
    expect(evaluateChallengeRelative("parpadear", lm, BASE_GAZE, BASELINE_NEUTRAL)).toBe(false);
  });

  it("landmarks insuficientes (menos de 160) -> false", () => {
    const lm = makeLandmarks({}).slice(0, 100);
    expect(evaluateChallengeRelative("parpadear", lm, BASE_GAZE, BASELINE_NEUTRAL)).toBe(false);
  });

  it("baseline null -> retorna false (no hay referencia)", () => {
    const lm = makeLandmarks({
      159: { y: 0.005 }, // ojo muy cerrado
      145: { y: 0 },
    });
    expect(evaluateChallengeRelative("parpadear", lm, BASE_GAZE, null)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Task 11.2: evaluateChallengeRelative — sonreír
// ---------------------------------------------------------------------------

describe("evaluateChallengeRelative — sonreír (Task 11.2)", () => {
  it("caso positivo: sonrisa genuina (ancho supera factor 1.25) -> true", () => {
    // baselineSmileWidth = 0.10
    // threshold = 0.10 * 1.25 = 0.125
    // smileWidth = |lm[291].x - lm[61].x| = |0.14 - 0| = 0.14 > 0.125 -> true
    const lm = makeLandmarks({
      61:  { x: 0 },
      291: { x: 0.14 },
    });
    expect(evaluateChallengeRelative("sonreír", lm, BASE_GAZE, BASELINE_NEUTRAL)).toBe(true);
  });

  it("caso negativo: cara en reposo (variacion natural menor al factor) -> false", () => {
    // smileWidth = 0.105, threshold = 0.125 -> false
    const lm = makeLandmarks({
      61:  { x: 0 },
      291: { x: 0.105 },
    });
    expect(evaluateChallengeRelative("sonreír", lm, BASE_GAZE, BASELINE_NEUTRAL)).toBe(false);
  });

  it("caso baseline con smileWidth alto: alumno sonreia en reposo -> falso positivo evitado", () => {
    // Si el baseline captura smileWidth = 0.14 (alumno sonreia al baseline),
    // el threshold sube a 0.14 * 1.25 = 0.175.
    // Con smileWidth = 0.15 -> 0.15 < 0.175 -> false (correcto: no detecta sonrisa genuina)
    const baselineConSonrisa: BaselineMetrics = {
      blinkOpenness: 0.060,
      smileWidth: 0.14,
      gazeX: 0,
    };
    const lm = makeLandmarks({
      61:  { x: 0 },
      291: { x: 0.15 },
    });
    expect(evaluateChallengeRelative("sonreír", lm, BASE_GAZE, baselineConSonrisa)).toBe(false);
  });

  it("landmarks insuficientes (menos de 292) -> false", () => {
    const lm = makeLandmarks({}).slice(0, 200);
    expect(evaluateChallengeRelative("sonreír", lm, BASE_GAZE, BASELINE_NEUTRAL)).toBe(false);
  });

  it("baseline null -> retorna false", () => {
    const lm = makeLandmarks({
      61:  { x: 0 },
      291: { x: 0.20 },
    });
    expect(evaluateChallengeRelative("sonreír", lm, BASE_GAZE, null)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Task 11.3: evaluateChallengeRelative — girar_cabeza DIRECCIONAL
// ---------------------------------------------------------------------------

describe("evaluateChallengeRelative — girar_cabeza DIRECCIONAL (Task 11.3)", () => {
  const lmVacio = makeLandmarks({});

  describe("con turnDirection = 'izquierda'", () => {
    const dir: TurnDirection = "izquierda";

    it("gaze.x = +0.25 -> true (giro correcto hacia izquierda percibida)", () => {
      expect(evaluateChallengeRelative("girar_cabeza", lmVacio, { x: 0.25, y: 0 }, BASELINE_NEUTRAL, dir)).toBe(true);
    });

    it("gaze.x = -0.25 -> false (giro en direccion equivocada)", () => {
      expect(evaluateChallengeRelative("girar_cabeza", lmVacio, { x: -0.25, y: 0 }, BASELINE_NEUTRAL, dir)).toBe(false);
    });

    it("gaze.x = 0 -> false (mirando al frente)", () => {
      expect(evaluateChallengeRelative("girar_cabeza", lmVacio, { x: 0, y: 0 }, BASELINE_NEUTRAL, dir)).toBe(false);
    });

    it("gaze.x exactamente en threshold (0.22) -> false (no cumple >)", () => {
      expect(evaluateChallengeRelative("girar_cabeza", lmVacio, { x: GAZE_TURN_THRESHOLD_ADJUSTED, y: 0 }, BASELINE_NEUTRAL, dir)).toBe(false);
    });

    it("gaze.x justo encima del threshold (0.221) -> true", () => {
      expect(evaluateChallengeRelative("girar_cabeza", lmVacio, { x: 0.221, y: 0 }, BASELINE_NEUTRAL, dir)).toBe(true);
    });
  });

  describe("con turnDirection = 'derecha'", () => {
    const dir: TurnDirection = "derecha";

    it("gaze.x = -0.25 -> true (giro correcto hacia derecha percibida)", () => {
      expect(evaluateChallengeRelative("girar_cabeza", lmVacio, { x: -0.25, y: 0 }, BASELINE_NEUTRAL, dir)).toBe(true);
    });

    it("gaze.x = +0.25 -> false (giro en direccion equivocada)", () => {
      expect(evaluateChallengeRelative("girar_cabeza", lmVacio, { x: 0.25, y: 0 }, BASELINE_NEUTRAL, dir)).toBe(false);
    });

    it("gaze.x = 0 -> false (mirando al frente)", () => {
      expect(evaluateChallengeRelative("girar_cabeza", lmVacio, { x: 0, y: 0 }, BASELINE_NEUTRAL, dir)).toBe(false);
    });
  });

  it("sin turnDirection (undefined) -> false por defecto (no se puede evaluar sin direccion)", () => {
    expect(evaluateChallengeRelative("girar_cabeza", lmVacio, { x: 0.5, y: 0 }, BASELINE_NEUTRAL, undefined)).toBe(false);
  });

  it("baseline null con giro correcto -> true (el giro no usa baseline)", () => {
    // El reto girar_cabeza usa umbral absoluto (no relativo al baseline)
    expect(evaluateChallengeRelative("girar_cabeza", lmVacio, { x: 0.30, y: 0 }, null, "izquierda")).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Task 11.4: framesMinForChallengeSeq
// ---------------------------------------------------------------------------

describe("framesMinForChallengeSeq (Task 11.4)", () => {
  it("parpadear requiere 3 frames", () => {
    expect(framesMinForChallengeSeq("parpadear")).toBe(FRAMES_MIN_BLINK_SEQ);
    expect(framesMinForChallengeSeq("parpadear")).toBe(3);
  });

  it("girar_cabeza requiere 4 frames", () => {
    expect(framesMinForChallengeSeq("girar_cabeza")).toBe(FRAMES_MIN_TURN_SEQ);
    expect(framesMinForChallengeSeq("girar_cabeza")).toBe(4);
  });

  it("sonreír requiere 4 frames", () => {
    expect(framesMinForChallengeSeq("sonreír")).toBe(FRAMES_MIN_SMILE_SEQ);
    expect(framesMinForChallengeSeq("sonreír")).toBe(4);
  });

  it("las constantes exportadas tienen los valores correctos", () => {
    expect(FRAMES_MIN_BLINK_SEQ).toBe(3);
    expect(FRAMES_MIN_TURN_SEQ).toBe(4);
    expect(FRAMES_MIN_SMILE_SEQ).toBe(4);
  });

  it("las constantes de factor tienen los valores correctos", () => {
    expect(BLINK_RELATIVE_FACTOR).toBe(0.45);
    expect(SMILE_RELATIVE_FACTOR).toBe(1.25);
    expect(GAZE_TURN_THRESHOLD_ADJUSTED).toBe(0.22);
  });
});

// ---------------------------------------------------------------------------
// Task 11.5: validacion del baseline
// Las funciones de logica del baseline viven en BiometricCapture (componente),
// pero exportamos una funcion pura de validacion para testearla aqui.
// ---------------------------------------------------------------------------

import {
  computeBaselineFromAccumulator,
  isBaselineSmileValid,
} from "./enrollmentChallengeDetector";

describe("validacion del baseline (Task 11.5)", () => {
  /** Crea un acumulador de frames con valores dados. */
  function makeAccumulator(count: number, values: Partial<{ blinkOpenness: number; smileWidth: number; gazeX: number }> = {}) {
    return Array.from({ length: count }, () => ({
      blinkOpenness: values.blinkOpenness ?? 0.060,
      smileWidth: values.smileWidth ?? 0.10,
      gazeX: values.gazeX ?? 0,
    }));
  }

  it("baseline con smileWidth > 0.14 es invalido", () => {
    expect(isBaselineSmileValid(0.15)).toBe(false);
    expect(isBaselineSmileValid(0.14)).toBe(false); // exactamente 0.14 es invalido (no cumple <=0.14 with strict <)
  });

  it("baseline con smileWidth <= 0.14 es valido", () => {
    expect(isBaselineSmileValid(0.13)).toBe(true);
    expect(isBaselineSmileValid(0.10)).toBe(true);
    expect(isBaselineSmileValid(0)).toBe(true);
  });

  it("acumulador con >= 12 frames calcula promedios correctos", () => {
    const acc = makeAccumulator(15, { blinkOpenness: 0.060, smileWidth: 0.10, gazeX: 0.01 });
    const result = computeBaselineFromAccumulator(acc);
    expect(result).not.toBeNull();
    expect(result!.blinkOpenness).toBeCloseTo(0.060);
    expect(result!.smileWidth).toBeCloseTo(0.10);
    expect(result!.gazeX).toBeCloseTo(0.01);
  });

  it("acumulador con < 12 frames no declara baseline (retorna null)", () => {
    const acc = makeAccumulator(11);
    expect(computeBaselineFromAccumulator(acc)).toBeNull();
  });

  it("acumulador vacio retorna null", () => {
    expect(computeBaselineFromAccumulator([])).toBeNull();
  });

  it("acumulador con exactamente 12 frames declara baseline", () => {
    const acc = makeAccumulator(12);
    expect(computeBaselineFromAccumulator(acc)).not.toBeNull();
  });

  it("acumulador con smileWidth promedio > 0.14 retorna null (sonrisa detectada en baseline)", () => {
    const acc = makeAccumulator(15, { smileWidth: 0.16 });
    // computeBaselineFromAccumulator deberia retornar null si el smileWidth promedio es invalido
    expect(computeBaselineFromAccumulator(acc)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// C-65 Task 4.1 RED / 4.3 TRIANGULATE: gestureHold — confirmación por tiempo
// ---------------------------------------------------------------------------

import { gestureHold, GESTURE_HOLD_MS } from "./enrollmentChallengeDetector";

describe("gestureHold — confirmación temporal (C-65 Task 4.1 / 4.3)", () => {
  // ── Caso base: gesto no sostenido suficiente ────────────────────────────
  it("gesto instantáneo (no cumple): no confirma y reinicia holdStart", () => {
    const result = gestureHold({ now: 1000, holdStart: null, cumple: false });
    expect(result.holdStart).toBeNull();
    expect(result.confirmado).toBe(false);
  });

  it("gesto nuevo (cumple por primera vez): inicia holdStart sin confirmar", () => {
    const result = gestureHold({ now: 1000, holdStart: null, cumple: true });
    expect(result.holdStart).toBe(1000);
    expect(result.confirmado).toBe(false);
  });

  it("gesto sostenido justo bajo el umbral: no confirma aún", () => {
    // holdStart = 0, now = GESTURE_HOLD_MS - 1 → elapsed < HOLD_MS
    const result = gestureHold({ now: GESTURE_HOLD_MS - 1, holdStart: 0, cumple: true });
    expect(result.confirmado).toBe(false);
    expect(result.holdStart).toBe(0); // holdStart se mantiene
  });

  it("gesto sostenido exactamente en el umbral: confirma", () => {
    // holdStart = 0, now = GESTURE_HOLD_MS → elapsed === HOLD_MS → confirma
    const result = gestureHold({ now: GESTURE_HOLD_MS, holdStart: 0, cumple: true });
    expect(result.confirmado).toBe(true);
  });

  it("gesto sostenido por encima del umbral: también confirma", () => {
    const result = gestureHold({ now: GESTURE_HOLD_MS + 200, holdStart: 0, cumple: true });
    expect(result.confirmado).toBe(true);
  });

  it("gesto interrumpido (deja de cumplir): resetea holdStart", () => {
    // holdStart tenía un valor; ahora cumple=false → resetea
    const result = gestureHold({ now: 600, holdStart: 200, cumple: false });
    expect(result.holdStart).toBeNull();
    expect(result.confirmado).toBe(false);
  });

  // ── Independencia del framerate (TRIANGULATE Task 4.3) ──────────────────
  it("30fps: 15 frames = 500ms → confirma exactamente igual que 60fps 30 frames", () => {
    // A 30fps: frames duran ~33ms, 15 frames = ~500ms → confirma
    // Simulamos holdStart=0, now=500 (15 frames a 30fps)
    const at30fps = gestureHold({ now: 500, holdStart: 0, cumple: true });
    expect(at30fps.confirmado).toBe(true);

    // A 60fps: frames duran ~16ms, 31 frames = ~496ms < 500ms → NO confirma
    const at60fps_early = gestureHold({ now: 496, holdStart: 0, cumple: true });
    expect(at60fps_early.confirmado).toBe(false);

    // A 60fps: 32 frames = ~512ms → confirma
    const at60fps_late = gestureHold({ now: 512, holdStart: 0, cumple: true });
    expect(at60fps_late.confirmado).toBe(true);
  });

  it("hold no comienza hasta cumple=true, incluso si now es alto", () => {
    // Si no cumplía antes (holdStart=null) y now es 9999, sin cumple no inicia
    const r = gestureHold({ now: 9999, holdStart: null, cumple: false });
    expect(r.holdStart).toBeNull();
    expect(r.confirmado).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Task 11.6: aleatorización Fisher-Yates
// ---------------------------------------------------------------------------

import { fisherYatesShuffle } from "./enrollmentChallengeDetector";
import { SEQUENTIAL_CHALLENGES } from "./liveness";

describe("aleatorización Fisher-Yates (Task 11.6)", () => {
  it("produce un array de la misma longitud con los mismos elementos", () => {
    const original = [...SEQUENTIAL_CHALLENGES];
    const shuffled = fisherYatesShuffle([...SEQUENTIAL_CHALLENGES]);
    expect(shuffled.length).toBe(original.length);
    expect(shuffled.sort()).toEqual(original.sort());
  });

  it("produce las 6 permutaciones posibles de SEQUENTIAL_CHALLENGES con N=1000 iteraciones", () => {
    // Hay 3! = 6 permutaciones posibles.
    // Con N=1000, cada una deberia aparecer ~1/6 de las veces (~166 veces).
    // Usamos un umbral conservador: cada permutacion debe aparecer al menos 50 veces.
    const permutacionCount: Record<string, number> = {};
    const N = 1000;

    for (let i = 0; i < N; i++) {
      const shuffled = fisherYatesShuffle([...SEQUENTIAL_CHALLENGES]);
      const key = shuffled.join(",");
      permutacionCount[key] = (permutacionCount[key] ?? 0) + 1;
    }

    const permutaciones = Object.keys(permutacionCount);
    // Deben existir exactamente 6 permutaciones distintas
    expect(permutaciones.length).toBe(6);

    // Cada permutacion debe aparecer con frecuencia razonable
    for (const [perm, count] of Object.entries(permutacionCount)) {
      expect(count).toBeGreaterThanOrEqual(50);
      expect(count).toBeLessThanOrEqual(250);
      // Verificar que son combinaciones validas
      const parts = perm.split(",");
      expect(parts.length).toBe(3);
      for (const part of parts) {
        expect(SEQUENTIAL_CHALLENGES).toContain(part as typeof SEQUENTIAL_CHALLENGES[number]);
      }
    }
  });
});
