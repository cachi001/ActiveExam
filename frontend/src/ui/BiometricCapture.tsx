/**
 * BiometricCapture — componente compartido de captura biométrica inmersiva (C-36).
 *
 * Encapsula la LÓGICA: acceso a cámara (getUserMedia), loop RAF de detección real
 * con el motor MediaPipe (loadEnrollmentEngine/disposeEnrollmentEngine), evaluación
 * secuencial de retos con baseline neutral (C-54: evaluateChallengeRelative,
 * framesMinForChallengeSeq, fisherYatesShuffle) y fallback manual cuando WebGL no
 * está disponible. La parte PRESENTACIONAL vive en ./biometric/ (CaptureOverlay +
 * sub-componentes).
 *
 * C-54 — Máquina de estados secuencial (D-1):
 * idle → baseline → challenge[N] → cooldown → done
 *
 * DATOS SENSIBLES (Ley 25.326): los landmarks del último frame se entregan al caller
 * via onComplete; el caller computa el embedding según RN-BIO-07/08.
 * El cliente es SENSOR NO CONFIABLE (RN-GLB-01): el backend re-infiere y firma.
 */

import { useCallback, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { CaptureOverlay } from './biometric/CaptureOverlay';
import { CaptureError } from './biometric/CaptureError';
import { playStepCompleted, playSuccess, playError } from './biometric/sounds';
import { decideCameraResumeActions } from './biometric/cameraResume';
import { snapshotToCanvas, getLabelForChallenge, COOLDOWN_MS } from './biometric/biometricUtils';
import { startDetectionLoop as startDetectionLoopImpl } from './biometric/detectionLoop';
import { useBiometricRefs } from './biometric/useBiometricRefs';
import { useCameraInit } from './biometric/useCameraInit';
import { disposeEnrollmentEngine } from '../vision/enrollmentEngineLoader';
import { fisherYatesShuffle } from '../vision/enrollmentChallengeDetector';
import { SEQUENTIAL_CHALLENGES, resumirPasivoDeLaCaptura, hayEvidenciaDeVida } from '../vision/liveness';
import type { FaceLandmark } from '../vision/VisionEngine';
import type { SequentialChallenge, TurnDirection } from '../vision/liveness';

export interface BiometricCaptureProps {
  /** @deprecated El catálogo secuencial es fijo desde C-54; no pasar challenges externos. */
  challenges?: SequentialChallenge[];
  onComplete: (
    landmarks: FaceLandmark[],
    frames: HTMLCanvasElement[],
    passiveOk: boolean,
    retosResueltos: string[],
    virtualCameraDetected: boolean,
  ) => void;
  onCancel: () => void;
}

export function BiometricCapture({ challenges, onComplete, onCancel }: BiometricCaptureProps) {
  const refs = useBiometricRefs();
  const {
    videoRef, containerRef, streamRef, rafHandleRef, engineRef,
    lastLandmarksRef, faseRef, desafiosRef, resueltosRef, procesarCompletadoRef,
    challengeIndexRef, completadosRef, baselineRef, baselineAccumulatorRef,
    baselineFrameCountRef, nosePositionsRef, bestReferenceFrameRef,
    cooldownActiveRef, cooldownTimerRef, desafiosBarajadosRef, turnDirectionRef,
    challengeCountsRef, challengeNeutralFramesRef, gestureAccumMsRef,
    gestureLostMsRef, lastFrameTimeRef, wasHoldingRef, lastProgressTickFractionRef,
    livenessWindowRef, passiveOkRef, passiveFramesEvaluadosRef, passiveFalseFramesRef,
    prevFrameDataRef, virtualCameraRef, wasBlockedByFramingRef,
    framingHintRef, framingStableRef, luminanceCanvasRef, fallbackManualRef,
    fase, setFase, desafios, setDesafios, resueltos, setResueltos,
    motorListo, setMotorListo, camaraLista, setCamaraLista,
    motorError, setMotorError, fallbackManual, setFallbackManual,
    errorMsg, setErrorMsg, cooldownActivo, setCooldownActivo,
    retoRecienResuelto, setRetoRecienResuelto,
    framingHint, setFramingHint, progreso, setProgreso, tonoOvalo, setTonoOvalo,
    turnDirection, setTurnDirection, stallTip, setStallTip,
  } = refs;

  // Sync de refs para acceso desde el loop RAF
  useEffect(() => { faseRef.current = fase; }, [fase, faseRef]);
  useEffect(() => { resueltosRef.current = resueltos; }, [resueltos, resueltosRef]);
  useEffect(() => { desafiosRef.current = desafios; }, [desafios, desafiosRef]);
  useEffect(() => { fallbackManualRef.current = fallbackManual; }, [fallbackManual, fallbackManualRef]);

  // Detector de estancamiento de gesto
  useEffect(() => {
    const idx = desafios.findIndex((id) => !resueltos.includes(id));
    const retoId = idx >= 0 ? desafios[idx] : null;
    setStallTip(null);
    if (!retoId || cooldownActivo || framingHint !== null) return;
    const STALL_TIP_MS = 6000;
    const TIPS: Record<SequentialChallenge, string> = {
      parpadear: 'Cerrá los ojos un poco más y mantenelos cerrados un par de segundos, sin apurarte.',
      girar_cabeza: 'Girá la cabeza un poco más al lado indicado y quedate quieto en esa posición hasta que la barra avance.',
      sonreír: 'Marcá más la sonrisa (mostrá los dientes está bien) y sostenela quieta hasta que la barra avance.',
    };
    const tip = TIPS[retoId] ?? 'Hacé el gesto más marcado y sostenelo quieto hasta que la barra avance.';
    const t = window.setTimeout(() => setStallTip(tip), STALL_TIP_MS);
    return () => window.clearTimeout(t);
  }, [resueltos, desafios, cooldownActivo, framingHint, progreso, setStallTip]);

  // Inicialización: barajar retos y elegir dirección
  useEffect(() => {
    const catalogo = challenges && challenges.length > 0 ? challenges : [...SEQUENTIAL_CHALLENGES];
    const barajados = fisherYatesShuffle([...catalogo]);
    desafiosBarajadosRef.current = barajados;
    setDesafios(barajados);
    desafiosRef.current = barajados;
    const dir: TurnDirection = Math.random() < 0.5 ? 'izquierda' : 'derecha';
    turnDirectionRef.current = dir;
    setTurnDirection(dir);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const activarFullscreen = useCallback(() => {
    const container = containerRef.current;
    if (!container || !container.requestFullscreen) return;
    container.requestFullscreen().catch(() => {});
  }, [containerRef]);

  const resolverRetoFromLoop = useCallback((id: SequentialChallenge) => {
    setResueltos((prev) => {
      if (prev.includes(id)) return prev;
      const next = [...prev, id];
      if (desafiosRef.current.length > 0 && next.length >= desafiosRef.current.length) {
        setFase('exito');
      }
      return next;
    });
  }, [desafiosRef, setFase, setResueltos]);

  const activarCooldown = useCallback((retoResueltoId: SequentialChallenge) => {
    cooldownActiveRef.current = true;
    setCooldownActivo(true);
    setRetoRecienResuelto(retoResueltoId);
    playStepCompleted();
    resolverRetoFromLoop(retoResueltoId);
    cooldownTimerRef.current = setTimeout(() => {
      challengeIndexRef.current += 1;
      cooldownActiveRef.current = false;
      setCooldownActivo(false);
      setRetoRecienResuelto(null);
      cooldownTimerRef.current = null;
      lastProgressTickFractionRef.current = 0;
      lastFrameTimeRef.current = null;
    }, COOLDOWN_MS);
  }, [resolverRetoFromLoop, cooldownActiveRef, cooldownTimerRef, challengeIndexRef,
      lastProgressTickFractionRef, lastFrameTimeRef, setCooldownActivo, setRetoRecienResuelto]);

  const startDetectionLoop = useCallback((engine: import('../vision/VisionEngine').VisionEngine) => {
    startDetectionLoopImpl(engine, {
      faseRef, videoRef, rafHandleRef, engineRef,
      luminanceCanvasRef, framingStableRef, framingHintRef,
      livenessWindowRef, passiveOkRef, passiveFramesEvaluadosRef, passiveFalseFramesRef,
      prevFrameDataRef, virtualCameraRef, wasBlockedByFramingRef,
      baselineRef, baselineFrameCountRef, baselineAccumulatorRef,
      nosePositionsRef, bestReferenceFrameRef, cooldownActiveRef,
      challengeIndexRef, desafiosBarajadosRef, completadosRef,
      challengeCountsRef, challengeNeutralFramesRef, gestureAccumMsRef,
      gestureLostMsRef, lastFrameTimeRef, wasHoldingRef,
      lastProgressTickFractionRef, turnDirectionRef, lastLandmarksRef,
      setFramingHint, setTonoOvalo, setProgreso, activarCooldown,
    });
  }, [activarCooldown, faseRef, videoRef, rafHandleRef, engineRef, luminanceCanvasRef, // eslint-disable-line react-hooks/exhaustive-deps
      framingStableRef, framingHintRef, livenessWindowRef, passiveOkRef, passiveFramesEvaluadosRef, passiveFalseFramesRef,
      prevFrameDataRef, virtualCameraRef, wasBlockedByFramingRef, baselineRef,
      baselineFrameCountRef, baselineAccumulatorRef, nosePositionsRef, bestReferenceFrameRef,
      cooldownActiveRef, challengeIndexRef, desafiosBarajadosRef, completadosRef,
      challengeCountsRef, challengeNeutralFramesRef, gestureAccumMsRef, gestureLostMsRef,
      lastFrameTimeRef, wasHoldingRef, lastProgressTickFractionRef, turnDirectionRef,
      lastLandmarksRef, setFramingHint, setTonoOvalo, setProgreso]);

  // Inicialización de cámara y motor
  useCameraInit({
    streamRef, videoRef, rafHandleRef, cooldownTimerRef, engineRef,
    setCamaraLista, setErrorMsg, setFase, setMotorListo, setMotorError,
    setFallbackManual, setTonoOvalo, activarFullscreen, startDetectionLoop,
  });

  const procesarCompletado = useCallback(() => {
    if (rafHandleRef.current !== null) { cancelAnimationFrame(rafHandleRef.current); rafHandleRef.current = null; }
    if (cooldownTimerRef.current !== null) { clearTimeout(cooldownTimerRef.current); cooldownTimerRef.current = null; }
    void disposeEnrollmentEngine();
    if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
    const frames: HTMLCanvasElement[] = Array.from(
      new Set([bestReferenceFrameRef.current, snapshotToCanvas(videoRef.current)].filter((c): c is HTMLCanvasElement => c !== null)),
    );
    const isFallback = fallbackManualRef.current;
    // El pasivo resume la captura ENTERA (ver resumirPasivoDeLaCaptura): antes se
    // reportaba el resultado del último frame, con el alumno ya quieto tras
    // completar los retos, y salía "no superado" junto a los tres retos hechos.
    const pasivoDeLaCaptura = isFallback
      ? false
      : resumirPasivoDeLaCaptura({
          algunaVezOk: passiveOkRef.current,
          framesEvaluados: passiveFramesEvaluadosRef.current,
        });
    // El veredicto suma las DOS fuentes: haber completado los retos que se le
    // pidieron —en el orden aleatorio en que se pidieron— es evidencia de vida
    // más fuerte que las varianzas del pasivo, cuyos umbrales hoy no se cumplen
    // ni con una persona real. Reportar "no superado" a alguien que hizo los tres
    // retos era contradecir la evidencia directa, y quedaba escrito en su legajo.
    const passiveOkFinal = isFallback
      ? false
      : hayEvidenciaDeVida({
          pasivoOk: pasivoDeLaCaptura,
          pedidos: desafiosRef.current,
          resueltos: resueltosRef.current,
        });
    const virtualCameraFinal = isFallback ? false : virtualCameraRef.current;
    if (!passiveOkFinal || virtualCameraFinal) playError();
    onComplete(lastLandmarksRef.current, frames, passiveOkFinal, resueltosRef.current, virtualCameraFinal);
  }, [onComplete, rafHandleRef, cooldownTimerRef, bestReferenceFrameRef, videoRef,
      fallbackManualRef, passiveOkRef, passiveFramesEvaluadosRef, virtualCameraRef, lastLandmarksRef,
      resueltosRef, desafiosRef]);

  useEffect(() => { procesarCompletadoRef.current = procesarCompletado; }, [procesarCompletado, procesarCompletadoRef]);

  useEffect(() => {
    if (fase !== 'exito') return;
    playSuccess();
    setTonoOvalo('exito');
    setProgreso(1);
    const t = setTimeout(() => { procesarCompletadoRef.current?.(); }, 1600);
    return () => clearTimeout(t);
  }, [fase, procesarCompletadoRef, setTonoOvalo, setProgreso]);

  const handleCancel = useCallback(() => {
    // 1. Frenar loop + timers (sincrónico, barato) para que el engine no se use tras liberarlo.
    if (rafHandleRef.current !== null) { cancelAnimationFrame(rafHandleRef.current); rafHandleRef.current = null; }
    if (cooldownTimerRef.current !== null) { clearTimeout(cooldownTimerRef.current); cooldownTimerRef.current = null; }
    // 2. Liberar la cámara y CERRAR el overlay YA. No esperamos el teardown pesado.
    streamRef.current?.getTracks().forEach((t) => t.stop());
    onCancel();
    // 3. Teardown pesado en segundo plano: `dispose()` del motor MediaPipe cierra los
    //    landmarkers WASM de forma SÍNCRONA (bloquea el hilo unos cientos de ms). Si corre
    //    antes de onCancel, el cierre "tarda demasiado". Diferirlo un tick lo hace instantáneo.
    setTimeout(() => {
      void disposeEnrollmentEngine();
      if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
    }, 0);
  }, [onCancel, rafHandleRef, cooldownTimerRef, streamRef]);

  // Si el alumno sale de pantalla completa a mitad de la captura (Esc, gesto del
  // SO, etc.), cerramos la captura en vez de dejarla corriendo "encogida": el
  // óvalo y el video están armados para ocupar el viewport completo de la
  // pantalla completa, y todo lo que depende de esa geometría (el loop de
  // detección, el layout del panel de instrucciones) queda desincronizado si
  // seguimos con la cámara abierta en la ventana normal. Cerrar y dejar que
  // vuelva a "Iniciar captura de referencia" es más simple y confiable que
  // intentar reacomodar todo en caliente.
  useEffect(() => {
    const onFullscreenChange = () => {
      if (!document.fullscreenElement && faseRef.current === 'capturando') {
        handleCancel();
      }
    };
    document.addEventListener('fullscreenchange', onFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', onFullscreenChange);
  }, [handleCancel, faseRef]);

  const reacquireCamera = useCallback(async () => {
    try {
      streamRef.current?.getTracks().forEach((t) => t.stop());
      const stream = await navigator.mediaDevices?.getUserMedia({ video: { facingMode: 'user', width: 640, height: 480 } });
      if (!stream) return;
      streamRef.current = stream;
      const video = videoRef.current;
      if (video) { video.srcObject = stream; await video.play().catch(() => {}); }
      if (faseRef.current === 'capturando' && engineRef.current) {
        if (rafHandleRef.current !== null) { cancelAnimationFrame(rafHandleRef.current); rafHandleRef.current = null; }
        startDetectionLoop(engineRef.current);
      }
    } catch { /* re-adquisición fallida, no romper */ }
  }, [startDetectionLoop, streamRef, videoRef, faseRef, engineRef, rafHandleRef]);

  useEffect(() => {
    const onVisibility = () => {
      const track = streamRef.current?.getVideoTracks()[0];
      const acciones = decideCameraResumeActions({
        visible: document.visibilityState === 'visible',
        trackEnded: !track || track.readyState === 'ended',
        videoPaused: videoRef.current?.paused ?? false,
        loopActive: rafHandleRef.current !== null,
        capturing: faseRef.current === 'capturando',
      });
      for (const accion of acciones) {
        if (accion === 'reacquire') void reacquireCamera();
        else if (accion === 'play') void videoRef.current?.play().catch(() => {});
        else if (accion === 'restart-loop' && engineRef.current) startDetectionLoop(engineRef.current);
      }
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, [reacquireCamera, startDetectionLoop, streamRef, videoRef, rafHandleRef, faseRef, engineRef]);

  const resolverRetoManual = useCallback((id: string) => {
    setResueltos((prev) => {
      if (prev.includes(id)) return prev;
      const next = [...prev, id];
      if (desafiosRef.current.length > 0 && next.length >= desafiosRef.current.length) setFase('exito');
      return next;
    });
  }, [desafiosRef, setFase, setResueltos]);

  const challengeIdx      = desafios.findIndex((id) => !resueltos.includes(id));
  const retoActivoId      = challengeIdx >= 0 ? desafios[challengeIdx] : null;
  const totalResueltos    = resueltos.length;
  const totalDesafios     = desafios.length;
  const todosResueltos    = totalDesafios > 0 && totalResueltos >= totalDesafios;
  const enExito           = fase === 'exito' || todosResueltos;
  const listoParaMostrar  = (motorListo && camaraLista) || fallbackManual;
  const retoRecienResueltoLabel = retoRecienResuelto ? getLabelForChallenge(retoRecienResuelto) : null;

  let retoActualLabel: string;
  if (cooldownActivo && retoRecienResuelto) {
    retoActualLabel = `Paso ${resueltos.length} completado ✓`;
  } else if (!retoActivoId) {
    retoActualLabel = '¡Listo!';
  } else if (retoActivoId === 'girar_cabeza') {
    retoActualLabel = `Girá despacio a la ${turnDirection === 'izquierda' ? 'IZQUIERDA' : 'DERECHA'} y mantené`;
  } else if (retoActivoId === 'parpadear') {
    retoActualLabel = 'Cerrá los ojos y mantené';
  } else if (retoActivoId === 'sonreír') {
    retoActualLabel = 'Sonreí y sostené';
  } else {
    retoActualLabel = getLabelForChallenge(retoActivoId);
  }

  if (fase === 'error') {
    return createPortal(
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
      listoParaMostrar={listoParaMostrar}
      motorError={motorError}
      enExito={enExito}
      motorListo={motorListo}
      fallbackManual={fallbackManual}
      retoActualLabel={retoActualLabel}
      retoActualId={retoActivoId}
      desafios={desafios}
      resueltos={resueltos}
      totalResueltos={totalResueltos}
      totalDesafios={totalDesafios}
      getLabel={getLabelForChallenge}
      onResolverManual={resolverRetoManual}
      onCancel={handleCancel}
      cooldownActivo={cooldownActivo}
      retoRecienResueltoLabel={retoRecienResueltoLabel}
      progreso={progreso}
      tonoOvalo={tonoOvalo}
      framingHint={framingHint}
      stallTip={stallTip}
    />,
    document.body,
  );
}
