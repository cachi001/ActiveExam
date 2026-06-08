/**
 * useExamProctoring — proctoring REAL de fondo para el flujo de EXAMEN del alumno.
 *
 * Cablea las mismas primitivas que el harness admin pero en una versión LEAN
 * pensada para correr en silencio mientras el alumno rinde:
 *
 *  1. Abre una sesión `modo:'examen'` en el backend slim al iniciar.
 *  2. Carga el motor MediaPipe real (fallback honesto al stub si init() falla)
 *     y crea un VisionPipeline (motor → reglas → sink).
 *  3. Corre un loop de frames (setInterval) sobre el <video> del preview,
 *     monta los detectores de contexto del navegador y por CADA evento discreto
 *     captura un screenshot y lo streamea al backend (fire-and-forget).
 *  4. Expone { sessionId, score, eventCount, activo } + detener() para cerrar
 *     prolijo al finalizar el examen.
 *
 * REGLAS DE DOMINIO:
 * - L2.5: solo produce/streamea señales y evidencia; NUNCA sanciona.
 * - Cliente = sensor no confiable: el backend re-infiere y firma server-side.
 * - Degradación silenciosa: un error de red NUNCA rompe el examen.
 * - Dual-mode: con USE_REAL_BACKEND=0 funciona (sesión mock, envío null).
 *
 * GUARDIA DE OVERLAY (C-53/D4): este flujo de examen del alumno corre el
 * pipeline de visión EN SILENCIO y NUNCA debe montar `VisionOverlay` ni dibujar
 * puntos/box sobre la cara del alumno. El overlay de diagnóstico (canvas con
 * mesh/box/gaze) queda restringido al harness de staff. NO importar ni instanciar
 * `VisionOverlay` aquí: pintar el rostro del examinado es intrusivo y viola la spec
 * `vision-overlay-canvas` ("El examen del alumno no dibuja overlay sobre la cara").
 *
 * DATO SENSIBLE (Ley 25.326): el screenshot base64 es imagen del alumno; se
 * transmite solo al backend, nunca se loguea ni se persiste localmente.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type { RefObject } from 'react';
import { api } from '../lib/api';
import { useApp } from '../lib/store';
import { captureVideoFrame } from '../lib/videoFrameCapture';
import { MediaPipeVisionEngine } from '../vision/MediaPipeVisionEngine';
import type { VisionEngine } from '../vision/VisionEngine';
import { loadRealEngine, disposeRealEngine } from '../vision/harnessEngineLoader';
import { VisionPipeline, type EventSink } from './visionPipeline';
import { StateTransitionRules, DEFAULT_CONFIG } from './stateTransitionRules';
import { PESO_SCORE } from './riskWeights';
import {
  FocusDetector,
  FullscreenDetector,
  ClipboardDetector,
  detectExtraMonitor,
  type ScreenDetailsProvider,
} from './contextDetectors';
import { descripcionEvento } from '../lib/api';
import type { EventoSesion, Severidad, TipoEvento } from '../lib/types';
import { CircularEventBuffer } from '../transport/eventBuffer';
import { IndexedDbEventBufferStore } from '../transport/indexedDbBufferStore';
import { drainAndReplay } from '../transport/replayCoordinator';
import type { ReplaySender } from '../transport/replayCoordinator';
import { hashClip } from '../features/biometria/clipCustody';

// DEUDA TÉCNICA: los siguientes módulos están implementados y testeados pero no se
// cablea porque el backend slim no los soporta aún:
//
// - `../transport/eventSignature.ts` (firma HMAC de eventos): el backend slim NO valida
//   la firma del payload del evento. Firmar sin validación es teatro de seguridad.
//   Cablear cuando el backend implemente la validación.
//
// - `../features/custodia/evidenceCapture.ts` (cadena de custodia completa): requiere
//   el endpoint `/evidence/presign` (inexistente en el slim), storage externo
//   (MinIO/S3 con Object Lock) y `sessionKey` rotativa post-verificación biométrica.
//   Cablear cuando se implemente el backend completo de evidencia (C-12/C-24).

/** Máximo de eventos recientes que el panel del examen muestra. */
const MAX_EVENTOS = 30;

/** ~5 fps: suficiente para detección en vivo sin saturar el cliente. */
const FRAME_INTERVAL_MS = 200;

/** Identificación mínima del examen que necesita el proctoring. */
interface ExamenInfo {
  id?: string;
  nombre?: string;
}

/** Estado observable que el hook expone al componente Examen. */
export interface ExamProctoringState {
  /** id de la sesión backend (real o mock). null hasta que resuelve. */
  sessionId: string | null;
  /** score de riesgo acumulado (0..100). Prioriza, NO sanciona. */
  score: number;
  /** cantidad de eventos discretos detectados en la sesión. */
  eventCount: number;
  /** true mientras el loop de detección está corriendo. */
  activo: boolean;
  /** últimos eventos detectados (para el panel de señales del examen). */
  eventos: EventoSesion[];
  /** true si hay un monitor adicional conectado AHORA mismo (polling, no historial). */
  extraMonitorActive: boolean;
}

export interface UseExamProctoringResult extends ExamProctoringState {
  /** Corta el loop, dispone el motor y limpia detectores. Idempotente. */
  detener: () => void;
}

/**
 * Hook de proctoring real para el examen.
 *
 * @param videoRef - ref al <video> del preview (su stream alimenta la detección).
 * @param examen   - examen activo (etiqueta + examId para la sesión backend).
 */
export function useExamProctoring(
  videoRef: RefObject<HTMLVideoElement>,
  examen?: ExamenInfo | null,
): UseExamProctoringResult {
  const setProctoringSessionId = useApp((s) => s.setProctoringSessionId);
  const addScore = useApp((s) => s.addScore);
  // C-64 D1: si Consent.tsx ya creó la sesión anticipada, reutilizarla — no crear otra.
  const existingSessionId = useApp((s) => s.proctoringSessionId);

  // ------ Estado observable ------
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [score, setScore] = useState(0);
  const [eventCount, setEventCount] = useState(0);
  const [activo, setActivo] = useState(false);
  const [eventos, setEventos] = useState<EventoSesion[]>([]);
  // Estado en vivo del monitor adicional. Refleja la ultima lectura del polling
  // (cada 5s). Examen.tsx lo usa para bloquear la rendicion mientras este `true`.
  const [extraMonitorActive, setExtraMonitorActive] = useState(false);

  // ------ Refs del motor / pipeline / loop ------
  const engineRef = useRef<VisionEngine | null>(null);
  const pipelineRef = useRef<VisionPipeline | null>(null);
  const frameLoopRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const sessionPromiseRef = useRef<Promise<string | null> | null>(null);
  const faceCountRef = useRef(0);
  const stoppedRef = useRef(false);

  // ------ Buffer IndexedDB (D1) ------
  // Instancia única que persiste toda la duración del hook. Null si IndexedDB
  // no está disponible (modo privado / iOS Safari → degradación silenciosa, R3).
  const bufferRef = useRef<CircularEventBuffer | null>(null);

  // ------ Señales de contexto del navegador (acumuladas, consumidas por tick) ------
  const focusLostRef = useRef(false);
  const tabChangedRef = useRef(false);
  const fullscreenExitedRef = useRef(false);
  const clipboardRef = useRef<'copy' | 'paste' | null>(null);
  const extraMonitorRef = useRef<boolean | null>(null);

  // ------ Callback de cada evento discreto (ref estable, lee estado fresco) ------
  const handleEvent = useRef<EventSink['sendEvent']>(async () => {});
  handleEvent.current = async (rawEvent) => {
    // Acumular score en el store global (scorePropio, L2.5 — prioriza, no sanciona).
    addScore(PESO_SCORE[rawEvent.severidad as Severidad] ?? 0);
    setScore((prev) =>
      Math.min(100, prev + (PESO_SCORE[rawEvent.severidad as Severidad] ?? 0)),
    );
    setEventCount((c) => c + 1);

    // Registrar en el panel de señales del examen.
    const ev: EventoSesion = {
      id: rawEvent.id,
      tipo: rawEvent.tipo as TipoEvento,
      severidad: rawEvent.severidad as Severidad,
      ts_backend: new Date().toISOString(),
      descripcion: descripcionEvento(rawEvent.tipo as TipoEvento),
      tiene_evidencia: !!rawEvent.payload?.['trigger_evidence'],
    };
    setEventos((prev) => [ev, ...prev].slice(0, MAX_EVENTOS));

    // Streaming al backend: screenshot + POST por cada evento. Fire-and-forget,
    // degradación silenciosa — un error de red NO rompe el examen.
    const sid =
      sessionIdRef.current ??
      (sessionPromiseRef.current ? await sessionPromiseRef.current : null);
    if (!sid) return;
    const screenshot = videoRef.current
      ? captureVideoFrame(videoRef.current, 0.7)
      : null;
    const faceCountCliente =
      rawEvent.payload?.face_count != null
        ? Number(rawEvent.payload.face_count)
        : faceCountRef.current;

    // Calcular hash SHA-256 del screenshot para la primera capa de cadena de
    // custodia del cliente (D5). Si falla (screenshot null / WebCrypto no disponible),
    // se omite el campo del payload — no bloquea el evento.
    let screenshotHash: string | undefined;
    if (screenshot) {
      try {
        const b64 = screenshot.replace(/^data:[^;]+;base64,/, '');
        const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
        screenshotHash = await hashClip(bytes.buffer);
      } catch {
        // error de WebCrypto: continuar sin el hash
      }
    }

    // Payload del evento — omitir screenshot_sha256_cliente si es undefined.
    const eventoPayload: {
      tipo: string;
      severidad: string;
      ts_cliente: string;
      payload?: Record<string, unknown>;
      screenshot_base64?: string | null;
      face_count_cliente?: number | null;
      screenshot_sha256_cliente?: string;
    } = {
      tipo: rawEvent.tipo,
      severidad: rawEvent.severidad,
      ts_cliente: new Date().toISOString(),
      payload: rawEvent.payload,
      screenshot_base64: screenshot,
      face_count_cliente: faceCountCliente,
      ...(screenshotHash !== undefined && { screenshot_sha256_cliente: screenshotHash }),
    };

    // Patrón buffer-first con purga-en-éxito (D1, CRÍTICO):
    // 1. Persistir ANTES del POST (idempotente por id — si falla el POST, queda para el drain).
    // 2. Ejecutar el POST.
    // 3. Si el POST resuelve OK → confirm(id) para PURGAR del buffer.
    // 4. Si el POST rechaza (red caída) → NO confirmar (queda pendiente para drainAndReplay).
    //
    // Sin confirm on-success, el buffer retiene todos los eventos del examen y el drain
    // los reinyecta masivamente en la primera reconexión (el backend slim NO deduplica).
    await bufferRef.current?.append(rawEvent.id, eventoPayload).catch(() => {});

    try {
      await api.enviarEventoProctoring(sid, eventoPayload);
      // POST resolvió OK → purgar del buffer (evento a salvo server-side).
      await bufferRef.current?.confirm(rawEvent.id).catch(() => {});
    } catch (err) {
      // POST rechazado (red caída) → no confirmar; el evento queda en el buffer
      // para que drainAndReplay lo reenvíe al recuperar la conexión.
      // C-64 D5: loguear el error para diagnóstico en prod (antes era catch silencioso).
      console.error('[proctoring] POST evento falló:', err);
    }
  };

  // ------ detener(): corta loop, dispone motor, limpia ------
  const detener = useCallback(() => {
    if (stoppedRef.current) return;
    stoppedRef.current = true;
    if (frameLoopRef.current) {
      clearInterval(frameLoopRef.current);
      frameLoopRef.current = null;
    }
    pipelineRef.current = null;
    engineRef.current = null;
    sessionIdRef.current = null;
    sessionPromiseRef.current = null;
    setProctoringSessionId(null);
    setActivo(false);
    // Liberar el motor WASM/GPU (singleton de módulo).
    void disposeRealEngine().catch(() => {});
  }, [setProctoringSessionId]);

  // ------ Arranque del proctoring (una vez por montaje) ------
  useEffect(() => {
    stoppedRef.current = false;
    let cancelled = false;

    // --- Inicializar buffer IndexedDB (R3: degradación silenciosa si no está disponible) ---
    try {
      bufferRef.current = new CircularEventBuffer(new IndexedDbEventBufferStore());
    } catch {
      bufferRef.current = null; // IndexedDB no disponible → operar sin buffer
    }

    // --- Adaptador ReplaySender: envuelve api.enviarEventoProctoring como ReplaySender ---
    // El buffer almacena el payload del evento (message) serializado; el sender
    // lo reenvía al backend usando el sessionId actual de sessionIdRef.
    const replaySender: ReplaySender = async (record) => {
      const sid = sessionIdRef.current;
      if (!sid) return { status: 'persisted', id: record.id };
      await api.enviarEventoProctoring(sid, record.message as Parameters<typeof api.enviarEventoProctoring>[1]);
      // El backend slim no distingue persisted/duplicate — siempre tratamos el 200 como persisted.
      return { status: 'persisted', id: record.id };
    };

    // --- handleDrain: drena el buffer al recuperar la conexión ---
    // Gracias al confirm on-success en handleEvent, solo contiene eventos que fallaron
    // mientras la red estaba caída — el drain reenvía únicamente esos (no el examen completo).
    const handleDrain = () => {
      if (bufferRef.current) {
        drainAndReplay(bufferRef.current, replaySender).catch(() => {});
      }
    };

    // --- handleOffline: solo para diagnóstico / future use ---
    const handleOffline = () => {
      // sin acción requerida: el patrón buffer-first en handleEvent ya persiste
      // cada evento antes del POST; al volver online handleDrain los reenvía.
    };

    window.addEventListener('online', handleDrain);
    window.addEventListener('offline', handleOffline);

    // --- Detectores de contexto del navegador ---
    const focus = new FocusDetector((sig) => {
      if (sig.focus_lost !== undefined) focusLostRef.current = sig.focus_lost;
      if (sig.tab_changed !== undefined) tabChangedRef.current = sig.tab_changed;
    });
    const fullscreen = new FullscreenDetector((sig) => {
      if (sig.fullscreen_exited) fullscreenExitedRef.current = true;
    });
    const clipboard = new ClipboardDetector((sig) => {
      if (sig.clipboard_action) clipboardRef.current = sig.clipboard_action;
    });
    focus.start();
    fullscreen.start();
    clipboard.start();

    // Monitor adicional — polling pasivo cada 5 s (degrada a null si no hay API).
    let monitorPollActive = true;
    const pollMonitor = async () => {
      const provider: ScreenDetailsProvider | undefined =
        typeof window !== 'undefined' && 'getScreenDetails' in window
          ? () =>
              (
                window as unknown as {
                  getScreenDetails: () => Promise<{ screens: unknown[] }>;
                }
              ).getScreenDetails()
          : undefined;
      const sig = await detectExtraMonitor(provider);
      const active = sig?.extra_monitor === true;
      extraMonitorRef.current = sig?.extra_monitor ?? null;
      // Solo set-state si cambia (evita re-renders innecesarios).
      setExtraMonitorActive((prev) => (prev !== active ? active : prev));
      if (monitorPollActive) setTimeout(pollMonitor, 5000);
    };
    void pollMonitor();

    // --- Carga del motor + sesión + loop (async) ---
    void (async () => {
      // C-64 D1: idempotencia — si Consent.tsx ya creó la sesión anticipada, reutilizarla.
      // Si ya existe en el store, setear directamente sin llamar al backend de nuevo.
      if (existingSessionId) {
        sessionIdRef.current = existingSessionId;
        setSessionId(existingSessionId);
        sessionPromiseRef.current = Promise.resolve(existingSessionId);
      } else if (examen?.id) {
        // Abrir sesión en el backend (fire-and-forget; sessionPromiseRef permite que
        // el primer evento espere si llega antes de que resuelva). Exigimos `examen.id`:
        // sin él, la sesión quedaba orfana ("examen sin examen vinculado") y aparecía
        // en supervisión en vivo sin contexto, indistinguible de una prueba.
        sessionPromiseRef.current = api
          .crearSesionProctoring('examen', examen.nombre, examen.id)
          .then((s) => {
            if (cancelled) return null;
            sessionIdRef.current = s.id;
            setSessionId(s.id);
            setProctoringSessionId(s.id);
            return s.id;
          })
          .catch(() => null);
      } else {
        // Llegamos a /examen sin un examenActivo válido (deep-link, reload sin
        // contexto). NO creamos sesión orfana — el flujo del alumno falla seguro
        // y el panel de supervisión queda limpio.
        sessionPromiseRef.current = Promise.resolve(null);
      }

      // Cargar motor real; fallback honesto al stub si init() falla (no rompe).
      let engine: VisionEngine;
      try {
        engine = await loadRealEngine();
      } catch {
        engine = new MediaPipeVisionEngine();
        try {
          await engine.init();
        } catch {
          /* el stub no debería fallar; si lo hace, abortar el arranque */
          return;
        }
      }
      if (cancelled || stoppedRef.current) {
        void disposeRealEngine().catch(() => {});
        return;
      }
      engineRef.current = engine;

      // Sink LEAN: delega cada evento al handler con estado fresco.
      const sink: EventSink = {
        sendEvent: (args) => handleEvent.current(args),
      };
      pipelineRef.current = new VisionPipeline({
        engine,
        sink,
        rules: new StateTransitionRules({ ...DEFAULT_CONFIG }),
      });
      setActivo(true);

      // Loop de frames: captura + inferencia + reglas (onSignals para no doblar
      // la inferencia) + consumo de señales de contexto.
      frameLoopRef.current = setInterval(() => {
        void runFrameTick({
          videoRef,
          engineRef,
          pipelineRef,
          faceCountRef,
          focusLostRef,
          tabChangedRef,
          fullscreenExitedRef,
          clipboardRef,
          extraMonitorRef,
        });
      }, FRAME_INTERVAL_MS);
    })();

    return () => {
      cancelled = true;
      monitorPollActive = false;
      focus.stop();
      fullscreen.stop();
      clipboard.stop();
      window.removeEventListener('online', handleDrain);
      window.removeEventListener('offline', handleOffline);
      // Drain final: enviar cualquier evento pendiente al finalizar el examen.
      if (bufferRef.current) {
        drainAndReplay(bufferRef.current, replaySender).catch(() => {});
      }
      detener();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [examen?.id]);

  return { sessionId, score, eventCount, activo, eventos, extraMonitorActive, detener };
}

// ---------------------------------------------------------------------------
// runFrameTick — cuerpo del loop de frames (LEAN, sin estado de overlay).
// ---------------------------------------------------------------------------

interface FrameTickRefs {
  videoRef: RefObject<HTMLVideoElement>;
  engineRef: RefObject<VisionEngine | null>;
  pipelineRef: RefObject<VisionPipeline | null>;
  faceCountRef: { current: number };
  focusLostRef: { current: boolean };
  tabChangedRef: { current: boolean };
  fullscreenExitedRef: { current: boolean };
  clipboardRef: { current: 'copy' | 'paste' | null };
  extraMonitorRef: { current: boolean | null };
}

/**
 * Procesa un frame: capta ImageBitmap, corre detectFaces/detectFaceMesh y evalúa
 * las reglas con onSignals (la inferencia ya se hizo, evitamos doble pasada).
 * Un error de frame NO crashea el loop (degradación silenciosa).
 */
async function runFrameTick(refs: FrameTickRefs): Promise<void> {
  const video = refs.videoRef.current;
  const engine = refs.engineRef.current;
  const pipeline = refs.pipelineRef.current;
  if (!video || !engine || !pipeline || video.readyState < 2) return;

  try {
    const frame = await createImageBitmap(video);
    let faceCount = 0;
    let gaze: { x: number; y: number } | undefined;
    try {
      const fd = await engine.detectFaces(frame);
      faceCount = fd.face_count;
      if (fd.face_count >= 1) {
        try {
          const mesh = await engine.detectFaceMesh(frame);
          gaze = mesh.gaze;
        } catch {
          /* mesh opcional: la ausencia de gaze no interrumpe el frame */
        }
      }
    } catch {
      /* motor sin inferencia (stub): seguimos solo con señales de contexto */
      faceCount = 0;
    }
    frame.close();
    refs.faceCountRef.current = faceCount;

    // Consumir señales de contexto y resetear (excepto extra_monitor, por polling).
    const snapFocus = refs.focusLostRef.current;
    const snapTab = refs.tabChangedRef.current;
    const snapFullscreen = refs.fullscreenExitedRef.current;
    const snapClipboard = refs.clipboardRef.current;
    refs.focusLostRef.current = false;
    refs.tabChangedRef.current = false;
    refs.fullscreenExitedRef.current = false;
    refs.clipboardRef.current = null;

    await pipeline.onSignals({
      ts_ms: Date.now(),
      face_count: faceCount,
      gaze,
      focus_lost: snapFocus,
      extra_monitor: refs.extraMonitorRef.current === true,
      tab_changed: snapTab,
      fullscreen_exited: snapFullscreen,
      clipboard_action: snapClipboard ?? undefined,
    });
  } catch {
    /* error de frame: no romper el loop */
  }
}
