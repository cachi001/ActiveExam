/**
 * frameProcessor — cuerpo del bucle de frames del harness (C-23).
 *
 * Extraído VERBATIM desde el setInterval de startHarness en useDetectionHarness.
 * NO cambia la lógica de detección: captura el frame, corre los detectores del
 * motor (faces/mesh/pose), estima head_yaw_deg desde la pose, consume las señales
 * de contexto de los refs y ejecuta el pipeline con onSignals.
 *
 * Recibe todas las refs y setters por una sola estructura de dependencias para
 * que el flujo sea idéntico al inline original (mismas closures, mismos refs).
 */

import type { RefObject, MutableRefObject } from 'react';
import type { VisionEngine, FaceDetectionSignal, FaceMeshSignal, PoseSignal } from '../../vision/VisionEngine';
import type { VisionPipeline } from '../../proctoring/visionPipeline';
import type { EngineMode, RawSignals } from './types';

interface FrameTickDeps {
  videoRef: RefObject<HTMLVideoElement>;
  engineRef: MutableRefObject<VisionEngine | null>;
  pipelineRef: MutableRefObject<VisionPipeline | null>;
  faceCountRef: MutableRefObject<number>;
  envFocusLostRef: MutableRefObject<boolean>;
  envTabChangedRef: MutableRefObject<boolean>;
  envFullscreenExitedRef: MutableRefObject<boolean>;
  envClipboardRef: MutableRefObject<'copy' | 'paste' | null>;
  envExtraMonitorRef: MutableRefObject<boolean | null>;
  setRawSignals: (s: RawSignals) => void;
  setEngineMode: (m: EngineMode) => void;
  setEngineError: (e: string | null) => void;
}

/**
 * Devuelve el callback que se pasa a setInterval(..., FRAME_INTERVAL_MS).
 * El cuerpo es idéntico al original — solo se aislaron las dependencias.
 */
export function createFrameTick(deps: FrameTickDeps): () => Promise<void> {
  const {
    videoRef,
    engineRef,
    pipelineRef,
    faceCountRef,
    envFocusLostRef,
    envTabChangedRef,
    envFullscreenExitedRef,
    envClipboardRef,
    envExtraMonitorRef,
    setRawSignals,
    setEngineMode,
    setEngineError,
  } = deps;

  return async () => {
    const video = videoRef.current;
    const engine_ = engineRef.current;
    const pipeline_ = pipelineRef.current;
    if (!video || !engine_ || !pipeline_ || video.readyState < 2) return;

    try {
      // Capturar frame como ImageBitmap (task 2.2)
      const frame = await createImageBitmap(video);

      // C-30: Extraer señales crudas del motor actual (real o stub)
      // Si el motor real falla durante la detección, el error se propaga al estado load-error.
      // No hay swallowing silencioso — D-6 / fallback honesto.
      let fd: FaceDetectionSignal;
      let mesh: FaceMeshSignal | null = null;
      let poseAvailable = false;
      let poseSignal: PoseSignal | null = null;

      try {
        fd = await engine_.detectFaces(frame);
      } catch (err) {
        // Si el motor real lanzó durante inferencia (no durante init), reportar
        const msg = err instanceof Error ? err.message : String(err);
        setEngineMode('load-error');
        setEngineError(`Error en detectFaces: ${msg}`);
        // Señal vacía para que el pipeline no crashee
        fd = { face_count: 0, faces: [] };
      }

      if (fd.face_count >= 1) {
        try {
          mesh = await engine_.detectFaceMesh(frame);
        } catch (err) {
          // Error en face mesh no interrumpe el frame
          console.warn('[AdminDetectionHarness] detectFaceMesh error:', err);
          mesh = null;
        }
      }

      try {
        poseSignal = await engine_.detectPose(frame);
        poseAvailable = poseSignal.keypoints.length > 0;
      } catch {
        poseAvailable = false;
        poseSignal = null;
      }

      frame.close();

      // Actualizar panel de señales crudas (task 4.2) + C-30: incluir poseSignal para overlay
      faceCountRef.current = fd.face_count;
      setRawSignals({ faceDetection: fd, faceMesh: mesh, poseAvailable, poseSignal, frameTs: Date.now() });

      // C-35 Task 5.1: Estimar head_yaw_deg aproximado a partir de PoseSignal.
      // Usamos los landmarks de hombros (indices 11 = izquierdo, 12 = derecho en
      // BlazePose/MediaPipe PoseLandmarker) y la diferencia de altura Y para aproximar
      // el yaw de cabeza: cuando la persona rota, un hombro sube y el otro baja.
      //
      // Formula: yaw_rad ≈ asin(clamp(deltaY / shoulderDist, -1, 1))
      //   donde deltaY = y_shoulder_right - y_shoulder_left (coordenadas normalizadas 0..1)
      //   y shoulderDist es la distancia euclidiana entre ambos hombros.
      //
      // Esta es una aproximacion — no es yaw preciso de cabeza (para eso se necesitarian
      // los facialTransformationMatrixes de FaceLandmarker), pero es suficiente como senal
      // complementaria para el harness. Si PoseSignal no esta disponible o los landmarks
      // de hombros no estan detectados, head_yaw_deg = undefined (sin efecto en evalGaze).
      let head_yaw_deg: number | undefined;
      if (poseSignal && poseSignal.keypoints.length > 12) {
        const shoulderLeft = poseSignal.keypoints[11];
        const shoulderRight = poseSignal.keypoints[12];
        // Usar los hombros solo si ambos tienen visibilidad razonable (> 0.3)
        if (
          shoulderLeft && shoulderRight &&
          (shoulderLeft.visibility ?? 0) > 0.3 &&
          (shoulderRight.visibility ?? 0) > 0.3
        ) {
          const dx = shoulderRight.x - shoulderLeft.x;
          const dy = shoulderRight.y - shoulderLeft.y;
          const shoulderDist = Math.hypot(dx, dy);
          if (shoulderDist > 0.01) {
            // Un hombro mas alto que el otro indica rotacion. Escalamos a grados:
            // |deltaY / dist| = sin(yaw_approx). Positivo = rotacion a la derecha.
            const sinYaw = Math.max(-1, Math.min(1, dy / shoulderDist));
            head_yaw_deg = (Math.asin(sinYaw) * 180) / Math.PI;
          }
        }
      }

      // C-25: consumir señales de contexto reales de los refs (no valores fijos)
      const snapFocus = envFocusLostRef.current;
      const snapTab = envTabChangedRef.current;
      const snapFullscreen = envFullscreenExitedRef.current;
      const snapClipboard = envClipboardRef.current;
      // Nota: focus_lost y tab_changed se resetean tras consumo para evitar re-emisión
      // hasta que el detector emita de nuevo; fullscreen se resetea desde las reglas.
      envFocusLostRef.current = false;
      envTabChangedRef.current = false;
      envFullscreenExitedRef.current = false;
      envClipboardRef.current = null;

      // Ejecutar pipeline (onFrame llama detectFaces/detectFaceMesh internamente).
      // Como ya los llamamos arriba para el panel de señales, usamos onSignals para evitar
      // doble inferencia: pasamos las señales ya extraídas. (task 3.3 / D-3)
      // C-35 Task 5.2: agregar head_yaw_deg al objeto de señales (campo opcional).
      await pipeline_.onSignals({
        ts_ms: Date.now(),
        face_count: fd.face_count,
        gaze: mesh?.gaze,
        focus_lost: snapFocus,
        extra_monitor: envExtraMonitorRef.current === true,
        tab_changed: snapTab,
        fullscreen_exited: snapFullscreen,
        clipboard_action: snapClipboard ?? undefined,
        head_yaw_deg,
      });
    } catch (err) {
      // Error en el frame no debe crashear el loop
      console.warn('[AdminDetectionHarness] frame error:', err);
    }
  };
}
