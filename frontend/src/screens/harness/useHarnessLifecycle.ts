/**
 * useHarnessLifecycle — start/stop de la detección y cleanup al desmontar (C-23).
 *
 * Extraído VERBATIM desde useDetectionHarness: startHarness pide cámara, carga el
 * motor real (fallback honesto al stub), crea sink + pipeline, abre sesión en
 * modo sesión y arranca el bucle de frames; stopHarness limpia stream/refs/estado;
 * el cleanup de desmontaje libera el motor WASM y vacía el <video>.
 *
 * NO cambia el flujo de detección: recibe todas las refs/setters/factories por
 * deps y opera exactamente igual que el inline original.
 */

import { useCallback, useEffect } from 'react';
import type { RefObject, MutableRefObject } from 'react';
import { api } from '../../lib/api';
import { MediaPipeVisionEngine } from '../../vision/MediaPipeVisionEngine';
import type { VisionEngine } from '../../vision/VisionEngine';
import { loadRealEngine, disposeRealEngine } from '../../vision/harnessEngineLoader';
import type { EventSink, VisionPipeline } from '../../proctoring/visionPipeline';
import type { TransitionConfig } from '../../proctoring/stateTransitionRules';
import type { useToast } from '../../ui/toast';
import {
  FRAME_INTERVAL_MS,
  LocalHarnessEventSink,
  type EngineMode,
  type HarnessState,
  type RawSignals,
  type CoverageEntry,
  type MonitorPermission,
  type SinkEventCallback,
} from './types';
import { createFrameTick } from './frameProcessor';

interface LifecycleDeps {
  harnessState: HarnessState;
  config: TransitionConfig;
  toast: ReturnType<typeof useToast>;
  setProctoringSessionId: (id: string | null) => void;
  createSink: (onEvent: SinkEventCallback) => LocalHarnessEventSink;
  createPipeline: (engine: VisionEngine, sink: EventSink, cfg: TransitionConfig) => VisionPipeline;
  onSinkEvent: MutableRefObject<SinkEventCallback>;
  // refs
  videoRef: RefObject<HTMLVideoElement>;
  streamRef: MutableRefObject<MediaStream | null>;
  engineRef: MutableRefObject<VisionEngine | null>;
  pipelineRef: MutableRefObject<VisionPipeline | null>;
  sinkRef: MutableRefObject<LocalHarnessEventSink | null>;
  frameLoopRef: MutableRefObject<ReturnType<typeof setInterval> | null>;
  animFrameRef: MutableRefObject<number | null>;
  sessionIdRef: MutableRefObject<string | null>;
  sessionPromiseRef: MutableRefObject<Promise<string | null> | null>;
  faceCountRef: MutableRefObject<number>;
  logSeqRef: MutableRefObject<number>;
  envFocusLostRef: MutableRefObject<boolean>;
  envTabChangedRef: MutableRefObject<boolean>;
  envFullscreenExitedRef: MutableRefObject<boolean>;
  envClipboardRef: MutableRefObject<'copy' | 'paste' | null>;
  envExtraMonitorRef: MutableRefObject<boolean | null>;
  // setters
  setModoSesion: (v: boolean) => void;
  setHarnessState: (s: HarnessState) => void;
  setLogEntries: (v: never[]) => void;
  setLogTruncated: (v: boolean) => void;
  setElapsed: (v: number) => void;
  setCoverage: (v: Partial<Record<string, CoverageEntry>>) => void;
  setMonitorPermission: (v: MonitorPermission) => void;
  setEngineMode: (m: EngineMode) => void;
  setEngineError: (e: string | null) => void;
  setIsFirstEngineLoad: (v: boolean) => void;
  setSessionStart: (v: number) => void;
  setEventosEnviados: (v: number) => void;
  setRawSignals: (s: RawSignals) => void;
}

export function useHarnessLifecycle(deps: LifecycleDeps) {
  const {
    harnessState,
    config,
    toast,
    setProctoringSessionId,
    createSink,
    createPipeline,
    onSinkEvent,
    videoRef,
    streamRef,
    engineRef,
    pipelineRef,
    sinkRef,
    frameLoopRef,
    animFrameRef,
    sessionIdRef,
    sessionPromiseRef,
    faceCountRef,
    logSeqRef,
    envFocusLostRef,
    envTabChangedRef,
    envFullscreenExitedRef,
    envClipboardRef,
    envExtraMonitorRef,
    setModoSesion,
    setHarnessState,
    setLogEntries,
    setLogTruncated,
    setElapsed,
    setCoverage,
    setMonitorPermission,
    setEngineMode,
    setEngineError,
    setIsFirstEngineLoad,
    setSessionStart,
    setEventosEnviados,
    setRawSignals,
  } = deps;

  // ------ Iniciar harness ------
  const startHarness = useCallback(async (conSesion: boolean) => {
    if (harnessState !== 'idle' && harnessState !== 'stopped') return;
    setModoSesion(conSesion);
    setHarnessState('initializing');
    setLogEntries([]);
    setLogTruncated(false);
    setElapsed(0);
    logSeqRef.current = 0;
    // C-25: resetear cobertura al inicio de sesión
    setCoverage({});
    // C-32 Task 6.2: detectar disponibilidad de la API y setear estado de permiso
    setMonitorPermission(
      typeof window !== 'undefined' && 'getScreenDetails' in window ? 'idle' : 'unsupported'
    );

    try {
      // C-35 Task 1.1: Limpiar el <video> ANTES de solicitar el nuevo stream.
      // Si el componente fue desmontado y re-montado (navegacion SPA ida/vuelta),
      // el elemento <video> puede retener el frame congelado de la sesion anterior.
      // Llamar srcObject = null + load() fuerza al decoder HTML5 a descartar
      // cualquier buffer anterior e ir al estado "vacio" (fondo negro) antes de
      // que el nuevo stream llegue — el usuario no ve ningun frame residual.
      if (videoRef.current) {
        videoRef.current.srcObject = null;
        videoRef.current.load();
      }

      // Solicitar cámara
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => {});
      }

      // C-30: intentar cargar el motor real MediaPipe (lazy, chunk separado)
      // Si falla, el harness queda en load-error — no cae a simulación (D-6)
      setEngineMode('loading');
      let engine: VisionEngine;
      try {
        engine = await loadRealEngine();
        setEngineMode('real-active');
        // C-32 Task 3.3: marcar que la primera carga ya ocurrió
        setIsFirstEngineLoad(false);
      } catch (realEngineErr) {
        const errMsg = realEngineErr instanceof Error ? realEngineErr.message : String(realEngineErr);
        setEngineMode('load-error');
        setEngineError(errMsg);
        // Fallback honesto: usar stub para que el harness siga corriendo (señales de navegador siguen siendo reales)
        // pero el banner mostrará el error claramente. El stub sigue usándose para no bloquear el pipeline.
        engine = new MediaPipeVisionEngine();
        await engine.init();
      }
      engineRef.current = engine;

      // Crear sink con referencia estable que delega al onSinkEvent.current (task 3.2)
      const sink = createSink((...args) => onSinkEvent.current(...args));
      sinkRef.current = sink;

      // Crear pipeline (task 3.3)
      pipelineRef.current = createPipeline(engine, sink, config);

      const start = Date.now();
      setSessionStart(start);
      setEventosEnviados(0);
      if (conSesion) {
        // Crear sesión en el backend automáticamente al arrancar la detección (fire-and-forget).
        // sessionPromiseRef permite que onSinkEvent espere la sesión si llega antes de que resuelva.
        sessionPromiseRef.current = api.crearSesionProctoring('diagnostico', 'Detección test')
          .then((s) => { sessionIdRef.current = s.id; setProctoringSessionId(s.id); return s.id; })
          .catch(() => null);
      } else {
        // Modo test local puro: sessionIdRef queda null, onSinkEvent no enviará nada al backend.
        sessionIdRef.current = null;
        sessionPromiseRef.current = null;
      }
      setHarnessState('running');

      // Bucle de frames (task 2.2): setInterval a FRAME_INTERVAL_MS para captura estable.
      // El cuerpo del tick vive en createFrameTick (mismo flujo, mismas refs/closures).
      const frameTick = createFrameTick({
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
      });
      frameLoopRef.current = setInterval(frameTick, FRAME_INTERVAL_MS);

    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(`Error al iniciar: ${msg}`);
      setHarnessState('idle');
    }
  }, [harnessState, config, createSink, createPipeline, toast]);

  // ------ Detener harness ------
  const stopHarness = useCallback(async () => {
    // Finalizar la sesión en el backend ANTES de limpiar las refs.
    // Sin esto la sesión queda `finalizada_en = NULL` en `proctoring_session`
    // y "Supervisión en vivo" la sigue listando como activa (filtra por
    // !finalizada_en). Fire-and-forget: si la red falla, igual avanzamos con
    // el cleanup local.
    const sidPendiente =
      sessionIdRef.current ??
      (sessionPromiseRef.current ? await sessionPromiseRef.current.catch(() => null) : null);
    if (sidPendiente) {
      void api.finalizarSesionProctoring(sidPendiente).catch(() => null);
    }

    // Limpiar sesión automática al detener
    sessionIdRef.current = null;
    sessionPromiseRef.current = null;
    setProctoringSessionId(null);
    if (frameLoopRef.current) { clearInterval(frameLoopRef.current); frameLoopRef.current = null; }
    if (animFrameRef.current) { cancelAnimationFrame(animFrameRef.current); animFrameRef.current = null; }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoRef.current) {
      videoRef.current.srcObject = null;
      // C-35 Task 1.3: llamar load() despues de limpiar srcObject para que el
      // decoder HTML5 descarte el buffer interno y el elemento quede en estado vacio.
      // Esto asegura que si el harness se reinicia (Iniciar de nuevo sin navegar),
      // no haya frame residual entre el stop y el proximo startHarness().
      videoRef.current.load();
    }
    // C-32 Task 2.1: NO llamar dispose() aquí — el motor WASM permanece vivo en
    // cache entre ciclos Iniciar/Detener dentro de la misma sesión de página.
    // disposeRealEngine() solo se llama al desmontar el componente (useEffect cleanup).
    engineRef.current = null;
    pipelineRef.current = null;
    sinkRef.current = null;
    setHarnessState('stopped');
    setRawSignals({ faceDetection: null, faceMesh: null, poseAvailable: false, poseSignal: null, frameTs: 0 });
    // C-30: reset engine mode al detener
    setEngineMode('simulated');
    setEngineError(null);
  }, [setProctoringSessionId]);

  // Cleanup al desmontar
  // C-32 Task 2.2: llamar disposeRealEngine() en lugar de engineRef.current?.dispose()
  // para liberar GPU/WASM al navegar fuera del harness (cleanup de ruta SPA).
  // C-35 Task 1.2: agregar limpieza de srcObject + load() en el cleanup para el caso
  // en que el usuario navega fuera SIN pasar por stopHarness() (ruta SPA directa).
  // Al desmontar, React puede ejecutar el cleanup ANTES de que el nuevo mount haya
  // iniciado. El <video> element ya no esta en el DOM al desmontar, pero si se vuelve
  // a montar con el mismo videoRef (rerenders rapidos) el buffer puede persistir.
  // La doble garantia (stop + cleanup) cubre ambos escenarios.
  useEffect(() => {
    return () => {
      if (frameLoopRef.current) clearInterval(frameLoopRef.current);
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
      // C-35 Task 1.2: limpiar srcObject + load() al desmontar para que el <video>
      // quede en estado vacio. Cubre la navegacion SPA rapida (sin pasar por stop).
      if (videoRef.current) {
        videoRef.current.srcObject = null;
        videoRef.current.load();
      }
      // Liberar el singleton de módulo al desmontar
      disposeRealEngine().catch(() => {});
    };
  }, []);

  return { startHarness, stopHarness };
}
