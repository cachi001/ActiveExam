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
  // true cuando el <video> ya tiene stream con dimensiones reales (frame visible).
  // El óvalo + cámara solo se revelan cuando motorListo && camaraLista.
  const [camaraLista, setCamaraLista] = useState(false);
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

  // Task 4.2: registrar procesarCompletado en ref para acceso desde el loop RAF
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
        // Bug 3: en vez de cerrar al instante, entrar en fase 'exito' (un effect
        // dedicado muestra "Verificación completada" ~1.6s y recién ahí completa).
        setFase('exito');
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
      // Task 5.3: al completar todos en fallback, mostrar el estado de éxito y
      // recién después completar (mismo flujo que el modo automático — Bug 3).
      if (desafiosRef.current.length > 0 && next.length >= desafiosRef.current.length) {
        setFase('exito');
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
  const enExito        = fase === 'exito' || todosResueltos;
  // El óvalo + cámara solo se revelan cuando el motor y la cámara están listos
  // (o en fallback manual). Mientras tanto se muestra un spinner limpio (Bug 1).
  const listoParaMostrar = (motorListo && camaraLista) || fallbackManual;

  // ---------------------------------------------------------------------------
  // Render — Task 6.1 al 6.11
  // ---------------------------------------------------------------------------

  // Task 6.9: estado de error de cámara
  if (fase === 'error') {
    return createPortal(
      // Task 6.1: contenedor raíz del overlay (portal a body — escapa el stacking context del shell)
      <div ref={containerRef} className="fixed inset-0 z-[60] bg-white flex flex-col items-center justify-center px-6">
        {/* Cancelar discreto */}
        <button
          onClick={handleCancel}
          className="absolute top-4 right-4 inline-flex items-center gap-1 text-sm text-neutral-500 hover:text-neutral-900 transition-colors px-3 py-1.5 rounded-full"
        >
          Cancelar <Icon name="close" className="text-[18px]" />
        </button>
        <div className="text-center space-y-md px-lg max-w-xs">
          <Icon name="videocam_off" className="text-error text-[48px]" fill />
          <p className="font-headline text-title-lg text-neutral-900">Sin acceso a la cámara</p>
          <p className="text-body-sm text-neutral-600">{errorMsg}</p>
          <p className="text-label-sm text-neutral-500">
            Habilitá el permiso de cámara en tu navegador y volvé a intentarlo.
          </p>
        </div>
      </div>,
      document.body,
    );
  }

  return createPortal(
    // Overlay full-screen, fondo claro estilo app de banco (portal a body — escapa el stacking context del shell)
    <div
      ref={containerRef}
      className="fixed inset-0 z-[60] bg-white flex flex-col items-center justify-center px-6"
    >
      {/* Cancelar — discreto, arriba a la derecha */}
      <button
        onClick={handleCancel}
        className="absolute top-4 right-4 inline-flex items-center gap-1 text-sm text-neutral-500 hover:text-neutral-900 transition-colors px-3 py-1.5 rounded-full"
      >
        Cancelar <Icon name="close" className="text-[18px]" />
      </button>

      {/* Etiqueta contextual opcional — oculta durante la carga para no competir con el spinner */}
      {contextLabel && listoParaMostrar && (
        <p className="text-sm text-neutral-500 mb-6 text-center max-w-xs">{contextLabel}</p>
      )}

      {/* Bug 1: estado de carga LIMPIO — solo un spinner centrado, sin óvalo,
          sin frame de cámara, sin jerga técnica. El <video> sigue montado abajo
          (opacity-0) para que el stream se inicialice, pero no se ve. */}
      {!listoParaMostrar && !motorError && (
        <div className="flex flex-col items-center justify-center gap-3">
          <Icon name="progress_activity" className="ae-spin text-primary text-[40px]" />
          <span className="text-sm text-neutral-500">Preparando cámara…</span>
        </div>
      )}

      {/* Óvalo con la cámara — ancho EXPLÍCITO para que no colapse.
          Fade-in: invisible y sin ocupar layout mientras la cámara/motor cargan;
          se revela (opacity + scale) cuando listoParaMostrar (Bug 1). */}
      <div
        className={`relative transition-all duration-500 ease-out ${
          listoParaMostrar ? 'opacity-100 scale-100' : 'opacity-0 scale-95 absolute pointer-events-none'
        }`}
        style={{ width: 'min(80vw, 300px)', filter: 'drop-shadow(0 10px 24px rgba(0,0,0,0.15))' }}
        aria-hidden={!listoParaMostrar}
      >
        {/* clip-path ellipse recorta el video a la forma del óvalo (esquinas transparentes → fondo blanco) */}
        <div
          className="relative w-full aspect-[3/4] overflow-hidden bg-neutral-100"
          style={{ clipPath: 'ellipse(50% 50% at 50% 50%)' }}
        >
          {/* Video de cámara */}
          <video
            ref={videoRef}
            autoPlay
            muted
            playsInline
            className="absolute inset-0 w-full h-full object-cover"
            style={{ transform: 'scaleX(-1)' }}
            aria-label="Vista de cámara para captura biométrica"
          />

          {/* Bug 3: capa de éxito sobre el óvalo — check grande sobre velo verde */}
          {enExito && (
            <div className="absolute inset-0 flex items-center justify-center bg-green-500/15 animate-in fade-in duration-300">
              <Icon name="check_circle" className="text-green-500 text-[72px]" fill />
            </div>
          )}
        </div>

        {/* Anillo de estado del óvalo */}
        <div
          className={`absolute inset-0 rounded-[50%] border-4 pointer-events-none ${
            enExito
              ? 'border-green-500'
              : motorListo && !fallbackManual
                ? 'border-blue-500 scanning-ring'
                : 'border-dashed border-neutral-300'
          }`}
        />
      </div>

      {/* Banner de fallback manual */}
      {fallbackManual && !enExito && (
        <div className="mt-4 w-full max-w-xs bg-amber-50 border border-amber-300 rounded-xl px-3 py-2 text-center">
          <p className="text-sm text-amber-800">
            Motor de visión no disponible — <strong>modo de prueba manual</strong>
          </p>
        </div>
      )}

      {/* Sección inferior — paso actual + progreso. Oculta durante la carga. */}
      {listoParaMostrar && (
      <div className="mt-8 text-center space-y-3 w-full max-w-xs">
        {/* Texto del paso actual: éxito → reto actual. */}
        <p className={`font-headline text-2xl font-bold ${
          enExito ? 'text-green-600' : 'text-neutral-900'
        }`}>
          {enExito ? 'Verificación completada' : retoActualLabel}
        </p>

        {/* Subtítulo de encuadre mientras el motor está listo pero aún sin completar */}
        {!enExito && !fallbackManual && (
          <p className="text-sm text-neutral-500">Buscá tu rostro en el óvalo y seguí las indicaciones.</p>
        )}

        {/* Dots de progreso + contador */}
        {!enExito && totalDesafios > 0 && (
          <div className="flex items-center justify-center gap-2">
            {desafios.map((id) => (
              <span
                key={id}
                className={`text-lg ${resueltos.includes(id) ? 'text-green-600' : 'text-neutral-300'}`}
              >
                {resueltos.includes(id) ? '●' : '○'}
              </span>
            ))}
            <span className="text-sm text-neutral-500 ml-1">
              {totalResueltos} / {totalDesafios}
            </span>
          </div>
        )}

        {/* Grilla de botones de retos en fallback manual */}
        {!enExito && fallbackManual && totalDesafios > 0 && (
          <div className="grid grid-cols-1 gap-2 mt-2">
            {desafios.map((id) => {
              const hecho = resueltos.includes(id);
              return (
                <button
                  key={id}
                  disabled={hecho}
                  onClick={() => resolverRetoManual(id)}
                  className={`flex items-center gap-2 p-2 rounded-xl border transition-all ${
                    hecho
                      ? 'bg-green-50 border-green-300 text-green-700 cursor-default'
                      : 'bg-neutral-50 border-neutral-300 text-neutral-800 hover:bg-neutral-100 cursor-pointer'
                  }`}
                >
                  <Icon name={hecho ? 'check_circle' : 'gesture'} fill={hecho} />
                  <span className="text-sm font-semibold">{getLabelForChallenge(id)}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
      )}
    </div>,
    document.body,
  );
}
