/**
 * RealMediaPipeVisionEngine — implementación real del motor de visión usando
 * @mediapipe/tasks-vision Tasks API (C-30, D-1, D-7).
 *
 * IMPORTANTE: Este archivo NO debe importarse directamente en el código de
 * producción. Solo se carga vía dynamic import desde `harnessEngineLoader.ts`
 * (D-2) para garantizar el chunk split de Vite y que @mediapipe/tasks-vision
 * NO entre en el bundle inicial (RD-8, bundle < 500 KB).
 *
 * Modelos servidos LOCALMENTE desde /mediapipe/ (soberanía de datos, RD-7).
 * NUNCA desde CDN externo en runtime.
 *
 * Fallback honesto (D-6): si init() falla, lanza Error descriptivo. No simula.
 */

import {
  FaceDetector,
  FaceLandmarker,
  PoseLandmarker,
  FilesetResolver,
} from "@mediapipe/tasks-vision";
import type { FaceDetectorResult, FaceLandmarkerResult, PoseLandmarkerResult } from "@mediapipe/tasks-vision";

import {
  embeddingFromLandmarks,
  gazeFromIris,
} from "./MediaPipeVisionEngine";
import type {
  FaceDetectionSignal,
  FaceLandmark,
  FaceMeshSignal,
  FrameResult,
  PoseKeypoint,
  PoseSignal,
  VisionEngine,
} from "./VisionEngine";

// Índices de landmarks de iris en FaceLandmarker (468 + iris extras)
// Iris izquierdo: 468–471, iris derecho: 473–476
// Centro del iris izquierdo: 468, centro del iris derecho: 473
// Esquinas del ojo izquierdo: 33 (right corner), 133 (left corner)
// Esquinas del ojo derecho: 362 (left corner), 263 (right corner)
const IRIS_LEFT_CENTER = 468;
const IRIS_RIGHT_CENTER = 473;
const EYE_LEFT_OUTER = 33;
const EYE_LEFT_INNER = 133;
const EYE_RIGHT_INNER = 362;
const EYE_RIGHT_OUTER = 263;

/** Ruta base donde Vite sirve los modelos desde frontend/public/mediapipe/ */
const MODEL_BASE_PATH = "/mediapipe";

export class RealMediaPipeVisionEngine implements VisionEngine {
  private ready = false;
  private faceDetector: FaceDetector | null = null;
  private faceLandmarker: FaceLandmarker | null = null;
  private poseLandmarker: PoseLandmarker | null = null;

  /** Timestamp del último frame procesado (requerido por detectForVideo). */
  private lastFrameTs = 0;

  async init(): Promise<void> {
    // Verificar WebGL antes de intentar cargar cualquier modelo
    if (!this.isWebGLAvailable()) {
      throw new Error(
        "WebGL no disponible en este entorno. MediaPipe Tasks API requiere WebGL para el delegado GPU. " +
        "Verificá que WebGL esté habilitado en tu navegador (chrome://flags/#disable-webgl).",
      );
    }

    // Resolver el fileset WASM desde rutas locales self-hosted (RD-7: soberanía de datos).
    //
    // Los archivos WASM se sirven desde /mediapipe/wasm/ — copiados del paquete npm
    // por el script de setup (scripts/download-mediapipe-models.sh/.ps1).
    //
    // Ruta WASM: frontend/public/mediapipe/wasm/ → servida como /mediapipe/wasm/ por Vite/Nginx.
    // En dev: Vite sirve public/ estáticamente. En prod: Nginx sirve el dist/ de Vite.
    // NUNCA desde CDN externo en runtime (RD-7).
    let vision;
    try {
      vision = await FilesetResolver.forVisionTasks(
        `${MODEL_BASE_PATH}/wasm`,
      );
    } catch (err) {
      throw new Error(
        `No se pudo inicializar el fileset WASM de MediaPipe desde /mediapipe/wasm/.\n` +
        `Error: ${err instanceof Error ? err.message : String(err)}\n` +
        "Para instalar los archivos WASM, ejecutá:\n" +
        "  bash: scripts/download-mediapipe-models.sh\n" +
        "  Windows: scripts\\download-mediapipe-models.ps1",
      );
    }

    // --- FaceDetector ---
    await this.loadFaceDetector(vision);

    // --- FaceLandmarker ---
    await this.loadFaceLandmarker(vision);

    // --- PoseLandmarker ---
    await this.loadPoseLandmarker(vision);

    this.ready = true;
  }

  // -------------------------------------------------------------------------
  // Loaders individuales (D-2.2, D-2.3, D-2.4)
  // -------------------------------------------------------------------------

  private async loadFaceDetector(vision: Awaited<ReturnType<typeof FilesetResolver.forVisionTasks>>): Promise<void> {
    const modelPath = `${MODEL_BASE_PATH}/face_detector_short_range.task`;
    try {
      // Intentar con delegado GPU primero; si falla, CPU como fallback
      try {
        this.faceDetector = await FaceDetector.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath: modelPath,
            delegate: "GPU",
          },
          runningMode: "VIDEO",
          minDetectionConfidence: 0.5,
          minSuppressionThreshold: 0.3,
        });
      } catch {
        this.faceDetector = await FaceDetector.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath: modelPath,
            delegate: "CPU",
          },
          runningMode: "VIDEO",
          minDetectionConfidence: 0.5,
          minSuppressionThreshold: 0.3,
        });
      }
    } catch (err) {
      this.checkModelNotFound(err, modelPath);
      throw err;
    }
  }

  private async loadFaceLandmarker(vision: Awaited<ReturnType<typeof FilesetResolver.forVisionTasks>>): Promise<void> {
    const modelPath = `${MODEL_BASE_PATH}/face_landmarker.task`;
    try {
      try {
        this.faceLandmarker = await FaceLandmarker.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath: modelPath,
            delegate: "GPU",
          },
          runningMode: "VIDEO",
          numFaces: 4,
          minFaceDetectionConfidence: 0.5,
          minFacePresenceConfidence: 0.5,
          minTrackingConfidence: 0.5,
          outputFaceBlendshapes: false,
          outputFacialTransformationMatrixes: false,
        });
      } catch {
        this.faceLandmarker = await FaceLandmarker.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath: modelPath,
            delegate: "CPU",
          },
          runningMode: "VIDEO",
          numFaces: 4,
          minFaceDetectionConfidence: 0.5,
          minFacePresenceConfidence: 0.5,
          minTrackingConfidence: 0.5,
          outputFaceBlendshapes: false,
          outputFacialTransformationMatrixes: false,
        });
      }
    } catch (err) {
      this.checkModelNotFound(err, modelPath);
      throw err;
    }
  }

  private async loadPoseLandmarker(vision: Awaited<ReturnType<typeof FilesetResolver.forVisionTasks>>): Promise<void> {
    const modelPath = `${MODEL_BASE_PATH}/pose_landmarker_lite.task`;
    try {
      try {
        this.poseLandmarker = await PoseLandmarker.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath: modelPath,
            delegate: "GPU",
          },
          runningMode: "VIDEO",
          numPoses: 1,
          minPoseDetectionConfidence: 0.5,
          minPosePresenceConfidence: 0.5,
          minTrackingConfidence: 0.5,
        });
      } catch {
        this.poseLandmarker = await PoseLandmarker.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath: modelPath,
            delegate: "CPU",
          },
          runningMode: "VIDEO",
          numPoses: 1,
          minPoseDetectionConfidence: 0.5,
          minPosePresenceConfidence: 0.5,
          minTrackingConfidence: 0.5,
        });
      }
    } catch (err) {
      this.checkModelNotFound(err, modelPath);
      throw err;
    }
  }

  // -------------------------------------------------------------------------
  // Métodos de detección (implementan VisionEngine)
  // -------------------------------------------------------------------------

  async detectFaces(frame: ImageBitmap | VideoFrame): Promise<FaceDetectionSignal> {
    this.ensureReady();
    const ts = this.nextTimestamp();
    const result: FaceDetectorResult = this.faceDetector!.detectForVideo(frame as ImageBitmap, ts);

    const faces = (result.detections ?? []).map((det) => {
      const box = det.boundingBox ?? { originX: 0, originY: 0, width: 0, height: 0 };
      // Normalizar coordenadas a 0..1 respecto al tamaño del frame
      const fw = (frame as ImageBitmap).width || 1;
      const fh = (frame as ImageBitmap).height || 1;
      const confidence = det.categories?.[0]?.score ?? 0;
      return {
        x: box.originX / fw,
        y: box.originY / fh,
        width: box.width / fw,
        height: box.height / fh,
        confidence,
      };
    });

    return {
      face_count: faces.length,
      faces,
    };
  }

  async detectFaceMesh(frame: ImageBitmap | VideoFrame): Promise<FaceMeshSignal> {
    this.ensureReady();
    const ts = this.nextTimestamp();
    const result: FaceLandmarkerResult = this.faceLandmarker!.detectForVideo(frame as ImageBitmap, ts);

    const faceLandmarks = result.faceLandmarks?.[0] ?? [];

    // Mapear a FaceLandmark[]
    const landmarks: FaceLandmark[] = faceLandmarks.map((lm) => ({
      x: lm.x,
      y: lm.y,
      z: lm.z ?? 0,
    }));

    // Calcular gaze usando iris landmarks (índices 468+ en FaceLandmarker)
    let gaze = { x: 0, y: 0 };
    if (faceLandmarks.length > IRIS_LEFT_CENTER) {
      const irisCenter = faceLandmarks[IRIS_LEFT_CENTER];
      const eyeLeft = faceLandmarks[EYE_LEFT_OUTER];
      const eyeRight = faceLandmarks[EYE_LEFT_INNER];
      if (irisCenter && eyeLeft && eyeRight) {
        gaze = gazeFromIris(irisCenter, eyeLeft, eyeRight);
      }
    } else if (faceLandmarks.length > EYE_RIGHT_OUTER) {
      // Fallback: usar ojo derecho si iris izquierdo no disponible
      const irisCenter = faceLandmarks[IRIS_RIGHT_CENTER] ?? faceLandmarks[EYE_RIGHT_INNER];
      const eyeLeft = faceLandmarks[EYE_RIGHT_INNER];
      const eyeRight = faceLandmarks[EYE_RIGHT_OUTER];
      if (irisCenter && eyeLeft && eyeRight) {
        gaze = gazeFromIris(irisCenter, eyeLeft, eyeRight);
      }
    }

    const embedding = embeddingFromLandmarks(landmarks);

    return { gaze, embedding, landmarks };
  }

  async detectPose(frame: ImageBitmap | VideoFrame): Promise<PoseSignal> {
    this.ensureReady();
    const ts = this.nextTimestamp();
    const result: PoseLandmarkerResult = this.poseLandmarker!.detectForVideo(frame as ImageBitmap, ts);

    const poseLandmarks = result.landmarks?.[0] ?? [];
    const keypoints: PoseKeypoint[] = poseLandmarks.map((lm) => ({
      x: lm.x,
      y: lm.y,
      visibility: lm.visibility ?? 0,
    }));

    return { keypoints };
  }

  async processFrame(frame: ImageBitmap | VideoFrame): Promise<FrameResult> {
    this.ensureReady();
    const faceDetection = await this.detectFaces(frame);
    const face_count = faceDetection.face_count;

    let landmarks: FaceLandmark[] = [];
    if (face_count >= 1) {
      try {
        const mesh = await this.detectFaceMesh(frame);
        landmarks = mesh.landmarks;
      } catch {
        // FaceMesh puede fallar si el FaceDetector detectó pero el Landmarker no convergió
      }
    }

    return { landmarks, face_count };
  }

  async computeEmbedding(frames: FrameResult[]): Promise<number[]> {
    this.ensureReady();
    if (frames.length === 0) {
      throw new Error("Sin frames: no se puede calcular el embedding.");
    }
    return embeddingFromLandmarks(frames.flatMap((f) => f.landmarks));
  }

  async dispose(): Promise<void> {
    try { this.faceDetector?.close(); } catch { /* ignorar */ }
    try { this.faceLandmarker?.close(); } catch { /* ignorar */ }
    try { this.poseLandmarker?.close(); } catch { /* ignorar */ }
    this.faceDetector = null;
    this.faceLandmarker = null;
    this.poseLandmarker = null;
    this.ready = false;
  }

  // -------------------------------------------------------------------------
  // Helpers privados
  // -------------------------------------------------------------------------

  private ensureReady(): void {
    if (!this.ready) {
      throw new Error(
        "RealMediaPipeVisionEngine no inicializado: llamá a init() primero.",
      );
    }
  }

  /** Genera un timestamp incremental para detectForVideo (requiere monotónico). */
  private nextTimestamp(): number {
    const ts = performance.now();
    // detectForVideo requiere que el timestamp sea estrictamente mayor al anterior
    if (ts <= this.lastFrameTs) {
      this.lastFrameTs = this.lastFrameTs + 1;
    } else {
      this.lastFrameTs = ts;
    }
    return this.lastFrameTs;
  }

  private isWebGLAvailable(): boolean {
    try {
      const canvas = document.createElement("canvas");
      return !!(
        canvas.getContext("webgl2") ??
        canvas.getContext("webgl") ??
        canvas.getContext("experimental-webgl")
      );
    } catch {
      return false;
    }
  }

  /**
   * Si el error parece ser un 404/modelo no encontrado, relanza con mensaje descriptivo
   * que incluye el path del modelo y las instrucciones de descarga.
   */
  private checkModelNotFound(err: unknown, modelPath: string): void {
    const msg = err instanceof Error ? err.message : String(err);
    const isNotFound =
      msg.includes("404") ||
      msg.includes("not found") ||
      msg.includes("Failed to fetch") ||
      msg.includes("NetworkError") ||
      msg.toLowerCase().includes("load");

    if (isNotFound) {
      throw new Error(
        `Modelo no encontrado: ${modelPath}\n` +
        "Para descargar los modelos, ejecutá:\n" +
        "  bash: scripts/download-mediapipe-models.sh\n" +
        "  Windows: scripts\\download-mediapipe-models.ps1",
      );
    }
  }
}
