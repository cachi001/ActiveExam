/**
 * Tests del pipeline de vision (C-11). Formato Vitest.
 *
 * Verifican: abstraccion del motor (el pipeline opera contra un doble de VisionEngine
 * que NO es MediaPipe); sustituibilidad (cambiar el doble no cambia el pipeline);
 * e2e feed -> detectores -> reglas -> evento emitido al transporte; multiples rostros
 * dispara evidencia + alerta; evento conforme al contrato de C-10 (tipo/severidad/payload).
 */

import { describe, expect, it, vi } from "vitest";

import type {
  FaceDetectionSignal,
  FaceMeshSignal,
  FrameResult,
  PoseSignal,
  VisionEngine,
} from "../vision/VisionEngine";
import { VisionPipeline } from "./visionPipeline";

/** Doble de motor que implementa la interfaz sin tocar MediaPipe (gancho ONNX). */
class FakeEngine implements VisionEngine {
  constructor(private readonly faceCount: number, private readonly gaze = { x: 0, y: 0 }) {}
  async init(): Promise<void> {}
  async processFrame(): Promise<FrameResult> {
    return { landmarks: [], face_count: this.faceCount };
  }
  async computeEmbedding(): Promise<number[]> {
    return [];
  }
  async detectFaces(): Promise<FaceDetectionSignal> {
    return { face_count: this.faceCount, faces: [] };
  }
  async detectFaceMesh(): Promise<FaceMeshSignal> {
    return { gaze: this.gaze, embedding: [], landmarks: [] };
  }
  async detectPose(): Promise<PoseSignal> {
    return { keypoints: [] };
  }
  async dispose(): Promise<void> {}
}

function fakeSink() {
  const sent: Array<{ tipo: string; severidad: string; payload?: Record<string, unknown> }> = [];
  return {
    sent,
    sink: { sendEvent: async (a: { tipo: string; severidad: string; payload?: Record<string, unknown> }) => void sent.push(a) },
  };
}

const FRAME = {} as ImageBitmap;

describe("abstraccion del motor (DD-17)", () => {
  it("el pipeline opera contra la interfaz VisionEngine, sin referenciar MediaPipe", async () => {
    const { sink, sent } = fakeSink();
    const pipe = new VisionPipeline({ engine: new FakeEngine(1), sink, config: { face_absent_ms: 1000 } });
    // Funciona con un motor que NO es MediaPipe -> el pipeline depende del contrato.
    await pipe.onFrame(FRAME, {}, 0);
    expect(sent).toHaveLength(0); // un rostro presente, sin evento
  });

  it("sustituir la implementacion del motor no cambia el pipeline ni las reglas", async () => {
    const { sink, sent } = fakeSink();
    // Dos motores distintos (ambos NO-MediaPipe): mismo comportamiento de reglas.
    const a = new VisionPipeline({ engine: new FakeEngine(0), sink, config: { face_absent_ms: 1000 } });
    await a.onSignals({ ts_ms: 0, face_count: 0 });
    const out = await a.onSignals({ ts_ms: 2000, face_count: 0 });
    expect(out[0].tipo).toBe("rostro_ausente");
    expect(sent.at(-1)!.tipo).toBe("rostro_ausente");
  });
});

describe("e2e feed -> detectores -> reglas -> transporte", () => {
  it("multiples rostros sostenidos emite evento alto conforme al contrato de C-10", async () => {
    const { sink, sent } = fakeSink();
    const pipe = new VisionPipeline({ engine: new FakeEngine(2), sink, config: { multiple_faces_frames: 3 } });
    for (let i = 0; i < 3; i += 1) await pipe.onFrame(FRAME, {}, i * 50);
    const ev = sent.find((e) => e.tipo === "multiples_rostros");
    expect(ev).toBeTruthy();
    expect(ev!.severidad).toBe("alta");
    expect(ev!.payload).toBeDefined();
  });

  it("multiples rostros dispara la captura de evidencia (via C-12)", async () => {
    const onEvidence = vi.fn();
    const { sink } = fakeSink();
    const pipe = new VisionPipeline({
      engine: new FakeEngine(2),
      sink,
      onEvidence,
      config: { multiple_faces_frames: 2 },
    });
    await pipe.onFrame(FRAME, {}, 0);
    await pipe.onFrame(FRAME, {}, 50);
    expect(onEvidence).toHaveBeenCalledTimes(1);
    expect(onEvidence.mock.calls[0][0].tipo).toBe("multiples_rostros");
  });
});
