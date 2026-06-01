/**
 * VisionOverlay — canvas superpuesto al video del harness de diagnóstico (C-30, D-4).
 *
 * Dibuja sobre un <canvas> con position:absolute las señales de visión detectadas:
 * - Bounding boxes de rostros con label y confianza
 * - Landmarks de Face Mesh (subconjunto canónico o 468 puntos completos)
 * - Vector gaze como línea desde el centro del rostro
 * - Keypoints de pose (opcional, solo si showPose === true)
 *
 * El canvas es `pointer-events: none` para no interferir con controles del video.
 * Se sincroniza con las dimensiones del video via ResizeObserver.
 *
 * PascalCase por convención del proyecto (regla dura #7).
 */

import { useRef, useEffect, type RefObject } from "react";
import type { FaceDetectionSignal, FaceMeshSignal, PoseSignal } from "../vision/VisionEngine";

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------

export interface RawSignals {
  faceDetection: FaceDetectionSignal | null;
  faceMesh: FaceMeshSignal | null;
  poseAvailable: boolean;
  poseSignal?: PoseSignal | null;
  frameTs: number;
}

interface VisionOverlayProps {
  rawSignals: RawSignals | null;
  videoRef: RefObject<HTMLVideoElement>;
  showFullMesh?: boolean;
  showPose?: boolean;
}

// ---------------------------------------------------------------------------
// Subconjunto canónico de 68 landmarks (contorno de cara, ojos, cejas, nariz, boca)
// Basado en los índices estándar de Face Mesh 468 para legibilidad visual.
// ---------------------------------------------------------------------------

const CANONICAL_68_INDICES: number[] = [
  // Óvalo facial
  10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
  397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
  172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109,
  // Ceja izquierda
  70, 63, 105, 66, 107,
  // Ceja derecha
  336, 296, 334, 293, 300,
  // Puente nasal
  168, 6, 195, 4,
  // Ojo izquierdo
  33, 7, 163, 144, 145, 153, 154, 155, 133,
  // Ojo derecho
  362, 382, 381, 380, 374, 373, 390, 249, 263,
  // Nariz inferior
  1, 2, 98, 327,
  // Boca exterior
  61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 375, 321, 405, 314, 17, 84, 181, 91, 146,
];

// Colores del overlay
const COLOR_FACE_BOX = "#ff4444";
const COLOR_MESH_CANONICAL = "rgba(0, 255, 120, 0.7)";
const COLOR_MESH_FULL = "rgba(0, 200, 255, 0.4)";
const COLOR_GAZE = "#ffcc00";
const COLOR_POSE_LINE = "rgba(100, 180, 255, 0.5)";

// Conexiones de pose (pares de índices de MediaPipe Pose 33 keypoints)
const POSE_CONNECTIONS: [number, number][] = [
  // Hombros
  [11, 12],
  // Hombro izquierdo → codo → muñeca
  [11, 13], [13, 15],
  // Hombro derecho → codo → muñeca
  [12, 14], [14, 16],
  // Caderas
  [23, 24],
  // Cadera izquierda → rodilla → tobillo
  [23, 25], [25, 27],
  // Cadera derecha → rodilla → tobillo
  [24, 26], [26, 28],
  // Torso
  [11, 23], [12, 24],
];

// ---------------------------------------------------------------------------
// Función de dibujo
// ---------------------------------------------------------------------------

export function drawFrame(
  ctx: CanvasRenderingContext2D,
  rawSignals: RawSignals,
  videoW: number,
  videoH: number,
  showFullMesh: boolean,
  showPose: boolean,
): void {
  // 1. Limpiar
  ctx.clearRect(0, 0, videoW, videoH);

  if (!rawSignals.faceDetection) return;

  const { faceDetection, faceMesh, poseAvailable, poseSignal } = rawSignals;

  // 2. Bounding boxes de rostros
  ctx.lineWidth = 2;
  ctx.font = "bold 13px monospace";

  faceDetection.faces.forEach((face, i) => {
    const x = face.x * videoW;
    const y = face.y * videoH;
    const w = face.width * videoW;
    const h = face.height * videoH;
    const confidence = Math.round(face.confidence * 100);

    // Rectángulo
    ctx.strokeStyle = COLOR_FACE_BOX;
    ctx.strokeRect(x, y, w, h);

    // Label "Rostro N (XX%)"
    const label = `Rostro ${i + 1} (${confidence}%)`;
    const labelX = x;
    const labelY = y > 18 ? y - 4 : y + h + 16;
    ctx.fillStyle = "rgba(0,0,0,0.65)";
    const metrics = ctx.measureText(label);
    ctx.fillRect(labelX - 2, labelY - 13, metrics.width + 4, 16);
    ctx.fillStyle = COLOR_FACE_BOX;
    ctx.fillText(label, labelX, labelY);
  });

  // 3. Landmarks de Face Mesh
  if (faceMesh && faceMesh.landmarks.length > 0) {
    const landmarks = faceMesh.landmarks;

    if (showFullMesh) {
      // Todos los 468 puntos (o los que haya)
      ctx.fillStyle = COLOR_MESH_FULL;
      for (const lm of landmarks) {
        ctx.beginPath();
        ctx.arc(lm.x * videoW, lm.y * videoH, 1.5, 0, Math.PI * 2);
        ctx.fill();
      }
    } else {
      // Subconjunto canónico de 68 puntos
      ctx.fillStyle = COLOR_MESH_CANONICAL;
      for (const idx of CANONICAL_68_INDICES) {
        const lm = landmarks[idx];
        if (!lm) continue;
        ctx.beginPath();
        ctx.arc(lm.x * videoW, lm.y * videoH, 2, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // 4. Vector gaze
    if (faceDetection.faces.length > 0) {
      const firstFace = faceDetection.faces[0];
      const centerX = (firstFace.x + firstFace.width / 2) * videoW;
      const centerY = (firstFace.y + firstFace.height / 2) * videoH;
      drawGazeArrow(ctx, centerX, centerY, faceMesh.gaze.x, faceMesh.gaze.y, videoH);
    } else {
      // Sin box pero con mesh — usar centro del canvas
      drawGazeArrow(ctx, videoW / 2, videoH / 2, faceMesh.gaze.x, faceMesh.gaze.y, videoH);
    }
  }

  // 5. Keypoints de pose
  if (showPose && poseAvailable && poseSignal && poseSignal.keypoints.length > 0) {
    const kps = poseSignal.keypoints;

    // Conexiones
    ctx.strokeStyle = COLOR_POSE_LINE;
    ctx.lineWidth = 2;
    for (const [a, b] of POSE_CONNECTIONS) {
      const kpA = kps[a];
      const kpB = kps[b];
      if (!kpA || !kpB) continue;
      if (kpA.visibility < 0.3 || kpB.visibility < 0.3) continue;
      ctx.beginPath();
      ctx.moveTo(kpA.x * videoW, kpA.y * videoH);
      ctx.lineTo(kpB.x * videoW, kpB.y * videoH);
      ctx.stroke();
    }

    // Puntos
    for (const kp of kps) {
      const alpha = Math.max(0.2, kp.visibility);
      ctx.fillStyle = `rgba(100, 180, 255, ${alpha})`;
      ctx.beginPath();
      ctx.arc(kp.x * videoW, kp.y * videoH, 4, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}

function drawGazeArrow(
  ctx: CanvasRenderingContext2D,
  fromX: number,
  fromY: number,
  gazeX: number,
  gazeY: number,
  videoH: number,
): void {
  const length = videoH * 0.15; // Flecha del 15% de la altura del video
  const toX = fromX + gazeX * length;
  const toY = fromY + gazeY * length;

  ctx.strokeStyle = COLOR_GAZE;
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  ctx.moveTo(fromX, fromY);
  ctx.lineTo(toX, toY);
  ctx.stroke();

  // Punta de flecha
  const angle = Math.atan2(toY - fromY, toX - fromX);
  const arrowLen = 10;
  ctx.beginPath();
  ctx.moveTo(toX, toY);
  ctx.lineTo(
    toX - arrowLen * Math.cos(angle - Math.PI / 6),
    toY - arrowLen * Math.sin(angle - Math.PI / 6),
  );
  ctx.moveTo(toX, toY);
  ctx.lineTo(
    toX - arrowLen * Math.cos(angle + Math.PI / 6),
    toY - arrowLen * Math.sin(angle + Math.PI / 6),
  );
  ctx.stroke();
}

// ---------------------------------------------------------------------------
// Componente React
// ---------------------------------------------------------------------------

export default function VisionOverlay({
  rawSignals,
  videoRef,
  showFullMesh = false,
  showPose = false,
}: VisionOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Sincronizar tamaño del canvas con el video via ResizeObserver
  useEffect(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    const updateSize = () => {
      if (video.videoWidth > 0 && video.videoHeight > 0) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
      } else {
        // Fallback: usar el tamaño CSS del video
        canvas.width = video.clientWidth || 640;
        canvas.height = video.clientHeight || 480;
      }
    };

    // Actualizar cuando el video carga los metadatos
    video.addEventListener("loadedmetadata", updateSize);
    video.addEventListener("resize", updateSize);

    // ResizeObserver para cambios de layout
    const observer = new ResizeObserver(updateSize);
    observer.observe(video);

    // Tamaño inicial
    updateSize();

    return () => {
      video.removeEventListener("loadedmetadata", updateSize);
      video.removeEventListener("resize", updateSize);
      observer.disconnect();
    };
  }, [videoRef]);

  // Dibujar cuando rawSignals cambia
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    if (!rawSignals || !rawSignals.faceDetection) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      return;
    }

    drawFrame(ctx, rawSignals, canvas.width, canvas.height, showFullMesh, showPose);
  }, [rawSignals, showFullMesh, showPose]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
      }}
      aria-hidden="true"
    />
  );
}
