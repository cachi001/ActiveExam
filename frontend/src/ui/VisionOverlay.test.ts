/**
 * Tests de VisionOverlay — canvas overlay de visión (C-30, vision-overlay-canvas).
 *
 * Verifica que drawFrame llama a drawRect (strokeRect) una vez por cada rostro
 * detectado, usando un mock del CanvasRenderingContext2D.
 */

import { describe, expect, it, vi } from "vitest";
import { drawFrame, type RawSignals } from "./VisionOverlay";

/** Crea un mock del CanvasRenderingContext2D con spies en todos los métodos de dibujo. */
function makeCtxMock(): CanvasRenderingContext2D {
  return {
    clearRect: vi.fn(),
    strokeRect: vi.fn(),
    fillRect: vi.fn(),
    fillText: vi.fn(),
    measureText: vi.fn().mockReturnValue({ width: 50 }),
    beginPath: vi.fn(),
    arc: vi.fn(),
    fill: vi.fn(),
    stroke: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    strokeStyle: "",
    fillStyle: "",
    lineWidth: 1,
    font: "",
  } as unknown as CanvasRenderingContext2D;
}

describe("drawFrame — bounding boxes", () => {
  it("con 0 rostros: strokeRect no se llama", () => {
    const ctx = makeCtxMock();
    const signals: RawSignals = {
      faceDetection: { face_count: 0, faces: [] },
      faceMesh: null,
      poseAvailable: false,
      frameTs: 0,
    };
    drawFrame(ctx, signals, 640, 480, false, false);
    expect(ctx.strokeRect).not.toHaveBeenCalled();
  });

  it("con 1 rostro: strokeRect se llama 1 vez", () => {
    const ctx = makeCtxMock();
    const signals: RawSignals = {
      faceDetection: {
        face_count: 1,
        faces: [{ x: 0.1, y: 0.1, width: 0.5, height: 0.6, confidence: 0.9 }],
      },
      faceMesh: null,
      poseAvailable: false,
      frameTs: 1000,
    };
    drawFrame(ctx, signals, 640, 480, false, false);
    expect(ctx.strokeRect).toHaveBeenCalledTimes(1);
  });

  it("con 2 rostros: strokeRect se llama 2 veces", () => {
    const ctx = makeCtxMock();
    const signals: RawSignals = {
      faceDetection: {
        face_count: 2,
        faces: [
          { x: 0.05, y: 0.1, width: 0.3, height: 0.4, confidence: 0.95 },
          { x: 0.55, y: 0.1, width: 0.3, height: 0.4, confidence: 0.88 },
        ],
      },
      faceMesh: null,
      poseAvailable: false,
      frameTs: 2000,
    };
    drawFrame(ctx, signals, 640, 480, false, false);
    expect(ctx.strokeRect).toHaveBeenCalledTimes(2);
  });

  it("clearRect se llama siempre al inicio del frame", () => {
    const ctx = makeCtxMock();
    const signals: RawSignals = {
      faceDetection: { face_count: 0, faces: [] },
      faceMesh: null,
      poseAvailable: false,
      frameTs: 0,
    };
    drawFrame(ctx, signals, 640, 480, false, false);
    expect(ctx.clearRect).toHaveBeenCalledWith(0, 0, 640, 480);
  });

  it("con rostro: el label incluye 'Rostro 1' y el porcentaje de confianza", () => {
    const ctx = makeCtxMock();
    const signals: RawSignals = {
      faceDetection: {
        face_count: 1,
        faces: [{ x: 0.2, y: 0.2, width: 0.4, height: 0.5, confidence: 0.93 }],
      },
      faceMesh: null,
      poseAvailable: false,
      frameTs: 500,
    };
    drawFrame(ctx, signals, 640, 480, false, false);
    expect(ctx.fillText).toHaveBeenCalledWith(
      expect.stringMatching(/Rostro 1 \(93%\)/),
      expect.any(Number),
      expect.any(Number),
    );
  });

});

describe("drawFrame — mesh opt-in solo-staff (C-53)", () => {
  /** Construye señales con faceMesh de `n` landmarks y un rostro detectado. */
  function makeMeshSignals(n: number): RawSignals {
    const landmarks = Array.from({ length: n }, (_, i) => ({
      x: 0.3 + i * 0.0001,
      y: 0.3 + i * 0.0001,
      z: 0,
    }));
    return {
      faceDetection: {
        face_count: 1,
        faces: [{ x: 0.1, y: 0.1, width: 0.5, height: 0.6, confidence: 0.9 }],
      },
      faceMesh: { gaze: { x: 0.1, y: 0.05 }, embedding: [], landmarks },
      poseAvailable: false,
      frameTs: 3000,
    };
  }

  it("showFullMesh=false: NO dibuja puntos de mesh (arc no se llama), pero SÍ box y gaze", () => {
    const ctx = makeCtxMock();
    const signals = makeMeshSignals(468);
    drawFrame(ctx, signals, 640, 480, false, false);
    // Sin mesh: arc() no se invoca (solo se usa para landmarks de mesh y keypoints de pose)
    expect(ctx.arc).not.toHaveBeenCalled();
    // Box del rostro presente
    expect(ctx.strokeRect).toHaveBeenCalledTimes(1);
    // Gaze presente: drawGazeArrow usa moveTo/lineTo desde el centro del rostro
    expect(ctx.moveTo).toHaveBeenCalled();
    expect(ctx.lineTo).toHaveBeenCalled();
  });

  it("showFullMesh=true con 468 landmarks: dibuja los 468 puntos (un arc por punto)", () => {
    const ctx = makeCtxMock();
    const signals = makeMeshSignals(468);
    drawFrame(ctx, signals, 640, 480, true, false);
    // 468 arcs de mesh; el gaze usa moveTo/lineTo, no arc → exactamente 468
    expect(ctx.arc).toHaveBeenCalledTimes(468);
  });
});
