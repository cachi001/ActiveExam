/**
 * BiometricCapture — componente compartido de captura biométrica inmersiva (C-36).
 *
 * Encapsula la LÓGICA: acceso a cámara (getUserMedia), loop RAF de detección real
 * con el motor MediaPipe (loadEnrollmentEngine/disposeEnrollmentEngine), evaluación
 * de retos (evaluateChallenge, framesMinForChallenge), selección aleatoria
 * (pickActiveChallenges) y fallback manual cuando WebGL no está disponible. La parte
 * PRESENTACIONAL vive en ./biometric/ (CaptureOverlay + sub-componentes).
 *
 * Decisiones (C-36): D-1 overlay `fixed inset-0 z-50` cross-platform; D-2
 * requestFullscreen() best-effort (el overlay CSS cubre todo si rechaza); D-3 óvalo
 * dominante aspect-[3/4], paso actual abajo, dots + "N / total", cancelar top-right;
 * D-4 parpadear incluido en ACTIVE_CHALLENGES; D-5 el embedding lo computa el caller
 * (este solo pasa landmarks a onComplete); D-6 fallback manual si loadEnrollmentEngine rechaza.
 *
 * DATOS SENSIBLES (Ley 25.326): los landmarks del último frame se entregan al caller
 * via onComplete; el caller computa el embedding (dato sensible) según RN-BIO-07/08.
 * El cliente es SENSOR NO CONFIABLE (RN-GLB-01): el backend re-infiere y firma.
 * L2.5 intacto: el sistema nunca sanciona automáticamente.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { CaptureOverlay } from './biometric/CaptureOverlay';
import { CaptureError } from './biometric/CaptureError';
import { loadEnrollmentEngine, disposeEnrollmentEngine } from '../vision/enrollmentEngineLoader';
import { evaluateChallenge, framesMinForChallenge } from '../vision/enrollmentChallengeDetector';
import { pickActiveChallenges } from '../vision/liveness';
import { DESAFIOS } from '../lib/api';
import type { FaceLandmark, VisionEngine } from '../vision/VisionEngine';
import type { ActiveChallenge } from '../vision/liveness';

// Props del componente
export interface BiometricCaptureProps {
  /** Retos a usar. Si no se pasan, pickActiveChallenges(challengeCount ?? 2) los elige. */
  challenges?: ActiveChallenge[];
  /** Número de retos a elegir si no se pasan explícitamente (default: 2). */
  challengeCount?: number;
  /** Texto de contexto mostrado en el encabezado del overlay. */
  contextLabel?: string;
  /**
   * Callback al completar todos los retos. Recibe los landmarks del último frame
   * y un canvas con ese frame (para que el caller compute el descriptor 128-d con
   * face-api). `frame` es null si la cámara no estaba lista al completar.
   */
  onComplete: (landmarks: FaceLandmark[], frame: HTMLCanvasElement | null) => void;
  /** Callback al cancelar. */
  onCancel: () => void;
}

// Task 1.3: Fase interna del componente
// 'exito' = todos los retos resueltos → se muestra el estado de verificación
// completada ~1.6s ANTES de invocar onComplete (mejor feedback de cierre).
type Fase = 'capturando' | 'exito' | 'error';

// Helper — label de un reto desde DESAFIOS
function getLabelForChallenge(id: ActiveChallenge): string {
  return DESAFIOS.find((d) => d.id === id)?.label ?? id;
}

export function BiometricCapture({
  challenges,
  challengeCount,
  contextLabel,
  onComplete,
  onCancel,
}: BiometricCaptureProps) {
  // Refs
  const videoRef             = useRef<HTMLVideoElement>(null);
  const containerRef         = useRef<HTMLDivElement>(null);
  const streamRef            = useRef<MediaStream | null>(null);
  const rafHandleRef         = useRef<number | null>(null);
  const engineRef            = useRef<VisionEngine | null>(null);
  const lastLandmarksRef     = useRef<FaceLandmark[]>([]);
  const challengeCountsRef   = useRef<Map<ActiveChallenge, number>>(new Map());
  const faseRef              = useRef<Fase>('capturando');
  const desafiosRef          = useRef<ActiveChallenge[]>([]);
  const resueltosRef         = useRef<string[]>([]);
  const procesarCompletadoRef = useRef<(() => void) | null>(null);

  // Estado de UI
  const [fase, setFase]               = useState<Fase>('capturando');
  const [desafios, setDesafios]       = useState<ActiveChallenge[]>([]);
  const [resueltos, setResueltos]     = useState<string[]>([]);
  const [motorListo, setMotorListo]   = useState(false);
  // true cuando el <video> ya tiene stream con dimensiones reales (frame visible).
  // El óvalo + cámara solo se revelan cuando motorListo && camaraLista.
  const [camaraLista, setCamaraLista] = useState(false);
  const [motorError, setMotorError]   = useState<string | null>(null);
  const [fallbackManual, setFallbackManual] = useState(false);
  const [errorMsg, setErrorMsg]       = useState<string | null>(null);

  // Sync de refs para acceso desde el loop RAF (sin stale closure)
  useEffect(() => { faseRef.current = fase; }, [fase]);
  useEffect(() => { resueltosRef.current = resueltos; }, [resueltos]);
  useEffect(() => { desafiosRef.current = desafios; }, [desafios]);

  // Inicialización de retos al montar
  useEffect(() => {
    const ids = challenges && challenges.length > 0
      ? challenges
      : pickActiveChallenges(challengeCount ?? 2);
    setDesafios(ids);
    desafiosRef.current = ids;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // activarFullscreen — best-effort, no lanza error
  const activarFullscreen = useCallback(() => {
    const container = containerRef.current;
    if (!container || !container.requestFullscreen) return;
    container.requestFullscreen().catch(() => {
      // rechazado (iOS Safari, entornos sin API) → el overlay CSS es suficiente
    });
  }, []);

  // procesarCompletado — cancelar RAF, dispose, salir fullscreen, callback
  const procesarCompletado = useCallback(() => {
    // Cancelar RAF
    if (rafHandleRef.current !== null) {
      cancelAnimationFrame(rafHandleRef.current);
      rafHandleRef.current = null;
    }
    // Dispose del motor
    void disposeEnrollmentEngine();
    // Salir de fullscreen si está activo
    if (document.fullscreenElement) {
      document.exitFullscreen?.().catch(() => {});
    }
    // Capturar el frame actual del video en un canvas para que el caller compute
    // el descriptor facial 128-d (face-api). Se dibuja SIN espejar (el espejado es
    // solo visual via CSS scaleX(-1)); el descriptor es invariante a reflejo, pero
    // mantenemos el frame "crudo" para fidelidad.
    let frame: HTMLCanvasElement | null = null;
    const video = videoRef.current;
    if (video && video.videoWidth > 0 && video.videoHeight > 0) {
      try {
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        if (ctx) {
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
          frame = canvas;
        }
      } catch {
        // Si el dibujo falla (tainted canvas / video no listo) → frame queda null.
        frame = null;
      }
    }
    // Llamar callback con los landmarks del último frame + el frame capturado
    onComplete(lastLandmarksRef.current, frame);
  }, [onComplete]);

  // Registrar procesarCompletado en ref para acceso desde el loop RAF
  useEffect(() => {
    procesarCompletadoRef.current = procesarCompletado;
  }, [procesarCompletado]);

  // Bug 3: al entrar en fase 'exito', mostrar "Verificación completada" un instante
  // (~1.6s) para que el usuario lo lea, y RECIÉN ahí invocar onComplete/cerrar.
  // El frame se captura dentro de procesarCompletado (el RAF ya se detiene solo).
  useEffect(() => {
    if (fase !== 'exito') return;
    const t = setTimeout(() => {
      procesarCompletadoRef.current?.();
    }, 1600);
    return () => clearTimeout(t);
  }, [fase]);

  // handleCancel — cancelar RAF, dispose, salir fullscreen, detener stream
  const handleCancel = useCallback(() => {
    if (rafHandleRef.current !== null) {
      cancelAnimationFrame(rafHandleRef.current);
      rafHandleRef.current = null;
    }
    void disposeEnrollmentEngine();
    if (document.fullscreenElement) {
      document.exitFullscreen?.().catch(() => {});
    }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    onCancel();
  }, [onCancel]);

  // resolverRetoFromLoop — updater funcional para evitar stale closure
  const resolverRetoFromLoop = useCallback((id: ActiveChallenge) => {
    setResueltos((prev) => {
      if (prev.includes(id)) return prev;
      const next = [...prev, id];
      if (desafiosRef.current.length > 0 && next.length >= desafiosRef.current.length) {
        // Bug 3: en vez de cerrar al instante, entrar en fase 'exito' (un effect
        // dedicado muestra "Verificación completada" ~1.6s y recién ahí completa).
        setFase('exito');
      }
      return next;
    });
  }, []);

  // startDetectionLoop — loop RAF de detección
  const startDetectionLoop = useCallback((engine: VisionEngine) => {
    engineRef.current = engine;

    const detectFrame = async () => {
      // Task 3.4: detener si la fase cambió
      if (faseRef.current !== 'capturando') {
        rafHandleRef.current = null;
        return;
      }

      if (videoRef.current && videoRef.current.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
        try {
          const bitmap = await createImageBitmap(videoRef.current);

          // Task 3.1: detección paralela face mesh + faces
          const [meshResult, faceResult] = await Promise.all([
            engine.detectFaceMesh(bitmap),
            engine.detectFaces(bitmap),
          ]);

          bitmap.close();

          const { landmarks, gaze } = meshResult;
          const face_count = faceResult.face_count;
          const bbox = faceResult.faces[0] ?? null;

          // Actualizar landmarks del último frame
          if (face_count > 0 && landmarks.length > 0) {
            lastLandmarksRef.current = landmarks;
          }

          const currentResueltos = resueltosRef.current;
          const currentDesafios  = desafiosRef.current;

          if (face_count === 0) {
            // Task 3.2: sin rostro → resetear todos los acumuladores
            challengeCountsRef.current.clear();
          } else {
            // Task 3.2: evaluar retos pendientes
            for (const id of currentDesafios) {
              if (currentResueltos.includes(id)) continue;

              const cumple = evaluateChallenge(id, landmarks, gaze, bbox);
              const prevCount = challengeCountsRef.current.get(id) ?? 0;

              if (cumple) {
                const newCount = prevCount + 1;
                challengeCountsRef.current.set(id, newCount);

                if (newCount >= framesMinForChallenge(id)) {
                  challengeCountsRef.current.set(id, 0);
                  resolverRetoFromLoop(id);
                }
              } else {
                challengeCountsRef.current.set(id, 0);
              }
            }
          }
        } catch {
          // Errores de detección son transitorios — continuar el loop
        }
      }

      // Continuar el loop
      if (faseRef.current === 'capturando') {
        rafHandleRef.current = requestAnimationFrame(() => { void detectFrame(); });
      } else {
        rafHandleRef.current = null;
      }
    };

    rafHandleRef.current = requestAnimationFrame(() => { void detectFrame(); });
  }, [resolverRetoFromLoop]); // eslint-disable-line react-hooks/exhaustive-deps

  // useEffect de inicialización de cámara y motor
  useEffect(() => {
    let cancelado = false;

    // Task 2.1: inicializar cámara
    navigator.mediaDevices?.getUserMedia({
      video: { facingMode: 'user', width: 640, height: 480 },
    }).then((stream) => {
      if (cancelado) { stream.getTracks().forEach((t) => t.stop()); return; }
      streamRef.current = stream;
      if (videoRef.current) {
        const video = videoRef.current;
        video.srcObject = stream;
        // Marcar la cámara como lista cuando haya datos reales del frame, para
        // revelar el óvalo recién entonces (Bug 1: nada de óvalo durante la carga).
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
        setFase('error');
      }
    });

    // Task 2.3: listener fullscreenchange
    const onFullscreenChange = () => {
      // Sincronizar al salir de fullscreen (sin acción necesaria — el overlay CSS persiste)
    };
    document.addEventListener('fullscreenchange', onFullscreenChange);

    // Task 2.2: cargar motor
    loadEnrollmentEngine().then((engine) => {
      if (cancelado) {
        void disposeEnrollmentEngine();
        return;
      }
      engineRef.current = engine;
      setMotorListo(true);
      // Task 4.6: activar fullscreen y empezar el loop
      activarFullscreen();
      startDetectionLoop(engine);
    }).catch((err) => {
      if (!cancelado) {
        const msg = err instanceof Error ? err.message : String(err);
        setMotorError(msg);
        setFallbackManual(true);
      }
    });

    // cleanup: cancelar RAF, dispose del motor, detener stream y quitar listener
    return () => {
      cancelado = true;
      if (rafHandleRef.current !== null) {
        cancelAnimationFrame(rafHandleRef.current);
        rafHandleRef.current = null;
      }
      void disposeEnrollmentEngine();
      streamRef.current?.getTracks().forEach((t) => t.stop());
      document.removeEventListener('fullscreenchange', onFullscreenChange);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // resolverRetoManual — fallback manual, sin RAF
  const resolverRetoManual = useCallback((id: string) => {
    setResueltos((prev) => {
      if (prev.includes(id)) return prev;
      const next = [...prev, id];
      // Task 5.3: al completar todos en fallback, mostrar el estado de éxito y
      // recién después completar (mismo flujo que el modo automático — Bug 3).
      if (desafiosRef.current.length > 0 && next.length >= desafiosRef.current.length) {
        setFase('exito');
      }
      return next;
    });
  }, []);

  // Derivados para la UI
  const retoActualId = desafios.find((id) => !resueltos.includes(id)) ?? null;
  const retoActualLabel = retoActualId ? getLabelForChallenge(retoActualId) : '¡Listo!';
  const totalResueltos = resueltos.length;
  const totalDesafios  = desafios.length;
  const todosResueltos = totalDesafios > 0 && totalResueltos >= totalDesafios;
  const enExito        = fase === 'exito' || todosResueltos;
  // El óvalo + cámara solo se revelan cuando el motor y la cámara están listos
  // (o en fallback manual). Mientras tanto se muestra un spinner limpio (Bug 1).
  const listoParaMostrar = (motorListo && camaraLista) || fallbackManual;

  // Render — estado de error de cámara
  if (fase === 'error') {
    return createPortal(
      // contenedor raíz del overlay (portal a body — escapa el stacking context del shell)
      <div ref={containerRef} className="fixed inset-0 z-[60] bg-white flex flex-col items-center justify-center px-6">
        <CaptureError errorMsg={errorMsg} onCancel={handleCancel} />
      </div>,
      document.body,
    );
  }

  return createPortal(
    <CaptureOverlay
      ref={containerRef}
      videoRef={videoRef}
      contextLabel={contextLabel}
      listoParaMostrar={listoParaMostrar}
      motorError={motorError}
      enExito={enExito}
      motorListo={motorListo}
      fallbackManual={fallbackManual}
      retoActualLabel={retoActualLabel}
      desafios={desafios}
      resueltos={resueltos}
      totalResueltos={totalResueltos}
      totalDesafios={totalDesafios}
      getLabel={getLabelForChallenge}
      onResolverManual={resolverRetoManual}
      onCancel={handleCancel}
    />,
    document.body,
  );
}
