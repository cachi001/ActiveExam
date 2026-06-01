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

  it("con faceMesh disponible: arc() es llamado para dibujar landmarks", () => {
    const ctx = makeCtxMock();
    const landmarks = Array.from({ length: 100 }, (_, i) => ({
      x: 0.3 + i * 0.001,
      y: 0.3 + i * 0.001,
      z: 0,
    }));
    const signals: RawSignals = {
      faceDetection: {
        face_count: 1,
        faces: [{ x: 0.1, y: 0.1, width: 0.5, height: 0.6, confidence: 0.9 }],
      },
      faceMesh: { gaze: { x: 0.1, y: 0.05 }, embedding: [], landmarks },
      poseAvailable: false,
      frameTs: 3000,
    };
    drawFrame(ctx, signals, 640, 480, false, false);
    // arc() se llama para los landmarks del subconjunto canónico que tengan índice < 100
    expect(ctx.arc).toHaveBeenCalled();
  });
});
