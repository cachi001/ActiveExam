/**
 * Motor de vision ABSTRAIDO detras de interfaz (DD-17, C-09).
 *
 * El cliente calcula el embedding y las senales de liveness con MediaPipe Face
 * Mesh (468 landmarks) en un Web Worker. Pero el motor concreto va DETRAS DE UNA
 * INTERFAZ: el resto del codigo depende de ``VisionEngine``, no de MediaPipe, de
 * modo que la ruta a ONNX Runtime Web (DD-17) o a otro backend no obligue a
 * reescribir la feature. El cliente es un SENSOR NO CONFIABLE (RN-GLB-01): lo que
 * produce aqui es una SENAL; el backend re-infiere sobre el clip y decide.
 *
 * Convencion del proyecto: motor abstraido + tipos snake_case en los contratos de
 * red, camelCase en el codigo TS.
 */

/** Landmark 3D de Face Mesh (x, y normalizados; z = profundidad relativa). */
export interface FaceLandmark {
  x: number;
  y: number;
  z: number;
}

/** Senales pasivas de liveness derivadas de la geometria de los landmarks. */
export interface PassiveSignals {
  parpadeo_detectado: boolean;
  micro_movimientos: boolean;
  profundidad_3d_coherente: boolean;
}

/** Caja delimitadora normalizada (0..1) de un rostro detectado. */
export interface FaceBox {
  x: number;
  y: number;
  width: number;
  height: number;
  /** Score de confianza del detector para este rostro (0..1). */
  confidence: number;
}

/** Punto clave de pose normalizado (x, y en 0..1; visibility 0..1). */
export interface PoseKeypoint {
  x: number;
  y: number;
  visibility: number;
}

/**
 * Senal continua de Face Detection (5-10 fps): conteo de rostros y sus cajas con
 * confianza (RN-EV-04, ausencia / multiples rostros).
 */
export interface FaceDetectionSignal {
  face_count: number;
  faces: FaceBox[];
}

/**
 * Senal continua de Face Mesh (5-10 fps): direccion de mirada por iris + embedding
 * facial para la verificacion silenciosa continua (RN-BIO-06).
 */
export interface FaceMeshSignal {
  /** Direccion de la mirada normalizada respecto al centro del marco (-1..1). */
  gaze: { x: number; y: number };
  /** Embedding facial derivado de la geometria (verificacion continua). */
  embedding: number[];
  landmarks: FaceLandmark[];
}

/** Senal continua de Pose (2-5 fps): puntos clave del cuerpo (postura de consulta). */
export interface PoseSignal {
  keypoints: PoseKeypoint[];
}

/** Resultado de procesar un frame: landmarks + senales puntuales. */
export interface FrameResult {
  landmarks: FaceLandmark[];
  /** Cantidad de rostros detectados en el frame (0, 1 o >1). */
  face_count: number;
}

/**
 * Identidad de cada detector de vision; usada por la degradacion graceful para
 * bajar detectores en orden (Pose -> Face Mesh) (RN-GLB-03).
 */
export type DetectorKind = "face_detection" | "face_mesh" | "pose";

/**
 * Interfaz del motor de vision. La implementacion MediaPipe vive en
 * ``MediaPipeVisionEngine``; los tests/otros backends (ONNX Runtime Web, DD-17)
 * implementan esta interfaz. Las reglas de transicion y el transporte SOLO conocen
 * este contrato, nunca tipos de MediaPipe.
 */
export interface VisionEngine {
  /** Inicializa el grafo del motor (carga WASM/modelo). Idempotente. */
  init(): Promise<void>;
  /** Procesa un frame de video y devuelve landmarks + conteo de rostros. */
  processFrame(frame: ImageBitmap | VideoFrame): Promise<FrameResult>;
  /** Calcula el embedding facial a partir de una secuencia de frames del clip. */
  computeEmbedding(frames: FrameResult[]): Promise<number[]>;
  /** Face Detection (5-10 fps): bounding boxes + confianza por rostro. */
  detectFaces(frame: ImageBitmap | VideoFrame): Promise<FaceDetectionSignal>;
  /** Face Mesh (5-10 fps): mirada (iris) + embedding facial. */
  detectFaceMesh(frame: ImageBitmap | VideoFrame): Promise<FaceMeshSignal>;
  /** Pose (2-5 fps): puntos clave del cuerpo para postura de consulta. */
  detectPose(frame: ImageBitmap | VideoFrame): Promise<PoseSignal>;
  /** Libera los recursos del motor. */
  dispose(): Promise<void>;
}
