/**
 * BiometricCapture — componente compartido de captura biométrica inmersiva (C-36).
 *
 * Encapsula: acceso a cámara (getUserMedia), loop RAF de detección real con el
 * motor MediaPipe (vía loadEnrollmentEngine/disposeEnrollmentEngine), evaluación
 * de retos (evaluateChallenge, framesMinForChallenge), selección aleatoria de retos
 * (pickActiveChallenges), UI inmersiva (overlay `fixed inset-0 z-50`) y fallback
 * manual cuando WebGL no está disponible.
 *
 * Decisiones (C-36):
 * D-1: overlay `fixed inset-0 z-50` como base cross-platform (desktop + iOS Safari).
 * D-2: requestFullscreen() best-effort sobre el elemento raíz — si rechaza o no
 *      está disponible, el overlay CSS ya cubre toda la pantalla.
 * D-3: óvalo dominante aspect-[3/4] max-h-[70vh], paso actual abajo con fuente
 *      grande, progreso de retos (dots + "N / total"), botón cancelar top-right.
 * D-4: parpadear incluido en ACTIVE_CHALLENGES — pickActiveChallenges lo elige.
 * D-5: el cálculo de embedding (embeddingFromLandmarks) queda en las pantallas
 *      caller; BiometricCapture solo pasa landmarks a onComplete.
 * D-6: fallback manual cuando loadEnrollmentEngine() rechaza.
 *
 * DATOS SENSIBLES (Ley 25.326):
 * Los landmarks del último frame son entregados al caller via onComplete. El caller
 * es responsable de calcular el embedding (dato sensible) y tratarlo según RN-BIO-07/08.
 * El cliente es SENSOR NO CONFIABLE (RN-GLB-01): el backend re-infiere y firma.
 * L2.5 intacto: el sistema nunca sanciona automáticamente.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Icon } from './components';
import { loadEnrollmentEngine, disposeEnrollmentEngine } from '../vision/enrollmentEngineLoader';
import { evaluateChallenge, framesMinForChallenge } from '../vision/enrollmentChallengeDetector';
import { pickActiveChallenges } from '../vision/liveness';
import { DESAFIOS } from '../lib/api';
import type { FaceLandmark, VisionEngine } from '../vision/VisionEngine';
import type { ActiveChallenge } from '../vision/liveness';

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------

// Task 1.2: Props del componente
export interface BiometricCaptureProps {
  /** Retos a usar. Si no se pasan, pickActiveChallenges(challengeCount ?? 2) los elige. */
  challenges?: ActiveChallenge[];
  /** Número de retos a elegir si no se pasan explícitamente (default: 2). */
  challengeCount?: number;
  /** Texto de contexto mostrado en el encabezado del overlay. */
  contextLabel?: string;
  /** Callback al completar todos los retos. Recibe los landmarks del último frame. */
  onComplete: (landmarks: FaceLandmark[]) => void;
  /** Callback al cancelar. */
  onCancel: () => void;
}

// Task 1.3: Fase interna del componente
type Fase = 'capturando' | 'error';

// ---------------------------------------------------------------------------
// Helpers — labels de retos desde DESAFIOS
// ---------------------------------------------------------------------------

function getLabelForChallenge(id: ActiveChallenge): string {
  return DESAFIOS.find((d) => d.id === id)?.label ?? id;
}

// ---------------------------------------------------------------------------
// Componente
// ---------------------------------------------------------------------------

export function BiometricCapture({
  challenges,
  challengeCount,
  contextLabel,
  onComplete,
  onCancel,
}: BiometricCaptureProps) {

  // Task 1.4: Refs
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
  const [motorError, setMotorError]   = useState<string | null>(null);
  const [fallbackManual, setFallbackManual] = useState(false);
  const [errorMsg, setErrorMsg]       = useState<string | null>(null);

  // Sync faseRef
  useEffect(() => { faseRef.current = fase; }, [fase]);
  // Sync resueltosRef
  useEffect(() => { resueltosRef.current = resueltos; }, [resueltos]);
  // Sync desafiosRef
  useEffect(() => { desafiosRef.current = desafios; }, [desafios]);

  // ---------------------------------------------------------------------------
  // Task 4.5: Inicialización de retos al montar
  // ---------------------------------------------------------------------------
  useEffect(() => {
    const ids = challenges && challenges.length > 0
      ? challenges
      : pickActiveChallenges(challengeCount ?? 2);
    setDesafios(ids);
    desafiosRef.current = ids;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ---------------------------------------------------------------------------
  // Task 4.3: activarFullscreen — best-effort, no lanza error
  // ---------------------------------------------------------------------------
  const activarFullscreen = useCallback(() => {
    const container = containerRef.current;
    if (!container || !container.requestFullscreen) return;
    container.requestFullscreen().catch(() => {
      // rechazado (iOS Safari, entornos sin API) → el overlay CSS es suficiente
    });
  }, []);

  // ---------------------------------------------------------------------------
  // Task 4.1: procesarCompletado — cancelar RAF, dispose, salir fullscreen, callback
  // ---------------------------------------------------------------------------
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
    // Llamar callback con los landmarks del último frame
    onComplete(lastLandmarksRef.current);
  }, [onComplete]);

  // Task 4.2: registrar procesarCompletado en ref para acceso desde el loop RAF
  useEffect(() => {
    procesarCompletadoRef.current = procesarCompletado;
  }, [procesarCompletado]);

  // ---------------------------------------------------------------------------
  // Task 4.4: handleCancel — cancelar RAF, dispose, salir fullscreen, detener stream
  // ---------------------------------------------------------------------------
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

  // ---------------------------------------------------------------------------
  // Task 3.3: resolverRetoFromLoop — updater funcional para evitar stale closure
  // ---------------------------------------------------------------------------
  const resolverRetoFromLoop = useCallback((id: ActiveChallenge) => {
    setResueltos((prev) => {
      if (prev.includes(id)) return prev;
      const next = [...prev, id];
      if (desafiosRef.current.length > 0 && next.length >= desafiosRef.current.length) {
        // Defer para no mutar estado dentro de otro setter
        setTimeout(() => {
          if (procesarCompletadoRef.current) {
            procesarCompletadoRef.current();
          }
        }, 0);
      }
      return next;
    });
  }, []);

  // ---------------------------------------------------------------------------
  // Task 3.1 + 3.2 + 3.4: startDetectionLoop — loop RAF de detección
  // ---------------------------------------------------------------------------
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

  // ---------------------------------------------------------------------------
  // Task 2.1 + 2.2 + 2.3 + 2.4: useEffect de inicialización de cámara y motor
  // ---------------------------------------------------------------------------
  useEffect(() => {
    let cancelado = false;

    // Task 2.1: inicializar cámara
    navigator.mediaDevices?.getUserMedia({
      video: { facingMode: 'user', width: 640, height: 480 },
    }).then((stream) => {
      if (cancelado) { stream.getTracks().forEach((t) => t.stop()); return; }
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play().catch(() => {});
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

    // Task 2.4: cleanup
    return () => {
      cancelado = true;
      // Cancelar RAF
      if (rafHandleRef.current !== null) {
        cancelAnimationFrame(rafHandleRef.current);
        rafHandleRef.current = null;
      }
      // Dispose del motor
      void disposeEnrollmentEngine();
      // Detener stream
      streamRef.current?.getTracks().forEach((t) => t.stop());
      // Quitar listener
      document.removeEventListener('fullscreenchange', onFullscreenChange);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ---------------------------------------------------------------------------
  // Task 5.1: resolverRetoManual — fallback manual, sin RAF
  // ---------------------------------------------------------------------------
  const resolverRetoManual = useCallback((id: string) => {
    setResueltos((prev) => {
      if (prev.includes(id)) return prev;
      const next = [...prev, id];
      // Task 5.3: al completar todos en fallback, llamar onComplete
      if (desafiosRef.current.length > 0 && next.length >= desafiosRef.current.length) {
        setTimeout(() => {
          if (procesarCompletadoRef.current) {
            procesarCompletadoRef.current();
          }
        }, 0);
      }
      return next;
    });
  }, []);

  // ---------------------------------------------------------------------------
  // Derivados para la UI
  // ---------------------------------------------------------------------------
  const retoActualId = desafios.find((id) => !resueltos.includes(id)) ?? null;
  const retoActualLabel = retoActualId ? getLabelForChallenge(retoActualId) : '¡Listo!';
  const totalResueltos = resueltos.length;
  const totalDesafios  = desafios.length;
  const todosResueltos = totalDesafios > 0 && totalResueltos >= totalDesafios;

  // ---------------------------------------------------------------------------
  // Render — Task 6.1 al 6.11
  // ---------------------------------------------------------------------------

  // Task 6.9: estado de error de cámara
  if (fase === 'error') {
    return createPortal(
      // Task 6.1: contenedor raíz del overlay (portal a body — escapa el stacking context del shell)
      <div ref={containerRef} className="fixed inset-0 z-50 bg-neutral-950 flex flex-col items-center justify-center">
        {/* Task 6.2: botón cancelar discreto */}
        <button
          onClick={handleCancel}
          className="absolute top-4 right-4 text-sm text-white/60 hover:text-white/90 transition-colors px-3 py-1"
        >
          Cancelar ×
        </button>
        <div className="text-center space-y-md px-lg">
          <Icon name="videocam_off" className="text-error text-[48px]" fill />
          <p className="font-headline text-title-lg text-white">Sin acceso a la cámara</p>
          <p className="text-body-sm text-white/70">{errorMsg}</p>
          <p className="text-label-sm text-white/60">
            Habilitá el permiso de cámara en tu navegador y volvé a intentarlo.
          </p>
        </div>
      </div>,
      document.body,
    );
  }

  return createPortal(
    // Task 6.1: contenedor raíz del overlay — fixed inset-0 z-50 (portal a body — escapa el stacking context del shell)
    <div
      ref={containerRef}
      className="fixed inset-0 z-50 bg-neutral-950 flex flex-col items-center justify-center"
    >
      {/* Task 6.2: botón cancelar discreto — absolute top-4 right-4 */}
      <button
        onClick={handleCancel}
        className="absolute top-4 right-4 text-sm text-white/60 hover:text-white/90 transition-colors px-3 py-1"
      >
        Cancelar ×
      </button>

      {/* Task 6.8: etiqueta contextual opcional */}
      {contextLabel && (
        <p className="text-label-sm text-white/60 mb-md text-center px-lg">{contextLabel}</p>
      )}

      {/* Task 6.3 + 6.4 + 6.5 + 6.6: óvalo con video */}
      <div className="relative flex items-center justify-center">
        {/* Óvalo: aspect-[3/4], max-w-xs, max-h-[70vh] */}
        <div
          className={`relative aspect-[3/4] w-full max-w-xs overflow-hidden rounded-full bg-neutral-800`}
          style={{ maxHeight: '70vh' }}
        >
          {/* Video de cámara */}
          <video
            ref={videoRef}
            muted
            playsInline
            className="absolute inset-0 w-full h-full object-cover"
            aria-label="Vista de cámara para captura biométrica"
          />

          {/* Task 6.5: spinner de carga del motor */}
          {!motorListo && !motorError && !fallbackManual && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/60">
              <Icon name="progress_activity" className="ae-spin text-white text-[32px]" />
              <span className="text-label-sm text-white/80 mt-sm">Preparando verificación…</span>
            </div>
          )}
        </div>

        {/* Task 6.4: anillo del óvalo con estado visual */}
        <div
          className={`absolute inset-0 rounded-full border-2 pointer-events-none ${
            todosResueltos
              ? 'border-green-400'
              : motorListo && !fallbackManual
                ? 'border-blue-400 scanning-ring'
                : 'border-dashed border-white/30'
          }`}
        />

        {/* Task 6.6: indicador "CÁMARA EN VIVO" */}
        <div className="absolute bottom-3 left-3 inline-flex items-center gap-base bg-error text-on-error text-label-sm font-bold px-sm py-base rounded-full z-10">
          <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
          CÁMARA EN VIVO
        </div>
      </div>

      {/* Task 6.10: banner de fallback manual */}
      {fallbackManual && (
        <div className="mt-md mx-lg w-full max-w-xs bg-amber-900/50 border border-amber-600/30 rounded-xl px-sm py-xs text-center">
          <p className="text-label-sm text-amber-200">
            Motor de visión no disponible — <strong>modo de prueba manual</strong>
          </p>
        </div>
      )}

      {/* Task 6.7: sección inferior — paso actual + dots de progreso */}
      <div className="mt-lg text-center space-y-sm px-lg w-full max-w-xs">
        {/* Texto del paso actual */}
        <p className={`font-headline text-2xl font-bold ${
          todosResueltos ? 'text-green-400' : 'text-white'
        }`}>
          {todosResueltos ? '¡Listo!' : retoActualLabel}
        </p>

        {/* Dots de progreso + contador */}
        {totalDesafios > 0 && (
          <div className="flex items-center justify-center gap-sm">
            {desafios.map((id) => (
              <span
                key={id}
                className={`text-lg ${resueltos.includes(id) ? 'text-green-400' : 'text-white/40'}`}
              >
                {resueltos.includes(id) ? '●' : '○'}
              </span>
            ))}
            <span className="text-label-sm text-white/60 ml-xs">
              {totalResueltos} / {totalDesafios}
            </span>
          </div>
        )}

        {/* Task 6.11: grilla de botones de retos en fallback manual */}
        {fallbackManual && totalDesafios > 0 && (
          <div className="grid grid-cols-1 gap-sm mt-sm">
            {desafios.map((id) => {
              const hecho = resueltos.includes(id);
              return (
                // Task 5.2: botones habilitados y clicables en fallback
                <button
                  key={id}
                  disabled={hecho}
                  onClick={() => resolverRetoManual(id)}
                  className={`flex items-center gap-sm p-sm rounded-xl border transition-all ${
                    hecho
                      ? 'bg-green-900/50 border-green-600/30 text-green-400 cursor-default'
                      : 'bg-white/10 border-white/20 text-white hover:bg-white/20 cursor-pointer'
                  }`}
                >
                  <Icon name={hecho ? 'check_circle' : 'gesture'} fill={hecho} />
                  <span className="text-label-md font-semibold">{getLabelForChallenge(id)}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}
