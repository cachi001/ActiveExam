import { useEffect } from 'react';
import type { VisionEngine } from '../../vision/VisionEngine';
import type { Fase } from './detectionLoop';
import type { OvalTono } from './CaptureOval';
import { loadEnrollmentEngine, disposeEnrollmentEngine } from '../../vision/enrollmentEngineLoader';
import { playError } from './sounds';
import { withTimeout } from '../../lib/withTimeout';

interface CameraInitDeps {
  streamRef: React.RefObject<MediaStream | null>;
  videoRef: React.RefObject<HTMLVideoElement | null>;
  rafHandleRef: React.MutableRefObject<number | null>;
  cooldownTimerRef: React.MutableRefObject<ReturnType<typeof setTimeout> | null>;
  engineRef: React.MutableRefObject<VisionEngine | null>;
  setCamaraLista: (v: boolean) => void;
  setErrorMsg: (msg: string | null) => void;
  setFase: (f: Fase | ((prev: Fase) => Fase)) => void;
  setMotorListo: (v: boolean) => void;
  setMotorError: (msg: string | null) => void;
  setFallbackManual: (v: boolean) => void;
  setTonoOvalo: (t: OvalTono) => void;
  activarFullscreen: () => void;
  startDetectionLoop: (engine: VisionEngine) => void;
}

export function useCameraInit(deps: CameraInitDeps) {
  const {
    streamRef, videoRef, rafHandleRef, cooldownTimerRef, engineRef,
    setCamaraLista, setErrorMsg, setFase, setMotorListo, setMotorError,
    setFallbackManual, setTonoOvalo, activarFullscreen, startDetectionLoop,
  } = deps;

  useEffect(() => {
    let cancelado = false;

    navigator.mediaDevices?.getUserMedia({
      video: { facingMode: 'user', width: 640, height: 480 },
    }).then((stream) => {
      if (cancelado) { stream.getTracks().forEach((t) => t.stop()); return; }
      streamRef.current = stream;

      try {
        const videoTrack = stream.getVideoTracks()[0];
        if (videoTrack) {
          type ExtendedCapabilities = MediaTrackCapabilities & {
            exposureMode?: string[];
            brightness?: { min: number; max: number; step?: number };
          };
          type ExtendedConstraints = MediaTrackConstraintSet & {
            exposureMode?: ConstrainDOMString;
            brightness?: ConstrainDouble;
          };
          const caps = videoTrack.getCapabilities() as ExtendedCapabilities;
          const advanced: ExtendedConstraints[] = [];
          if (caps.exposureMode && caps.exposureMode.includes('continuous')) {
            advanced.push({ exposureMode: 'continuous' });
          }
          if (caps.brightness) {
            const targetBrightness = caps.brightness.min + (caps.brightness.max - caps.brightness.min) * 0.7;
            advanced.push({ brightness: targetBrightness });
          }
          if (advanced.length > 0) {
            void videoTrack.applyConstraints({ advanced } as MediaTrackConstraints).catch(() => {});
          }
        }
      } catch { /* silently ignore */ }

      if (videoRef.current) {
        const video = videoRef.current;
        video.srcObject = stream;
        const marcarLista = () => {
          if (!cancelado && video.videoWidth > 0 && video.videoHeight > 0) {
            setCamaraLista(true);
          }
        };
        video.addEventListener('loadeddata', marcarLista);
        video.addEventListener('playing', marcarLista);
        video.play().then(marcarLista).catch(() => {});
      }
    }).catch((err) => {
      if (!cancelado) {
        setErrorMsg(`Sin acceso a la cámara: ${err?.message ?? 'permiso denegado'}`);
        setFase('error' as Fase);
        playError();
      }
    });

    const onFullscreenChange = () => {};
    document.addEventListener('fullscreenchange', onFullscreenChange);

    const ENGINE_LOAD_TIMEOUT_MS = 30000;
    withTimeout(
      loadEnrollmentEngine(),
      ENGINE_LOAD_TIMEOUT_MS,
      'La cámara inteligente tardó demasiado en cargar (conexión lenta). Podés continuar de forma manual.',
    ).then((engine) => {
      if (cancelado) { void disposeEnrollmentEngine(); return; }
      engineRef.current = engine;
      setMotorListo(true);
      setTonoOvalo('ok');
      activarFullscreen();
      startDetectionLoop(engine);
    }).catch((err) => {
      if (!cancelado) {
        const msg = err instanceof Error ? err.message : String(err);
        setMotorError(msg);
        setFallbackManual(true);
      }
    });

    return () => {
      cancelado = true;
      if (rafHandleRef.current !== null) {
        cancelAnimationFrame(rafHandleRef.current);
        rafHandleRef.current = null;
      }
      if (cooldownTimerRef.current !== null) {
        clearTimeout(cooldownTimerRef.current);
        cooldownTimerRef.current = null;
      }
      void disposeEnrollmentEngine();
      streamRef.current?.getTracks().forEach((t) => t.stop());
      document.removeEventListener('fullscreenchange', onFullscreenChange);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
}
