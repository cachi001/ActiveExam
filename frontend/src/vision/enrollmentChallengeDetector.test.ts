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
  isSmileByBlendshape,
  BLINK_RELATIVE_FACTOR,
  SMILE_RELATIVE_FACTOR,
  SMILE_BLENDSHAPE_THRESHOLD,
  TURN_YAW_THRESHOLD,
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
// C-67: sonreír por BLENDSHAPE (coeficiente mouthSmile de MediaPipe).
// Señal ABSOLUTA y robusta: cuando el motor la provee, manda sobre la métrica
// geométrica (ancho relativo al baseline), que era frágil y daba el "no me toma
// la sonrisa" crónico. Si no hay coeficiente, se cae al método geométrico.
// ---------------------------------------------------------------------------
describe("isSmileByBlendshape (C-67)", () => {
  it("coeficiente por encima del umbral -> true", () => {
    expect(isSmileByBlendshape(SMILE_BLENDSHAPE_THRESHOLD + 0.1)).toBe(true);
  });

  it("coeficiente por debajo del umbral -> false", () => {
    expect(isSmileByBlendshape(SMILE_BLENDSHAPE_THRESHOLD - 0.1)).toBe(false);
  });

  it("coeficiente exactamente en el umbral -> true (>=)", () => {
    expect(isSmileByBlendshape(SMILE_BLENDSHAPE_THRESHOLD)).toBe(true);
  });
});

describe("evaluateChallengeRelative — sonreír por blendshape (C-67)", () => {
  // Boca angosta + baseline con boca ancha => la métrica GEOMÉTRICA daría false.
  const lmBocaAngosta = makeLandmarks({ 61: { x: 0 }, 291: { x: 0.10 } });
  const baselineBocaAncha: BaselineMetrics = { blinkOpenness: 0.06, smileWidth: 0.20, gazeX: 0 };

  it("blendshape alto MANDA sobre la geometría: sonrisa genuina detectada aunque el ancho no alcance", () => {
    // Sin blendshape esto sería false (boca angosta vs baseline ancho).
    expect(
      evaluateChallengeRelative("sonreír", lmBocaAngosta, BASE_GAZE, baselineBocaAncha, undefined, 0.7),
    ).toBe(true);
  });

  it("blendshape bajo MANDA: cara neutra de boca ancha NO cuenta como sonrisa", () => {
    const lmBocaAncha = makeLandmarks({ 61: { x: 0 }, 291: { x: 0.30 } });
    expect(
      evaluateChallengeRelative("sonreír", lmBocaAncha, BASE_GAZE, BASELINE_NEUTRAL, undefined, 0.05),
    ).toBe(false);
  });

  it("con blendshape alto, baseline null ya NO bloquea (la señal absoluta basta)", () => {
    expect(
      evaluateChallengeRelative("sonreír", lmBocaAngosta, BASE_GAZE, null, undefined, 0.8),
    ).toBe(true);
  });

  it("sin coeficiente (undefined) -> cae al método geométrico (retrocompat)", () => {
    // Boca clara de sonrisa vs baseline neutral -> geométrico true.
    const lmSonrisa = makeLandmarks({ 61: { x: 0 }, 291: { x: 0.14 } });
    expect(
      evaluateChallengeRelative("sonreír", lmSonrisa, BASE_GAZE, BASELINE_NEUTRAL),
    ).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Task 11.3: evaluateChallengeRelative — girar_cabeza DIRECCIONAL
// ---------------------------------------------------------------------------

describe("evaluateChallengeRelative — girar_cabeza por HEAD YAW (C-67)", () => {
  // C-67: el giro se mide por la CABEZA (yaw geométrico nariz vs comisuras externas),
  // no por los ojos (gaze). Con comisuras en x=0 y x=1, el yaw = 2·noseX − 1:
  //   noseX 0.5 → yaw 0 (de frente) | noseX > 0.5 → yaw + | noseX < 0.5 → yaw −
  const lmTurn = (noseX: number) => makeLandmarks({ 1: { x: noseX }, 33: { x: 0 }, 263: { x: 1 } });
  const G = { x: 0, y: 0 }; // gaze ya NO se usa para el giro
  // noseX que produce yaw == TURN_YAW_THRESHOLD exacto: (1 + thr) / 2
  const noseAtThreshold = (1 + TURN_YAW_THRESHOLD) / 2;

  describe("con turnDirection = 'izquierda' (yaw +)", () => {
    const dir: TurnDirection = "izquierda";

    it("cabeza bien girada (yaw +) -> true", () => {
      expect(evaluateChallengeRelative("girar_cabeza", lmTurn(0.85), G, BASELINE_NEUTRAL, dir)).toBe(true);
    });

    it("girada al lado opuesto (yaw -) -> false", () => {
      expect(evaluateChallengeRelative("girar_cabeza", lmTurn(0.15), G, BASELINE_NEUTRAL, dir)).toBe(false);
    });

    it("de frente (yaw 0) -> false", () => {
      expect(evaluateChallengeRelative("girar_cabeza", lmTurn(0.5), G, BASELINE_NEUTRAL, dir)).toBe(false);
    });

    it("apenas por debajo del umbral -> false (no alcanza)", () => {
      expect(evaluateChallengeRelative("girar_cabeza", lmTurn(noseAtThreshold - 0.03), G, BASELINE_NEUTRAL, dir)).toBe(false);
    });

    it("apenas por encima del umbral -> true", () => {
      expect(evaluateChallengeRelative("girar_cabeza", lmTurn(noseAtThreshold + 0.03), G, BASELINE_NEUTRAL, dir)).toBe(true);
    });
  });

  describe("con turnDirection = 'derecha' (yaw -)", () => {
    const dir: TurnDirection = "derecha";

    it("cabeza bien girada (yaw -) -> true", () => {
      expect(evaluateChallengeRelative("girar_cabeza", lmTurn(0.15), G, BASELINE_NEUTRAL, dir)).toBe(true);
    });

    it("girada al lado opuesto (yaw +) -> false", () => {
      expect(evaluateChallengeRelative("girar_cabeza", lmTurn(0.85), G, BASELINE_NEUTRAL, dir)).toBe(false);
    });

    it("de frente (yaw 0) -> false", () => {
      expect(evaluateChallengeRelative("girar_cabeza", lmTurn(0.5), G, BASELINE_NEUTRAL, dir)).toBe(false);
    });

    it("un giro chiquito (apenas) NO alcanza -> false", () => {
      // yaw ~0.10 (noseX 0.55): el problema reportado ("apenas giro lo toma")
      expect(evaluateChallengeRelative("girar_cabeza", lmTurn(0.45), G, BASELINE_NEUTRAL, dir)).toBe(false);
    });
  });

  it("sin turnDirection (undefined) -> false", () => {
    expect(evaluateChallengeRelative("girar_cabeza", lmTurn(0.85), G, BASELINE_NEUTRAL, undefined)).toBe(false);
  });

  it("baseline null con giro correcto -> true (el giro no usa baseline)", () => {
    expect(evaluateChallengeRelative("girar_cabeza", lmTurn(0.85), G, null, "izquierda")).toBe(true);
  });

  it("landmarks insuficientes (<264) -> false", () => {
    const lm = lmTurn(0.85).slice(0, 200);
    expect(evaluateChallengeRelative("girar_cabeza", lm, G, BASELINE_NEUTRAL, "izquierda")).toBe(false);
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

import { gestureAccumulator, GESTURE_GRACE_MS } from "./enrollmentChallengeDetector";

describe("gestureAccumulator — progreso por hold con GRACIA (C-67)", () => {
  const gestureHoldMs = 500;

  // Test 2.1a: acumula dt mientras el gesto está sostenido; resetea la pérdida
  it("2.1a: acumula dt mientras el gesto es cumplido (lostMs vuelve a 0)", () => {
    const result = gestureAccumulator({
      prevAccumMs: 0,
      cumple: true,
      dt: 100,
      gestureHoldMs,
      prevLostMs: 80,
    });
    expect(result.accumMs).toBeCloseTo(100);
    expect(result.fracReto).toBeCloseTo(0.2);
    expect(result.isHolding).toBe(true);
    expect(result.confirmado).toBe(false);
    expect(result.lostMs).toBe(0);
  });

  // Test 2.1b: pérdida BREVE (≤ gracia) → PRESERVA el progreso (anillo sube smooth).
  it("2.1b: un titileo breve (≤ gracia) PRESERVA el acumulado", () => {
    const dt = Math.floor(GESTURE_GRACE_MS / 3);
    const result = gestureAccumulator({ prevAccumMs: 300, cumple: false, dt, gestureHoldMs, prevLostMs: 0 });
    expect(result.accumMs).toBe(300); // preservado
    expect(result.isHolding).toBe(false);
    expect(result.confirmado).toBe(false);
    expect(result.lostMs).toBe(dt);
  });

  // Test 2.1b-bis: pérdida SOSTENIDA (> gracia) → RESETEA a 0 (hay que sostener).
  it("2.1b-bis: soltar de verdad (> gracia) RESETEA el acumulado a 0", () => {
    const result = gestureAccumulator({
      prevAccumMs: 300,
      cumple: false,
      dt: 50,
      gestureHoldMs,
      prevLostMs: GESTURE_GRACE_MS, // lostMs = gracia + 50 > gracia
    });
    expect(result.accumMs).toBe(0);
    expect(result.fracReto).toBe(0);
  });

  // Test 2.1c: tras un titileo (preservado), el gesto se reanuda y sigue sumando
  it("2.1c: reanuda desde el valor preservado tras un titileo breve", () => {
    const dt = Math.floor(GESTURE_GRACE_MS / 3);
    const lost = gestureAccumulator({ prevAccumMs: 300, cumple: false, dt, gestureHoldMs, prevLostMs: 0 });
    expect(lost.accumMs).toBe(300); // preservado dentro de la gracia

    const resume = gestureAccumulator({
      prevAccumMs: lost.accumMs,
      cumple: true,
      dt: 100,
      gestureHoldMs,
      prevLostMs: lost.lostMs,
    });
    expect(resume.accumMs).toBeCloseTo(400); // 300 + 100
    expect(resume.lostMs).toBe(0);
    expect(resume.isHolding).toBe(true);
  });

  // Test 2.1c-bis: parpadeo rápido (cerrar/abrir) NO acumula: cada apertura supera
  // la gracia y resetea. Simulamos frames de 33ms: cerrado 3 frames, abierto 5.
  it("2.1c-bis: el parpadeo rápido NO acumula hasta confirmar (cada apertura resetea)", () => {
    let accum = 0;
    let lost = 0;
    for (let ciclo = 0; ciclo < 10; ciclo++) {
      for (let i = 0; i < 3; i++) {
        const r = gestureAccumulator({ prevAccumMs: accum, cumple: true, dt: 33, gestureHoldMs, prevLostMs: lost });
        accum = r.accumMs; lost = r.lostMs;
      }
      for (let i = 0; i < 5; i++) {
        const r = gestureAccumulator({ prevAccumMs: accum, cumple: false, dt: 33, gestureHoldMs, prevLostMs: lost });
        accum = r.accumMs; lost = r.lostMs;
      }
    }
    expect(accum).toBeLessThan(gestureHoldMs); // nunca completa parpadeando rápido
  });

  // Test 2.1d: confirma cuando accumMs alcanza gestureHoldMs (hold sostenido)
  it("2.1d: confirma cuando accumMs >= gestureHoldMs", () => {
    const result = gestureAccumulator({ prevAccumMs: 450, cumple: true, dt: 60, gestureHoldMs });
    expect(result.confirmado).toBe(true);
    expect(result.fracReto).toBe(1);
    expect(result.isHolding).toBe(true);
  });

  // Test 2.1e: soltar de verdad resetea; recién un hold sostenido completo confirma.
  it("2.1e: tras soltar (reset), hay que rehacer el hold sostenido para confirmar", () => {
    // Hold parcial 300ms
    let r = gestureAccumulator({ prevAccumMs: 0, cumple: true, dt: 300, gestureHoldMs });
    expect(r.accumMs).toBeCloseTo(300);

    // Soltó de verdad (> gracia) → reset 0
    r = gestureAccumulator({ prevAccumMs: r.accumMs, cumple: false, dt: GESTURE_GRACE_MS + 50, gestureHoldMs, prevLostMs: 0 });
    expect(r.accumMs).toBe(0);

    // Hold sostenido completo (>=500) → confirma
    r = gestureAccumulator({ prevAccumMs: 0, cumple: true, dt: 520, gestureHoldMs });
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

  it("5.2e evaluateChallengeRelative(girar_cabeza, izquierda) confirma con head yaw > threshold", () => {
    // C-67: el giro se mide por head yaw (cabeza), no gaze. nose 0.85 vs comisuras
    // 0/1 → yaw +0.70 (giro claro a izquierda).
    const lm = makeLandmarks({ 1: { x: 0.85 }, 33: { x: 0 }, 263: { x: 1 } });
    const gaze = { x: 0, y: 0 };
    const baseline: BaselineMetrics = { blinkOpenness: 0.06, smileWidth: 0.10, gazeX: 0 };

    expect(evaluateChallengeRelative("girar_cabeza", lm, gaze, baseline, "izquierda")).toBe(true);
    // La misma cabeza girada (yaw +) NO confirma "derecha"
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

  // Test 4.4d: con cumple=false el acumulador NO confirma (isHolding=false) y, C-67,
  // DECAE (resta dt) en vez de preservar — perder la sonrisa cuesta progreso.
  it("4.4d: perder la sonrisa un frame breve (≤ gracia) NO confirma pero PRESERVA (anti doble-paso)", () => {
    const accumLost = gestureAccumulator({
      prevAccumMs: SMILE_GESTURE_HOLD_MS - 1, // 499
      cumple: false,
      dt: 50, // dentro de la gracia → preserva
      gestureHoldMs: SMILE_GESTURE_HOLD_MS,
      prevLostMs: 0,
    });
    expect(accumLost.confirmado).toBe(false);
    expect(accumLost.isHolding).toBe(false);
    // Titileo breve dentro de la gracia → preserva (no resetea)
    expect(accumLost.accumMs).toBe(SMILE_GESTURE_HOLD_MS - 1);
  });
});
