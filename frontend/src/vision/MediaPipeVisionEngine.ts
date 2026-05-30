/**
 * Implementacion MediaPipe del motor de vision (DD-17, C-09).
 *
 * Corre Face Mesh (468 landmarks) sobre WASM+WebGL en un Web Worker. Implementa la
 * interfaz ``VisionEngine`` para que la feature dependa del contrato, no de la
 * libreria (ruta a ONNX Runtime Web sin reescribir, DD-17). El embedding facial se
 * deriva de la geometria normalizada de los landmarks.
 *
 * La integracion concreta con ``@mediapipe/tasks-vision`` se cablea en el deploy
 * (carga del .wasm y del modelo). Aqui se deja la estructura y los hooks; el
 * cliente es un SENSOR NO CONFIABLE: el backend re-infiere (RN-GLB-01).
 */

import type {
  FaceDetectionSignal,
  FaceLandmark,
  FaceMeshSignal,
  FrameResult,
  PoseSignal,
  VisionEngine,
} from "./VisionEngine";

export class MediaPipeVisionEngine implements VisionEngine {
  private ready = false;

  // El runner concreto (FaceLandmarker de @mediapipe/tasks-vision) se inyecta en
  // el deploy. Se mantiene opaco para no atar el contrato a la libreria (DD-17).
  constructor(private readonly runner?: unknown) {}

  async init(): Promise<void> {
    // En produccion: cargar WASM + modelo Face Mesh y crear el FaceLandmarker.
    this.ready = true;
  }

  async processFrame(_frame: ImageBitmap | VideoFrame): Promise<FrameResult> {
    this.ensureReady();
    // En produccion: runner.detectForVideo(frame, ts) -> landmarks + face_count.
    throw new Error(
      "MediaPipeVisionEngine.processFrame requiere el runner de tasks-vision cableado en el deploy (DD-17).",
    );
  }

  async detectFaces(_frame: ImageBitmap | VideoFrame): Promise<FaceDetectionSignal> {
    this.ensureReady();
    // En produccion: FaceDetector.detectForVideo -> bounding boxes + confianza.
    throw new Error(
      "MediaPipeVisionEngine.detectFaces requiere el FaceDetector de tasks-vision (DD-17).",
    );
  }

  async detectFaceMesh(_frame: ImageBitmap | VideoFrame): Promise<FaceMeshSignal> {
    this.ensureReady();
    // En produccion: FaceLandmarker -> landmarks (iris) -> gaze + embedding.
    throw new Error(
      "MediaPipeVisionEngine.detectFaceMesh requiere el FaceLandmarker de tasks-vision (DD-17).",
    );
  }

  async detectPose(_frame: ImageBitmap | VideoFrame): Promise<PoseSignal> {
    this.ensureReady();
    // En produccion: PoseLandmarker.detectForVideo -> keypoints del cuerpo.
    throw new Error(
      "MediaPipeVisionEngine.detectPose requiere el PoseLandmarker de tasks-vision (DD-17).",
    );
  }

  async computeEmbedding(frames: FrameResult[]): Promise<number[]> {
    this.ensureReady();
    // Embedding = promedio normalizado de la geometria de los landmarks por frame.
    // Aqui se deja la derivacion determinista del contrato; el grafo real corre en
    // el Worker. Si no hay frames, no hay embedding.
    if (frames.length === 0) {
      throw new Error("Sin frames: no se puede calcular el embedding.");
    }
    return embeddingFromLandmarks(frames.flatMap((f) => f.landmarks));
  }

  async dispose(): Promise<void> {
    this.ready = false;
  }

  private ensureReady(): void {
    if (!this.ready) {
      throw new Error("MediaPipeVisionEngine no inicializado: llama a init() primero.");
    }
  }
}

/**
 * Deriva un embedding determinista de una lista de landmarks (centrando y
 * normalizando la geometria). Pura y testeable; la version de produccion usa el
 * grafo de Face Mesh, pero el CONTRATO (vector de floats) es el mismo.
 */
export function embeddingFromLandmarks(landmarks: FaceLandmark[]): number[] {
  if (landmarks.length === 0) return [];
  const n = landmarks.length;
  const cx = landmarks.reduce((s, l) => s + l.x, 0) / n;
  const cy = landmarks.reduce((s, l) => s + l.y, 0) / n;
  const cz = landmarks.reduce((s, l) => s + l.z, 0) / n;
  // Vector aplanado centrado (x-cx, y-cy, z-cz) por landmark.
  const flat: number[] = [];
  for (const l of landmarks) {
    flat.push(l.x - cx, l.y - cy, l.z - cz);
  }
  const norm = Math.sqrt(flat.reduce((s, v) => s + v * v, 0)) || 1;
  return flat.map((v) => v / norm);
}

/**
 * Estima la direccion de la mirada a partir del centro del iris relativo al centro
 * de los ojos (esquinas). Devuelve un vector normalizado (-1..1) donde (0,0) es
 * mirada al frente. Pura y testeable; la version de produccion usa los landmarks de
 * iris de Face Mesh, pero el CONTRATO (vector gaze) es el mismo (RN-EV-06).
 */
export function gazeFromIris(
  irisCenter: { x: number; y: number },
  eyeLeft: { x: number; y: number },
  eyeRight: { x: number; y: number },
): { x: number; y: number } {
  const cx = (eyeLeft.x + eyeRight.x) / 2;
  const cy = (eyeLeft.y + eyeRight.y) / 2;
  const halfWidth = Math.abs(eyeRight.x - eyeLeft.x) / 2 || 1;
  // Desplazamiento del iris respecto al centro, escalado por el semi-ancho del ojo.
  const gx = clamp((irisCenter.x - cx) / halfWidth, -1, 1);
  const gy = clamp((irisCenter.y - cy) / halfWidth, -1, 1);
  return { x: gx, y: gy };
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}
