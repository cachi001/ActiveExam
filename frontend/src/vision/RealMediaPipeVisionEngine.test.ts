/**
 * Tests de RealMediaPipeVisionEngine (C-30, real-vision-engine-harness).
 *
 * Verifica que la clase satisface el contrato VisionEngine y que el mapeo de
 * señales es correcto, usando mocks de los runners de @mediapipe/tasks-vision.
 *
 * NOTA: En este entorno (jsdom) WebGL no está disponible, por lo que init()
 * lanzará error de WebGL. Los tests de señales mockean los runners directamente
 * sin pasar por init().
 */

import { describe, expect, it, vi, beforeEach } from "vitest";

// Mockear @mediapipe/tasks-vision antes de importar el motor
vi.mock("@mediapipe/tasks-vision", () => {
  const makeMockRunner = () => ({
    detectForVideo: vi.fn(),
    close: vi.fn(),
  });

  return {
    FaceDetector: {
      createFromOptions: vi.fn().mockResolvedValue(makeMockRunner()),
    },
    FaceLandmarker: {
      createFromOptions: vi.fn().mockResolvedValue(makeMockRunner()),
    },
    PoseLandmarker: {
      createFromOptions: vi.fn().mockResolvedValue(makeMockRunner()),
    },
    FilesetResolver: {
      forVisionTasks: vi.fn().mockResolvedValue({}),
    },
  };
});

import { RealMediaPipeVisionEngine } from "./RealMediaPipeVisionEngine";
import type { VisionEngine } from "./VisionEngine";

// Verificar que RealMediaPipeVisionEngine satisface el contrato VisionEngine
describe("RealMediaPipeVisionEngine — contrato VisionEngine", () => {
  it("tiene todos los métodos del contrato VisionEngine", () => {
    const engine = new RealMediaPipeVisionEngine();
    // Verificar que implementa la interfaz VisionEngine
    const contract: VisionEngine = engine;
    expect(typeof contract.init).toBe("function");
    expect(typeof contract.processFrame).toBe("function");
    expect(typeof contract.computeEmbedding).toBe("function");
    expect(typeof contract.detectFaces).toBe("function");
    expect(typeof contract.detectFaceMesh).toBe("function");
    expect(typeof contract.detectPose).toBe("function");
    expect(typeof contract.dispose).toBe("function");
  });

  it("es una instancia asignable a VisionEngine", () => {
    const engine: VisionEngine = new RealMediaPipeVisionEngine();
    expect(engine).toBeInstanceOf(RealMediaPipeVisionEngine);
  });
});

describe("RealMediaPipeVisionEngine — mapeo de señales (runners mockeados)", () => {
  let engine: RealMediaPipeVisionEngine;

  beforeEach(() => {
    engine = new RealMediaPipeVisionEngine();
    // Inyectar runners mockeados directamente (bypass de init() para tests unitarios)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (engine as any).ready = true;
  });

  it("detectFaces: 2 detecciones → face_count = 2 con FaceBox normalizados", async () => {
    const mockDetector = {
      detectForVideo: vi.fn().mockReturnValue({
        detections: [
          {
            boundingBox: { originX: 100, originY: 50, width: 200, height: 300 },
            categories: [{ score: 0.95 }],
          },
          {
            boundingBox: { originX: 400, originY: 80, width: 180, height: 280 },
            categories: [{ score: 0.87 }],
          },
        ],
      }),
      close: vi.fn(),
    };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (engine as any).faceDetector = mockDetector;

    const mockFrame = { width: 1000, height: 600 } as ImageBitmap;
    const result = await engine.detectFaces(mockFrame);

    expect(result.face_count).toBe(2);
    expect(result.faces).toHaveLength(2);
    expect(mockDetector.detectForVideo).toHaveBeenCalledTimes(1);

    // Verificar normalización: x=100/1000=0.1, y=50/600≈0.083
    expect(result.faces[0].x).toBeCloseTo(0.1, 5);
    expect(result.faces[0].y).toBeCloseTo(50 / 600, 5);
    expect(result.faces[0].confidence).toBe(0.95);
    expect(result.faces[1].confidence).toBe(0.87);
  });

  it("detectFaces: 0 detecciones → face_count = 0", async () => {
    const mockDetector = {
      detectForVideo: vi.fn().mockReturnValue({ detections: [] }),
      close: vi.fn(),
    };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (engine as any).faceDetector = mockDetector;

    const mockFrame = { width: 640, height: 480 } as ImageBitmap;
    const result = await engine.detectFaces(mockFrame);

    expect(result.face_count).toBe(0);
    expect(result.faces).toHaveLength(0);
  });

  it("detectFaceMesh: landmarks mapeados a FaceLandmark[] correctamente", async () => {
    const landmarksMock = Array.from({ length: 478 }, (_, i) => ({
      x: i * 0.001,
      y: i * 0.002,
      z: 0,
    }));

    const mockLandmarker = {
      detectForVideo: vi.fn().mockReturnValue({
        faceLandmarks: [landmarksMock],
      }),
      close: vi.fn(),
    };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (engine as any).faceLandmarker = mockLandmarker;

    const mockFrame = { width: 640, height: 480 } as ImageBitmap;
    const result = await engine.detectFaceMesh(mockFrame);

    expect(result.landmarks).toHaveLength(478);
    expect(result.landmarks[0]).toMatchObject({ x: 0, y: 0, z: 0 });
    expect(result.embedding).toBeInstanceOf(Array);
    // gaze es un vector {x, y}
    expect(typeof result.gaze.x).toBe("number");
    expect(typeof result.gaze.y).toBe("number");
  });

  it("detectFaceMesh: sin landmarks → landmarks vacíos y gaze (0, 0)", async () => {
    const mockLandmarker = {
      detectForVideo: vi.fn().mockReturnValue({ faceLandmarks: [] }),
      close: vi.fn(),
    };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (engine as any).faceLandmarker = mockLandmarker;

    const mockFrame = { width: 640, height: 480 } as ImageBitmap;
    const result = await engine.detectFaceMesh(mockFrame);

    expect(result.landmarks).toHaveLength(0);
    expect(result.gaze).toEqual({ x: 0, y: 0 });
    expect(result.embedding).toEqual([]);
  });

  it("detectPose: landmarks mapeados a PoseKeypoint[] con visibility", async () => {
    const poseMock = [
      { x: 0.5, y: 0.3, z: 0, visibility: 0.9 },
      { x: 0.6, y: 0.4, z: 0, visibility: 0.7 },
    ];
    const mockPose = {
      detectForVideo: vi.fn().mockReturnValue({ landmarks: [poseMock] }),
      close: vi.fn(),
    };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (engine as any).poseLandmarker = mockPose;

    const mockFrame = { width: 640, height: 480 } as ImageBitmap;
    const result = await engine.detectPose(mockFrame);

    expect(result.keypoints).toHaveLength(2);
    expect(result.keypoints[0]).toMatchObject({ x: 0.5, y: 0.3, visibility: 0.9 });
  });

  it("dispose: cierra todos los runners y deja ready = false", async () => {
    const mockFaceDetector = { close: vi.fn(), detectForVideo: vi.fn() };
    const mockFaceLandmarker = { close: vi.fn(), detectForVideo: vi.fn() };
    const mockPoseLandmarker = { close: vi.fn(), detectForVideo: vi.fn() };

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (engine as any).faceDetector = mockFaceDetector;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (engine as any).faceLandmarker = mockFaceLandmarker;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (engine as any).poseLandmarker = mockPoseLandmarker;

    await engine.dispose();

    expect(mockFaceDetector.close).toHaveBeenCalledTimes(1);
    expect(mockFaceLandmarker.close).toHaveBeenCalledTimes(1);
    expect(mockPoseLandmarker.close).toHaveBeenCalledTimes(1);

    // Después de dispose, ensureReady debería lanzar
    await expect(engine.detectFaces({} as ImageBitmap)).rejects.toThrow(
      "no inicializado",
    );
  });
});
