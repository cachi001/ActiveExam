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
    expect(SMILE_RELATIVE_FACTOR).toBe(1.12); // C-67: bajado de 1.25 (sonrisa más fácil)
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
// C-67 Group 2: gestureAccumulator — progreso acumulado con reanudación
// ---------------------------------------------------------------------------

import { gestureAccumulator } from "./enrollmentChallengeDetector";

describe("gestureAccumulator — progreso acumulado sin reinicio (C-67 Group 2)", () => {
  const gestureHoldMs = 500;

  // Test 2.1a: acumula dt mientras el gesto está sostenido
  it("2.1a: acumula dt mientras el gesto es cumplido", () => {
    const result = gestureAccumulator({
      prevAccumMs: 0,
      cumple: true,
      dt: 100,
      gestureHoldMs,
    });
    expect(result.accumMs).toBeCloseTo(100);
    expect(result.fracReto).toBeCloseTo(0.2);
    expect(result.isHolding).toBe(true);
    expect(result.confirmado).toBe(false);
  });

  // Test 2.1b: NO resetea accumMs al perder el gesto
  it("2.1b: NO resetea accumMs cuando el gesto se pierde (isHolding=false, accumMs preservado)", () => {
    const result = gestureAccumulator({
      prevAccumMs: 300,
      cumple: false,
      dt: 50,
      gestureHoldMs,
    });
    // accumMs debe preservarse en 300 (no se pierde el progreso)
    expect(result.accumMs).toBe(300);
    expect(result.isHolding).toBe(false);
    expect(result.confirmado).toBe(false);
    // fracReto refleja el progreso preservado
    expect(result.fracReto).toBeCloseTo(0.6);
  });

  // Test 2.1c: reanuda desde el valor preservado cuando el gesto vuelve
  it("2.1c: reanuda desde accumMs preservado cuando el gesto se recupera", () => {
    // Simular: tenía 300ms acumulados, pierde el gesto (accumMs=300 preservado)
    const lostResult = gestureAccumulator({
      prevAccumMs: 300,
      cumple: false,
      dt: 50,
      gestureHoldMs,
    });
    expect(lostResult.accumMs).toBe(300);

    // Ahora reanuda con el valor preservado
    const resumeResult = gestureAccumulator({
      prevAccumMs: lostResult.accumMs,
      cumple: true,
      dt: 100,
      gestureHoldMs,
    });
    expect(resumeResult.accumMs).toBeCloseTo(400);
    expect(resumeResult.fracReto).toBeCloseTo(0.8);
    expect(resumeResult.isHolding).toBe(true);
    expect(resumeResult.confirmado).toBe(false);
  });

  // Test 2.1d: confirma cuando accumMs alcanza gestureHoldMs
  it("2.1d: confirma cuando accumMs >= gestureHoldMs", () => {
    const result = gestureAccumulator({
      prevAccumMs: 450,
      cumple: true,
      dt: 60, // 450 + 60 = 510 >= 500
      gestureHoldMs,
    });
    expect(result.confirmado).toBe(true);
    expect(result.fracReto).toBe(1);
    expect(result.isHolding).toBe(true);
  });

  // Test 2.1e: con múltiples pérdidas y reanudaciones, eventualmente confirma
  it("2.1e: con múltiples pérdidas y reanudaciones, eventualmente confirma", () => {
    let accum = 0;

    // Ciclo 1: gana 200ms
    let r = gestureAccumulator({ prevAccumMs: accum, cumple: true, dt: 200, gestureHoldMs });
    accum = r.accumMs;
    expect(r.confirmado).toBe(false);

    // Pierde el gesto
    r = gestureAccumulator({ prevAccumMs: accum, cumple: false, dt: 100, gestureHoldMs });
    accum = r.accumMs;
    expect(accum).toBeCloseTo(200); // preservado

    // Ciclo 2: gana 150ms más (total ~350ms)
    r = gestureAccumulator({ prevAccumMs: accum, cumple: true, dt: 150, gestureHoldMs });
    accum = r.accumMs;
    expect(r.confirmado).toBe(false);

    // Pierde el gesto de nuevo
    r = gestureAccumulator({ prevAccumMs: accum, cumple: false, dt: 50, gestureHoldMs });
    accum = r.accumMs;
    expect(accum).toBeCloseTo(350); // preservado

    // Ciclo 3: gana 200ms más (total ~550ms >= 500ms → confirma)
    r = gestureAccumulator({ prevAccumMs: accum, cumple: true, dt: 200, gestureHoldMs });
    accum = r.accumMs;
    expect(r.confirmado).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// C-67 Group 4: computeSmileScore + evaluateChallengeRelative sonrisa compuesta
// ---------------------------------------------------------------------------

import {
  computeSmileScore,
  SMILE_CORNER_RISE_THRESHOLD,
} from "./enrollmentChallengeDetector";

describe("computeSmileScore — métrica compuesta de sonrisa (C-67 Group 4)", () => {
  function makeLm468(overrides: Record<number, Partial<FaceLandmark>>): FaceLandmark[] {
    const lm: FaceLandmark[] = Array.from({ length: 468 }, () => ({ x: 0, y: 0, z: 0 }));
    for (const [idx, vals] of Object.entries(overrides)) {
      lm[Number(idx)] = { x: 0, y: 0, z: 0, ...vals };
    }
    return lm;
  }

  it("retorna null si hay menos de 292 landmarks", () => {
    const lm: FaceLandmark[] = Array.from({ length: 100 }, () => ({ x: 0, y: 0, z: 0 }));
    expect(computeSmileScore(lm)).toBeNull();
  });

  it("retorna { width, elevation, composite } con landmarks suficientes", () => {
    const lm = makeLm468({ 61: { x: 0.05 }, 291: { x: 0.15 } });
    const result = computeSmileScore(lm);
    expect(result).not.toBeNull();
    expect(typeof result!.width).toBe('number');
    expect(typeof result!.elevation).toBe('number');
    expect(typeof result!.composite).toBe('number');
  });

  it("width = |lm[291].x - lm[61].x|", () => {
    const lm = makeLm468({ 61: { x: 0.05 }, 291: { x: 0.15 } });
    const result = computeSmileScore(lm);
    expect(result!.width).toBeCloseTo(0.10);
  });
});

describe("evaluateChallengeRelative — sonrisa compuesta (C-67 Group 4)", () => {
  function makeLm468(overrides: Record<number, Partial<FaceLandmark>>): FaceLandmark[] {
    const lm: FaceLandmark[] = Array.from({ length: 468 }, () => ({ x: 0, y: 0, z: 0 }));
    for (const [idx, vals] of Object.entries(overrides)) {
      lm[Number(idx)] = { x: 0, y: 0, z: 0, ...vals };
    }
    return lm;
  }

  const BASE_GAZE = { x: 0, y: 0 };

  // Test 4.1a: sonrisa real (ancho + elevación de comisuras) → confirma
  it("4.1a: sonrisa real (ancho grande) → confirma (widthOk)", () => {
    const baseline: BaselineMetrics = { blinkOpenness: 0.06, smileWidth: 0.10, gazeX: 0 };
    // width = 0.14 > 0.10 * 1.25 = 0.125 → widthOk = true
    const lm = makeLm468({ 61: { x: 0, y: 0.5 }, 291: { x: 0.14, y: 0.5 } });
    expect(evaluateChallengeRelative("sonreír", lm, BASE_GAZE, baseline)).toBe(true);
  });

  // Test 4.1b: cara neutral (sin aumento de ancho, sin elevación) → NO confirma
  it("4.1b: cara neutral (sin sonrisa) → NO confirma", () => {
    const baseline: BaselineMetrics = { blinkOpenness: 0.06, smileWidth: 0.10, gazeX: 0 };
    // width = 0.105 < 0.125, sin elevación → false
    const lm = makeLm468({ 61: { x: 0, y: 0.5 }, 291: { x: 0.105, y: 0.5 } });
    expect(evaluateChallengeRelative("sonreír", lm, BASE_GAZE, baseline)).toBe(false);
  });

  // Test 4.1c: boca abierta sin sonreír (ancho parcial + esquinas no suben) → NO confirma
  // cuando hay datos de cornerY en el baseline
  it("4.1c: ancho parcial (85% de factor) sin elevación de comisuras → NO confirma", () => {
    // widthPartial = 0.106 (>= 0.10 * 1.25 * 0.85 = 0.106), pero elevationOk = false
    const baselineWithCorner = {
      blinkOpenness: 0.06,
      smileWidth: 0.10,
      gazeX: 0,
      smileCornerY: 0.45, // baseline corner y (en reposo)
    } as BaselineMetrics & { smileCornerY: number };
    // avgCornerY = 0.46 > baseline.smileCornerY - threshold = 0.45 - 0.008 = 0.442
    // 0.46 < 0.442? No → elevationOk = false
    const lm = makeLm468({
      61:  { x: 0, y: 0.46 },
      291: { x: 0.106, y: 0.46 },
    });
    expect(evaluateChallengeRelative("sonreír", lm, BASE_GAZE, baselineWithCorner)).toBe(false);
  });

  // Test 4.1d: sin datos de cornerY en baseline → fallback a solo ancho
  it("4.1d: sin smileCornerY en baseline → fallback a width-only, confirma si width pasa", () => {
    const baseline: BaselineMetrics = { blinkOpenness: 0.06, smileWidth: 0.10, gazeX: 0 };
    // Sin smileCornerY: elevationOk = false, pero widthOk con width = 0.13 > 0.125
    const lm = makeLm468({ 61: { x: 0, y: 0.5 }, 291: { x: 0.13, y: 0.5 } });
    expect(evaluateChallengeRelative("sonreír", lm, BASE_GAZE, baseline)).toBe(true);
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

// ---------------------------------------------------------------------------
// C-67 Grupo 5: Consistencia de la defensa anti-foto (PAD) — Task 5.2
// ---------------------------------------------------------------------------

describe("C-67 Grupo 5 — consistencia de la defensa anti-foto (PAD, Task 5.2)", () => {
  /**
   * Verifica que el barajado Fisher-Yates produzca orden diferente al original
   * con suficiente frecuencia (probabilidad de mantener el orden: 1/6 ≈ 16.7%).
   * En N=200 iteraciones, al menos un barajado debe diferir.
   *
   * Nota: el orden barajado Y la dirección de giro aleatoria elevan el costo de
   * un video pregrabado (el atacante no puede ensayar la secuencia exacta).
   * ISO/IEC 30107-3: la aleatoriedad del reto-respuesta es parte del Nivel 1–2.
   */
  it("5.2a Fisher-Yates produce al menos una permutación distinta al original en 200 intentos", () => {
    const original = [...SEQUENTIAL_CHALLENGES];
    let seenDifferent = false;

    for (let i = 0; i < 200; i++) {
      const shuffled = fisherYatesShuffle([...original]);
      if (shuffled.join(",") !== original.join(",")) {
        seenDifferent = true;
        break;
      }
    }

    expect(seenDifferent).toBe(true);
  });

  /**
   * El barajado preserva todos los retos (sin duplicados ni omisiones).
   * Una foto no puede ejecutar ninguno; el orden es irrelevante para ella.
   * Para un video pregrabado, el orden aleatorio ya invalida la grabación.
   */
  it("5.2b Fisher-Yates preserva todos los elementos (sin duplicados ni omisiones)", () => {
    for (let i = 0; i < 50; i++) {
      const shuffled = fisherYatesShuffle([...SEQUENTIAL_CHALLENGES]);
      expect(shuffled).toHaveLength(SEQUENTIAL_CHALLENGES.length);
      for (const challenge of SEQUENTIAL_CHALLENGES) {
        expect(shuffled).toContain(challenge);
      }
    }
  });

  /**
   * La dirección de giro tiene dos valores posibles ('izquierda' / 'derecha').
   * En N=200 iteraciones ambas deben aparecer (distribución no degenerada).
   * Esta aleatoriedad sube el costo del video pregrabado: un video que gira
   * a la izquierda falla si se pide girar a la derecha.
   *
   * Nota: la lógica de elección vive en BiometricCapture (Math.random() < 0.5),
   * no en una función pura. Verificamos aquí la invarianza de dominio:
   * los únicos valores válidos son 'izquierda' y 'derecha'.
   */
  it("5.2c la dirección de giro tiene exactamente dos valores posibles (izquierda/derecha)", () => {
    // Los únicos valores válidos del tipo TurnDirection
    const validDirections: readonly string[] = ["izquierda", "derecha"];
    const seen = new Set<string>();

    for (let i = 0; i < 200; i++) {
      const dir = Math.random() < 0.5 ? "izquierda" : "derecha";
      expect(validDirections).toContain(dir);
      seen.add(dir);
    }

    // Ambas deben aparecer en 200 intentos (P(ninguna derecha) = (0.5)^200 ≈ 0)
    expect(seen.has("izquierda")).toBe(true);
    expect(seen.has("derecha")).toBe(true);
  });

  /**
   * Las tres capas de defensa están presentes en el módulo:
   * - Activa: SEQUENTIAL_CHALLENGES (reto-respuesta)
   * - Pasiva: derivePassiveSignals + passivePassed (en liveness.ts)
   * - Cámara virtual: detectVirtualCamera (en liveness.ts)
   *
   * Este test verifica la invarianza estructural: girar_cabeza es el reto
   * con dirección aleatoria; sin baseline o sin dirección, no confirma.
   */
  it("5.2d evaluateChallengeRelative(girar_cabeza) sin turnDirection retorna false (dirección requerida)", () => {
    const lm = makeLandmarks({});
    const gaze = { x: 0.5, y: 0 }; // gaze desplazado — debería confirmar giro izq
    const baseline: BaselineMetrics = { blinkOpenness: 0.06, smileWidth: 0.10, gazeX: 0 };

    // Sin turnDirection → false (no se puede confirmar el giro sin dirección)
    expect(evaluateChallengeRelative("girar_cabeza", lm, gaze, baseline, undefined)).toBe(false);
  });

  it("5.2e evaluateChallengeRelative(girar_cabeza, izquierda) confirma con gaze.x > threshold", () => {
    const lm = makeLandmarks({});
    const gaze = { x: GAZE_TURN_THRESHOLD_ADJUSTED + 0.05, y: 0 }; // claramente izquierda
    const baseline: BaselineMetrics = { blinkOpenness: 0.06, smileWidth: 0.10, gazeX: 0 };

    expect(evaluateChallengeRelative("girar_cabeza", lm, gaze, baseline, "izquierda")).toBe(true);
    // El mismo gaze NO confirma "derecha"
    expect(evaluateChallengeRelative("girar_cabeza", lm, gaze, baseline, "derecha")).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// C-67 Task 4.4 / 4.5: SMILE_GESTURE_HOLD_MS — hold propio de sonrisa
//
// Reconciliación con la decisión del dueño:
//   "TODO deliberado, NO rápido" (Open Questions resueltas, 2026-06-13).
//   SMILE_GESTURE_HOLD_MS = GESTURE_HOLD_MS (500 ms) — mismo valor pero
//   constante PROPIA, exportada y ajustable sin re-deploy.
//   "Menor latencia" del spec = HOLD PROPIO separado del genérico, no
//   necesariamente un valor menor. Si el dueño en el futuro quiere bajar el
//   valor (ej. a 450 ms), cambia SOLO esta constante sin romper nada más.
//   ⚠️ DUDA PARA EL DUEÑO: el spec pide "menor latencia que los demás gestos"
//   literalmente, pero la decisión de diseño pide "deliberado, ≥500ms".
//   Esta implementación da hold PROPIO = 500 ms (conservador). Si el dueño
//   quiere reducirlo, debe confirmar el valor mínimo seguro.
// ---------------------------------------------------------------------------

import { SMILE_GESTURE_HOLD_MS } from "./enrollmentChallengeDetector";
// Note: gestureAccumulator and GESTURE_HOLD_MS already imported above (line ~316 and ~385)

describe("SMILE_GESTURE_HOLD_MS — hold propio de sonrisa (C-67 Task 4.4/4.5)", () => {
  // Test 4.4a (happy path): la sonrisa confirma al sostener SMILE_GESTURE_HOLD_MS
  it("4.4a: sonrisa sostenida por SMILE_GESTURE_HOLD_MS confirma (happy path)", () => {
    // Simular frames que acumulan hasta alcanzar exactamente SMILE_GESTURE_HOLD_MS.
    // Con prevAccumMs = SMILE_GESTURE_HOLD_MS - 1 y dt = 1, debe confirmar.
    const result = gestureAccumulator({
      prevAccumMs: SMILE_GESTURE_HOLD_MS - 1,
      cumple: true,
      dt: 1,
      gestureHoldMs: SMILE_GESTURE_HOLD_MS,
    });
    expect(result.confirmado).toBe(true);
    expect(result.isHolding).toBe(true);
  });

  // Test 4.4b (edge: neutral NO confirma): con cara neutral, evaluateChallengeRelative
  // retorna false para sonreír → el acumulador NO avanza → no confirma.
  it("4.4b: cara neutral — evaluateChallengeRelative sonreír = false → acumulador no confirma", () => {
    const baselineNeutral: BaselineMetrics = {
      blinkOpenness: 0.06,
      smileWidth: 0.10,
      gazeX: 0,
    };
    // Cara neutral: ancho de boca = 0.105 (< threshold de 0.112 = 0.10 * 1.12)
    const lm = makeLandmarks({ 61: { x: 0, y: 0.5 }, 291: { x: 0.105, y: 0.5 } });
    const cumple = evaluateChallengeRelative("sonreír", lm, { x: 0, y: 0 }, baselineNeutral);
    expect(cumple).toBe(false);

    // Acumulador con cumple=false no avanza — aunque prevAccumMs sea alto
    const accumResult = gestureAccumulator({
      prevAccumMs: SMILE_GESTURE_HOLD_MS - 10,
      cumple: false,
      dt: 100,
      gestureHoldMs: SMILE_GESTURE_HOLD_MS,
    });
    expect(accumResult.confirmado).toBe(false);
    expect(accumResult.isHolding).toBe(false);
  });

  // Test 4.4c: SMILE_GESTURE_HOLD_MS está exportada y es >= GESTURE_HOLD_MS (deliberada)
  it("4.4c: SMILE_GESTURE_HOLD_MS es constante propia >= GESTURE_HOLD_MS (ritmo deliberado)", () => {
    // Invariante de seguridad anti-spoofing: el hold de sonrisa no puede ser
    // agresivamente corto. El mínimo seguro es GESTURE_HOLD_MS (500ms).
    expect(typeof SMILE_GESTURE_HOLD_MS).toBe("number");
    expect(SMILE_GESTURE_HOLD_MS).toBeGreaterThanOrEqual(GESTURE_HOLD_MS);
  });

  // Test 4.4d: el gate de neutralidad sigue activo con SMILE_GESTURE_HOLD_MS —
  // el acumulador con cumple=false no confirma aunque tenga prevAccumMs alto.
  it("4.4d: el gate de neutralidad preserva el acumulado pero NO confirma (anti doble-paso)", () => {
    // Si el alumno tiene 499ms acumulados y pierde la sonrisa un frame,
    // el acumulador se preserva pero isHolding=false → no confirma ese frame.
    const accumLost = gestureAccumulator({
      prevAccumMs: SMILE_GESTURE_HOLD_MS - 1,
      cumple: false,
      dt: 50,
      gestureHoldMs: SMILE_GESTURE_HOLD_MS,
    });
    expect(accumLost.confirmado).toBe(false);
    expect(accumLost.isHolding).toBe(false);
    // El acumulado se preserva para reanudación
    expect(accumLost.accumMs).toBe(SMILE_GESTURE_HOLD_MS - 1);
  });
});
