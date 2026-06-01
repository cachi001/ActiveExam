/**
 * AdminDetectionHarness — Herramienta DIAGNÓSTICA para administradores (C-23).
 *
 * Ruta: /admin/detection-test  (roles: admin_examenes | coordinador)
 * Acceso: protegido por el guard de roles del router; sin examen activo, sin sesión
 * de alumno, sin emisión al backend de producción.
 *
 * Reutiliza el pipeline completo de visión sin duplicar lógica:
 *   MediaPipeVisionEngine → VisionPipeline → StateTransitionRules → LocalHarnessEventSink
 *
 * RESTRICCIÓN DE AISLAMIENTO (D-4):
 * Este módulo NO instancia StudentEventChannel ni ResilientStudentEventChannel.
 * NO realiza ninguna llamada HTTP ni WebSocket al backend de producción.
 * El LocalHarnessEventSink es "air-gapped" del transporte real.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Card, Button, Badge, SeverityBadge, SectionTitle } from '../ui/components';
import { STAFF_NAV } from '../ui/nav';
import { useApp } from '../lib/store';
import { SEVERIDAD_LABEL, TIPO_EVENTO_LABEL } from '../lib/api';
import { Term } from '../ui/Term';
import type { Severidad } from '../lib/types';
import { PESO_SCORE } from '../proctoring/riskWeights';
import VisionOverlay from '../ui/VisionOverlay';

// Visión — reutilizar sin duplicar (C-11, DD-17)
import { MediaPipeVisionEngine } from '../vision/MediaPipeVisionEngine';
import type { VisionEngine, FaceDetectionSignal, FaceMeshSignal, PoseSignal } from '../vision/VisionEngine';
// C-30: loader lazy del motor real (dynamic import — no entra al bundle inicial)
// C-32: importar también disposeRealEngine para el cache singleton
import { loadRealEngine, disposeRealEngine } from '../vision/harnessEngineLoader';
import type { EventSink } from '../proctoring/visionPipeline';
import { VisionPipeline } from '../proctoring/visionPipeline';
import {
  StateTransitionRules,
  type DiscreteEvent,
  type TransitionConfig,
  DEFAULT_CONFIG,
} from '../proctoring/stateTransitionRules';
import type { EventoSesion, TipoEvento } from '../lib/types';

// C-25: detectores de contexto reales (no valores fijos)
// C-32: también importar requestAndDetectExtraMonitor y ScreenPermissionResult
import {
  FocusDetector,
  FullscreenDetector,
  ClipboardDetector,
  detectExtraMonitor,
  requestAndDetectExtraMonitor,
} from '../proctoring/contextDetectors';
import type { ScreenPermissionResult } from '../proctoring/contextDetectors';

// C-25: catálogo canónico para el checklist de cobertura integral
import { SUSPICIOUS_ACTIVITY_CATALOG } from '../proctoring/suspiciousActivityCatalog';

// ---------------------------------------------------------------------------
// Constantes
// ---------------------------------------------------------------------------

/** Límite de entradas del log local (independiente del límite de 50 de anomaliasVivo). */
const LOG_MAX = 200;

/** FPS objetivo del bucle de frames del harness. */
const FRAME_INTERVAL_MS = 200; // ~5 fps — suficiente para diagnóstico

// ---------------------------------------------------------------------------
// Tipos locales
// ---------------------------------------------------------------------------

type HarnessState = 'idle' | 'initializing' | 'running' | 'stopped';

/**
 * C-30: estado del motor de visión en el harness.
 * - simulated: estado inicial, motor stub (C-29)
 * - loading: se está cargando el motor real MediaPipe
 * - real-active: motor real inicializado y procesando frames
 * - load-error: init() falló (WebGL ausente, modelo faltante, etc.)
 */
type EngineMode = 'simulated' | 'loading' | 'real-active' | 'load-error';

/** Señales crudas del frame actual (actualizadas por cada frame). */
interface RawSignals {
  faceDetection: FaceDetectionSignal | null;
  faceMesh: FaceMeshSignal | null;
  poseAvailable: boolean;
  /** C-30: señal de pose para el overlay del canvas. */
  poseSignal?: PoseSignal | null;
  frameTs: number;
}

/**
 * C-25: señales de entorno de navegador en vivo (actualizadas por detectores reales).
 * null = no determinable (API ausente/denegada).
 */
interface EnvSignals {
  focusLost: boolean;
  tabChanged: boolean;
  fullscreenExited: boolean;
  clipboardAction: 'copy' | 'paste' | null;
  /** null = API no disponible o denegada (no determinable). */
  extraMonitor: boolean | null;
}

/** Entrada del log de eventos del harness con estado del sink. */
interface HarnessLogEntry {
  id: string;
  event: DiscreteEvent;
  /** Estado del sink tras el sendEvent. */
  sinkStatus: 'ok' | 'error';
  sinkError?: string;
  /** true si el evento fue empujado a store.anomaliasVivo. */
  inStore: boolean;
  /** Timestamp absoluto de cuando se registró en el log. */
  loggedAt: number;
  /** true si el store estaba lleno (50) al llegar este evento. */
  storeOverflow: boolean;
}

// ---------------------------------------------------------------------------
// LocalHarnessEventSink — implementa EventSink sin StudentEventChannel
// ---------------------------------------------------------------------------

/** Tipo del callback de notificación del LocalHarnessEventSink. */
type SinkEventCallback = (
  rawEvent: { id: string; tipo: string; severidad: string; payload?: Record<string, unknown> },
  sinkStatus: 'ok' | 'error',
  sinkError?: string,
) => void;

/**
 * RESTRICCIÓN DE AISLAMIENTO (D-4, C-23):
 * Este sink implementa la interfaz EventSink del pipeline de visión (visionPipeline.ts)
 * acumulando eventos en memoria local y empujando al store Zustand.
 *
 * NO instancia StudentEventChannel ni ResilientStudentEventChannel.
 * NO realiza ninguna llamada HTTP ni WebSocket al backend de producción.
 * Es "air-gapped" del transporte real: puro diagnóstico local.
 */
class LocalHarnessEventSink implements EventSink {
  constructor(private readonly onEvent: SinkEventCallback) {}

  async sendEvent(args: {
    id: string;
    tipo: string;
    severidad: string;
    payload?: Record<string, unknown>;
  }): Promise<void> {
    // Simula el procesamiento del sink (sin red, sin persistencia).
    // En producción este sería el StudentEventChannel; aquí es solo local.
    try {
      // Notifica al componente para que registre el evento en el log.
      this.onEvent(args, 'ok', undefined);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      this.onEvent(args, 'error', msg);
    }
  }
}

// ---------------------------------------------------------------------------
// Validación de TransitionConfig
// ---------------------------------------------------------------------------

type ConfigErrors = Partial<Record<keyof TransitionConfig, string>>;

function validateConfig(cfg: TransitionConfig): ConfigErrors {
  const errors: ConfigErrors = {};
  const positiveFields: Array<keyof TransitionConfig> = [
    'face_absent_ms',
    'multiple_faces_frames',
    'gaze_deviation_threshold',
    'gaze_sustained_ms',
    'gaze_fixation_tolerance',
  ];
  for (const field of positiveFields) {
    const v = cfg[field];
    if (typeof v !== 'number' || isNaN(v)) {
      errors[field] = 'Debe ser un número válido';
    } else if (v <= 0) {
      errors[field] = 'Debe ser mayor a 0';
    }
  }
  return errors;
}

// ---------------------------------------------------------------------------
// Helpers de presentación
// ---------------------------------------------------------------------------

function formatRelativeTs(eventTs: number, sessionStart: number): string {
  const diff = Math.max(0, eventTs - sessionStart);
  const s = Math.floor(diff / 1000);
  const ms = diff % 1000;
  return `+${s}.${String(ms).padStart(3, '0')}s`;
}

const SEVERITY_ORDER: Severidad[] = ['baseline', 'baja', 'media', 'alta', 'critica'];

const SEVERITY_BADGE_COLORS: Record<Severidad, string> = {
  baseline: 'bg-surface-container-high text-on-surface-variant',
  baja: 'bg-success-container text-success',
  media: 'bg-warning-container text-warning',
  alta: 'bg-error-container text-on-error-container',
  critica: 'bg-error text-on-error',
};

// ---------------------------------------------------------------------------
// C-33: Helpers de color del gauge de riesgo
// ---------------------------------------------------------------------------

/**
 * Devuelve la clase Tailwind de fondo para la barra de progreso del gauge.
 * - score >= threshold → rojo (bg-error)
 * - score >= threshold * 0.7 → amarillo (bg-warning)
 * - por defecto → verde (bg-success)
 */
function gaugeColor(score: number, threshold: number): string {
  if (score >= threshold) return 'bg-error';
  if (score >= threshold * 0.7) return 'bg-warning';
  return 'bg-success';
}

/**
 * Devuelve la clase Tailwind de color de texto para el porcentaje del gauge.
 */
function gaugeTextColor(score: number, threshold: number): string {
  if (score >= threshold) return 'text-error';
  if (score >= threshold * 0.7) return 'text-warning';
  return 'text-success';
}

// ---------------------------------------------------------------------------
// Componente principal
// ---------------------------------------------------------------------------

export default function AdminDetectionHarness() {
  // ------ Store ------
  const anomaliasVivo = useApp((s) => s.anomaliasVivo);
  const pushAnomalia = useApp((s) => s.pushAnomalia);

  // ------ Estado del harness ------
  const [harnessState, setHarnessState] = useState<HarnessState>('idle');
  const [sessionStart, setSessionStart] = useState<number>(0);
  const [elapsed, setElapsed] = useState(0); // segundos desde inicio (para "Sin eventos aún")

  // ------ C-33: Medidor de riesgo ------
  const [harnessScore, setHarnessScore] = useState(0);
  const [riskThreshold, setRiskThreshold] = useState(60);

  // ------ C-30: Estado del motor de visión ------
  const [engineMode, setEngineMode] = useState<EngineMode>('simulated');
  const [engineError, setEngineError] = useState<string | null>(null);
  // C-32 Task 3.3: true si el motor nunca fue cacheado en esta sesión de página
  // (para mostrar el subtítulo "primera vez" solo en la primera carga).
  const [isFirstEngineLoad, setIsFirstEngineLoad] = useState(true);

  // ------ C-30: Toggles del overlay ------
  const [showPose, setShowPose] = useState(false);
  const [showFullMesh, setShowFullMesh] = useState(false);

  // ------ Señales crudas ------
  const [rawSignals, setRawSignals] = useState<RawSignals>({
    faceDetection: null,
    faceMesh: null,
    poseAvailable: false,
    frameTs: 0,
  });

  // ------ C-25: Señales de entorno (detectores reales) ------
  const [envSignals, setEnvSignals] = useState<EnvSignals>({
    focusLost: false,
    tabChanged: false,
    fullscreenExited: false,
    clipboardAction: null,
    extraMonitor: null,
  });
  // Refs para consumir en el loop de frames (evita stale closure)
  const envFocusLostRef = useRef(false);
  const envTabChangedRef = useRef(false);
  const envFullscreenExitedRef = useRef(false);
  const envClipboardRef = useRef<'copy' | 'paste' | null>(null);
  const envExtraMonitorRef = useRef<boolean | null>(null);

  // ------ Log de eventos ------
  const [logEntries, setLogEntries] = useState<HarnessLogEntry[]>([]);
  const [logTruncated, setLogTruncated] = useState(false);
  const logSeqRef = useRef(0);

  // ------ C-25: Checklist de cobertura integral ------
  // Mapea tipo → { capturedAt: timestamp, clipMonitorNA: bool }
  type CoverageEntry = { capturedAt: number; severidad: string };
  const [coverage, setCoverage] = useState<Partial<Record<string, CoverageEntry>>>({});
  // C-32 Task 6.1: estado del permiso de monitores (reemplaza monitorApiUnavailable)
  // Inicializado según soporte del navegador al montar
  const [monitorPermission, setMonitorPermission] = useState<
    'idle' | 'requesting' | 'granted' | 'denied' | 'unsupported'
  >(typeof window !== 'undefined' && 'getScreenDetails' in window ? 'idle' : 'unsupported');

  // ------ Filtros y UI ------
  const [severityFilter, setSeverityFilter] = useState<Set<Severidad>>(new Set(SEVERITY_ORDER));
  const [expandedPayloads, setExpandedPayloads] = useState<Set<string>>(new Set());

  // ------ Config de umbrales ------
  const [config, setConfig] = useState<TransitionConfig>({ ...DEFAULT_CONFIG });
  const [configDraft, setConfigDraft] = useState<TransitionConfig>({ ...DEFAULT_CONFIG });
  const [configErrors, setConfigErrors] = useState<ConfigErrors>({});

  // ------ Toast ------
  const [toast, setToast] = useState<string | null>(null);

  // ------ Refs del motor y pipeline ------
  const engineRef = useRef<VisionEngine | null>(null);
  const pipelineRef = useRef<VisionPipeline | null>(null);
  const sinkRef = useRef<LocalHarnessEventSink | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const frameLoopRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const animFrameRef = useRef<number | null>(null);

  // Ref del estado del store para detectar overflow sin capturar en closure
  const anomaliasLengthRef = useRef(anomaliasVivo.length);
  useEffect(() => { anomaliasLengthRef.current = anomaliasVivo.length; }, [anomaliasVivo]);

  // ------ Toast helper ------
  const showToast = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3500);
  }, []);

  // ------ Elapsado para "Sin eventos aún" ------
  useEffect(() => {
    if (harnessState !== 'running') return;
    const t = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(t);
  }, [harnessState]);

  // ------ C-25: Detectores de contexto reales (se montan al iniciar, se desmontan al detener) ------
  useEffect(() => {
    if (harnessState !== 'running') return;

    // Foco de ventana + cambio de pestaña
    const fd = new FocusDetector((sig) => {
      if (sig.focus_lost !== undefined) {
        envFocusLostRef.current = sig.focus_lost;
        setEnvSignals((prev) => ({ ...prev, focusLost: sig.focus_lost! }));
      }
      if (sig.tab_changed !== undefined) {
        envTabChangedRef.current = sig.tab_changed;
        setEnvSignals((prev) => ({ ...prev, tabChanged: sig.tab_changed! }));
      }
    });
    fd.start();

    // Salida de pantalla completa
    const fsd = new FullscreenDetector((sig) => {
      if (sig.fullscreen_exited !== undefined) {
        envFullscreenExitedRef.current = sig.fullscreen_exited;
        setEnvSignals((prev) => ({ ...prev, fullscreenExited: sig.fullscreen_exited! }));
      }
    });
    fsd.start();

    // Clipboard (copy/paste sin leer contenido)
    const cd = new ClipboardDetector((sig) => {
      if (sig.clipboard_action) {
        envClipboardRef.current = sig.clipboard_action;
        setEnvSignals((prev) => ({ ...prev, clipboardAction: sig.clipboard_action! }));
        // Reset del label después de 3 s para que no quede "pegado"
        setTimeout(() => {
          envClipboardRef.current = null;
          setEnvSignals((prev) => ({ ...prev, clipboardAction: null }));
        }, 3000);
      }
    });
    cd.start();

    // C-32: el polling de monitor ya NO se inicia automáticamente aquí.
    // Solo se inicia cuando el usuario concede el permiso mediante
    // el botón "Detectar pantallas" (monitorPermission === 'granted').
    // Ver useEffect de pollMonitor abajo.

    return () => {
      fd.stop();
      fsd.stop();
      cd.stop();
      // Resetear señales al detener
      setEnvSignals({ focusLost: false, tabChanged: false, fullscreenExited: false, clipboardAction: null, extraMonitor: null });
      envFocusLostRef.current = false;
      envTabChangedRef.current = false;
      envFullscreenExitedRef.current = false;
      envClipboardRef.current = null;
      envExtraMonitorRef.current = null;
    };
  }, [harnessState]);

  // C-32 Task 6.4: polling pasivo de monitor — se activa solo cuando el permiso fue concedido
  useEffect(() => {
    if (harnessState !== 'running' || monitorPermission !== 'granted') return;

    let pollActive = true;
    const pollMonitor = async () => {
      const provider = () => (window as unknown as { getScreenDetails: () => Promise<{ screens: unknown[] }> }).getScreenDetails();
      const sig = await detectExtraMonitor(provider);
      const val = sig?.extra_monitor ?? null;
      envExtraMonitorRef.current = val;
      setEnvSignals((prev) => ({ ...prev, extraMonitor: val }));
      if (pollActive) setTimeout(pollMonitor, 5000);
    };
    pollMonitor();

    return () => { pollActive = false; };
  }, [harnessState, monitorPermission]);

  // ------ Crear sink (referencia estable, captura callback) ------
  const createSink = useCallback(
    (onEvent: SinkEventCallback) => new LocalHarnessEventSink(onEvent),
    [],
  );

  // ------ Crear pipeline con config actual ------
  const createPipeline = useCallback(
    (engine: VisionEngine, sink: EventSink, cfg: TransitionConfig) =>
      new VisionPipeline({ engine, sink, rules: new StateTransitionRules(cfg) }),
    [],
  );

  // ------ Callback que el sink llama por cada evento ------
  // Usamos ref para no recrear el sink al cambiar el estado (patrón "ref estable")
  // eslint-disable-next-line @typescript-eslint/no-empty-function
  const onSinkEvent = useRef<SinkEventCallback>(() => {});

  // Redefine onSinkEvent.current en cada render para capturar estado fresco
  onSinkEvent.current = (rawEvent, sinkStatus, sinkError) => {
    const wasAtLimit = anomaliasLengthRef.current >= 50;

    // Empujar al store (igual que el flujo del alumno)
    const ev: EventoSesion = {
      id: rawEvent.id,
      tipo: rawEvent.tipo as TipoEvento,
      severidad: rawEvent.severidad as Severidad,
      ts_backend: new Date().toISOString(),
      descripcion: rawEvent.payload ? JSON.stringify(rawEvent.payload).slice(0, 80) : '',
      tiene_evidencia: !!(rawEvent.payload?.['trigger_evidence']),
    };
    pushAnomalia(ev);

    // C-25: actualizar checklist de cobertura (primer evento de cada tipo)
    setCoverage((prev) => {
      if (prev[rawEvent.tipo]) return prev; // ya capturado
      return { ...prev, [rawEvent.tipo]: { capturedAt: Date.now(), severidad: rawEvent.severidad } };
    });

    // C-33: acumular score de riesgo diagnóstico (setter funcional — sin stale closure)
    setHarnessScore((prev) => Math.min(100, prev + (PESO_SCORE[rawEvent.severidad as Severidad] ?? 0)));

    // Registrar en log local
    const seqId = String(logSeqRef.current++);
    const entry: HarnessLogEntry = {
      id: seqId,
      event: {
        tipo: rawEvent.tipo,
        severidad: rawEvent.severidad as Severidad,
        ts_ms: Date.now(),
        payload: rawEvent.payload ?? {},
        trigger_evidence: !!(rawEvent.payload?.['trigger_evidence']),
      },
      sinkStatus,
      sinkError,
      inStore: true, // pushAnomalia fue llamado; el store hace slice(0,50)
      loggedAt: Date.now(),
      storeOverflow: wasAtLimit,
    };

    setLogEntries((prev) => {
      const next = [entry, ...prev];
      if (next.length > LOG_MAX) {
        setLogTruncated(true);
        return next.slice(0, LOG_MAX);
      }
      return next;
    });
  };

  // ------ Iniciar harness ------
  const startHarness = useCallback(async () => {
    if (harnessState !== 'idle' && harnessState !== 'stopped') return;
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
      setHarnessState('running');

      // Bucle de frames (task 2.2): setInterval a FRAME_INTERVAL_MS para captura estable
      frameLoopRef.current = setInterval(async () => {
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
      }, FRAME_INTERVAL_MS);

    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      showToast(`Error al iniciar: ${msg}`);
      setHarnessState('idle');
    }
  }, [harnessState, config, createSink, createPipeline, showToast]);

  // ------ Detener harness ------
  const stopHarness = useCallback(async () => {
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
  }, []);

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

  // ------ Cambio de config de umbrales (task 5.2) ------
  const applyConfigChange = useCallback(
    (field: keyof TransitionConfig, rawValue: string) => {
      const num = parseFloat(rawValue);
      const next: TransitionConfig = { ...configDraft, [field]: num };
      setConfigDraft(next);

      const errors = validateConfig(next);
      setConfigErrors(errors);

      if (Object.keys(errors).length === 0) {
        setConfig(next);
        // Recrear pipeline con la nueva config (motor persiste, solo reglas cambian — D-3)
        if (engineRef.current && sinkRef.current) {
          pipelineRef.current = createPipeline(engineRef.current, sinkRef.current, next);
        }
      }
    },
    [configDraft, createPipeline],
  );

  // ------ Resetear estado de reglas (task 5.3) ------
  const resetRules = useCallback(() => {
    if (engineRef.current && sinkRef.current) {
      pipelineRef.current = createPipeline(engineRef.current, sinkRef.current, config);
    }
  }, [config, createPipeline]);

  // ------ C-32 Task 6.4: handler del botón "Detectar pantallas" ------
  const handleRequestMonitorPermission = useCallback(async () => {
    setMonitorPermission('requesting');
    const result: ScreenPermissionResult = await requestAndDetectExtraMonitor();
    if (result.status === 'granted') {
      // Actualizar señal inmediatamente con el resultado obtenido
      const val = result.extra_monitor;
      envExtraMonitorRef.current = val;
      setEnvSignals((prev) => ({ ...prev, extraMonitor: val }));
      // Setear estado 'granted' → el useEffect del polling pasivo tomará el relevo
      setMonitorPermission('granted');
    } else if (result.status === 'denied') {
      setMonitorPermission('denied');
    } else {
      // unsupported (no debería ocurrir si el botón solo aparece con 'idle')
      setMonitorPermission('unsupported');
    }
  }, []);

  // ------ Filtro por severidad (task 8.1) ------
  const toggleSeverityFilter = useCallback((sev: Severidad) => {
    setSeverityFilter((prev) => {
      const next = new Set(prev);
      if (next.has(sev)) { next.delete(sev); } else { next.add(sev); }
      return next;
    });
  }, []);

  const showAllSeverities = useCallback(() => {
    setSeverityFilter(new Set(SEVERITY_ORDER));
  }, []);

  // ------ Exportar log (task 8.2) ------
  const exportLog = useCallback(() => {
    const events = logEntries.map((e) => e.event);
    if (events.length === 0) {
      showToast('El log está vacío — no hay eventos para exportar.');
    }
    const data = {
      session_start_ts: new Date(sessionStart).toISOString(),
      config,
      events,
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `detection-harness-log-${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [logEntries, sessionStart, config, showToast]);

  // ------ Entries filtradas ------
  const filteredEntries = logEntries.filter((e) => severityFilter.has(e.event.severidad as Severidad));
  const isFilterActive = severityFilter.size !== SEVERITY_ORDER.length;

  // ------ Estado del panel de propósito (task 4.4) ------
  const [propositoPanelOpen, setPropositoPanelOpen] = useState(false);

  // ------ Render ------
  return (
    <StaffShell nav={STAFF_NAV} title="Test de detección">
      <div className="space-y-lg animate-in fade-in duration-300">

        {/* ================================================================
            C-30: BANNER CONDICIONAL DEL MOTOR — 4 estados (D-5, harness-legibility-layer)
        ================================================================ */}
        {/* Estado 'simulated' (idle): sin banner — al iniciar la cámara se activa el motor real (MediaPipe). */}
        {/* C-32 Tasks 3.1–3.4: spinner amigable, sin jerga técnica */}
        {engineMode === 'loading' && (
          <div className="flex items-start gap-sm p-md rounded-xl bg-primary-container border-2 border-primary/30 text-on-primary-container" role="status" aria-live="polite">
            <Icon name="progress_activity" className="text-[22px] shrink-0 mt-px text-primary animate-spin" />
            <div className="min-w-0">
              <p className="font-bold text-label-md">Preparando la cámara…</p>
              {/* Task 3.3: subtítulo solo en la primera carga */}
              {isFirstEngineLoad && (
                <p className="text-label-sm mt-base">
                  Esto puede tardar unos segundos la primera vez.
                </p>
              )}
            </div>
          </div>
        )}
        {engineMode === 'real-active' && (
          <div className="flex items-start gap-sm p-md rounded-xl bg-success-container border-2 border-success/40 text-on-primary-container" role="status" aria-live="polite">
            <Icon name="sensors" className="text-[22px] shrink-0 mt-px text-success" fill />
            <div className="min-w-0">
              <p className="font-bold text-label-md text-success">VISIÓN REAL (MediaPipe)</p>
              <p className="text-label-sm mt-base text-on-surface-variant">
                Motor MediaPipe real activo —{' '}
                <strong>FaceDetector + FaceLandmarker + PoseLandmarker</strong> procesando frames reales de la cámara.
              </p>
            </div>
          </div>
        )}
        {engineMode === 'load-error' && (
          <div className="flex items-start gap-sm p-md rounded-xl bg-error-container border-2 border-error/50 text-on-error-container" role="alert" aria-live="assertive">
            <Icon name="error" className="text-[22px] shrink-0 mt-px text-error" fill />
            <div className="min-w-0 flex-1">
              <p className="font-bold text-label-md">ERROR AL CARGAR EL MOTOR MEDIAPIPE</p>
              <p className="text-label-sm mt-base font-mono break-all">{engineError}</p>
              <p className="text-label-sm mt-sm">
                Las señales de visión siguen siendo del stub. Verificá que ejecutaste{' '}
                <code className="bg-error/10 px-base rounded font-mono text-[11px]">scripts/download-mediapipe-models.sh</code>{' '}
                (o <code className="bg-error/10 px-base rounded font-mono text-[11px]">.ps1</code> en Windows) y que WebGL está habilitado.
              </p>
              {/* C-32 Task 2.3: botón Reintentar llama disposeRealEngine() antes de re-invocar loadRealEngine() */}
              {harnessState === 'running' && (
                <button
                  type="button"
                  className="mt-sm inline-flex items-center gap-base px-sm py-base rounded-lg bg-error text-on-error text-label-sm font-semibold hover:opacity-90 transition-opacity"
                  onClick={async () => {
                    setEngineMode('loading');
                    setEngineError(null);
                    await disposeRealEngine();
                    try {
                      const engine = await loadRealEngine();
                      engineRef.current = engine;
                      if (sinkRef.current) {
                        pipelineRef.current = createPipeline(engine, sinkRef.current, config);
                      }
                      setEngineMode('real-active');
                    } catch (err) {
                      const msg = err instanceof Error ? err.message : String(err);
                      setEngineMode('load-error');
                      setEngineError(msg);
                    }
                  }}
                >
                  <Icon name="refresh" className="text-[16px]" />
                  Reintentar
                </button>
              )}
            </div>
          </div>
        )}

        {/* ================================================================
            PANEL DE PROPÓSITO — colapsable (DD-29-04, tasks 4.1–4.4)
        ================================================================ */}
        <div className="rounded-xl border border-outline-variant/60 bg-surface-container-lowest overflow-hidden">
          <button
            type="button"
            onClick={() => setPropositoPanelOpen((v) => !v)}
            className="w-full flex items-center justify-between gap-sm px-md py-sm text-left hover:bg-surface-container-low transition-colors"
            aria-expanded={propositoPanelOpen}
          >
            <div className="flex items-center gap-sm">
              <Icon name="help_outline" className="text-primary text-[20px] shrink-0" />
              <span className="font-semibold text-label-md text-on-surface">¿Para qué sirve esta prueba?</span>
            </div>
            <Icon name={propositoPanelOpen ? 'expand_less' : 'expand_more'} className="text-on-surface-variant text-[20px] shrink-0" />
          </button>
          {propositoPanelOpen && (
            <div className="px-md pb-md pt-sm space-y-sm border-t border-outline-variant/40 text-label-sm text-on-surface-variant">
              <p>
                Esta herramienta verifica que el sistema detecta señales correctamente antes de un examen real.
                Al iniciar la cámara, el motor de visión (MediaPipe) procesa los frames en vivo: rostros, mirada y
                postura. Las señales del navegador (pestaña, pantalla completa, portapapeles) también son reales.
              </p>
              <div>
                <p className="font-semibold text-on-surface mb-base">Acciones sugeridas para probar:</p>
                <ul className="list-disc list-inside space-y-base ml-sm">
                  <li>Moverse frente a la cámara o alejarse</li>
                  <li>Tapar la cámara con la mano</li>
                  <li>Cambiar de pestaña o abrir otra aplicación</li>
                  <li>Copiar o pegar texto en cualquier campo</li>
                  <li>Salir de la vista de pantalla completa (si aplica)</li>
                </ul>
              </div>
              <div className="flex items-start gap-base p-sm rounded-lg bg-surface-container border border-outline-variant/40">
                <Icon name="info" className="text-[16px] shrink-0 mt-px text-primary" fill />
                <span>
                  <strong className="text-on-surface">Señales de visión</strong> (rostros, <Term termKey="gaze_vector">mirada</Term>, <Term termKey="pose_keypoints">cuerpo</Term>): del motor MediaPipe procesando la cámara en vivo. &nbsp;
                  <strong className="text-on-surface">Señales de navegador</strong> (pestaña, pantalla completa, portapapeles): <em>reales</em>.
                </span>
              </div>
            </div>
          )}
        </div>

        {/* ================================================================
            HEADER DIAGNÓSTICO — badge prominente (task 2.1 / D-4)
        ================================================================ */}
        {/* C-30 / C-29: Advertencia de herramienta diagnóstica siempre visible (admin-detection-test-harness spec) */}
        <div className="flex items-center gap-base p-sm rounded-lg bg-surface-container border border-outline-variant/40 text-label-sm text-on-surface-variant">
          <Icon name="admin_panel_settings" className="text-[16px] shrink-0 text-primary" fill />
          <span>
            <strong className="text-on-surface">Esta es una herramienta diagnóstica admin.</strong>{' '}
            No genera evidencia de examen ni emite eventos al backend de producción.
          </span>
        </div>

        <div className="flex items-center justify-between flex-wrap gap-md">
          <div className="flex items-center gap-sm">
            <div className="inline-flex items-center gap-sm px-md py-sm rounded-xl bg-error-container text-on-error-container font-bold text-label-md border border-error/30">
              <Icon name="bug_report" className="text-[20px]" fill />
              MODO DIAGNÓSTICO — sin examen real
            </div>
          </div>
          <div className="flex items-center gap-sm">
            {harnessState === 'running' && (
              <span className="inline-flex items-center gap-base text-label-sm text-success bg-success-container px-sm py-base rounded-full font-semibold">
                <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
                Cámara activa
              </span>
            )}
            {(harnessState === 'idle' || harnessState === 'stopped') && (
              <Button icon="videocam" onClick={startHarness}>Iniciar cámara</Button>
            )}
            {harnessState === 'initializing' && (
              <Button icon="hourglass_empty" disabled>Inicializando…</Button>
            )}
            {harnessState === 'running' && (
              <Button variant="danger" icon="stop_circle" onClick={stopHarness}>Detener</Button>
            )}
          </div>
        </div>

        {/* ================================================================
            GRID PRINCIPAL
        ================================================================ */}
        <div className="grid lg:grid-cols-3 gap-lg">

          {/* ---- Columna izquierda: cámara + señales crudas + config ---- */}
          <div className="space-y-lg">

            {/* Cámara + VisionOverlay (C-30: canvas superpuesto) */}
            <Card padded={false} className="overflow-hidden">
              <div className="relative aspect-video bg-inverse-surface" style={{ position: 'relative' }}>
                <video ref={videoRef} muted playsInline className="w-full h-full object-cover" />
                {/* C-30: canvas overlay — solo visible cuando el motor real está activo */}
                {engineMode === 'real-active' && (
                  <VisionOverlay
                    rawSignals={rawSignals.faceDetection ? rawSignals : null}
                    videoRef={videoRef}
                    showFullMesh={showFullMesh}
                    showPose={showPose}
                  />
                )}
                {harnessState === 'idle' || harnessState === 'stopped' ? (
                  <div className="absolute inset-0 flex flex-col items-center justify-center text-on-surface-variant gap-sm">
                    <Icon name="videocam_off" className="text-[40px]" />
                    <span className="text-label-sm">Cámara inactiva</span>
                  </div>
                ) : null}
                {harnessState === 'initializing' && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center text-on-surface-variant gap-sm">
                    <Icon name="hourglass_empty" className="text-[40px] animate-spin" />
                    <span className="text-label-sm">Inicializando motor…</span>
                  </div>
                )}
              </div>
            </Card>

            {/* C-30: Toggles del overlay — visibles cuando el motor real está activo */}
            {engineMode === 'real-active' && (
              <Card className="space-y-sm">
                <p className="text-label-sm font-semibold text-on-surface">Overlay de visión</p>
                <div className="flex items-center gap-md flex-wrap">
                  <label className="flex items-center gap-sm cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={showPose}
                      onChange={(e) => setShowPose(e.target.checked)}
                      className="w-4 h-4 accent-primary rounded"
                    />
                    <span className="text-label-sm text-on-surface">
                      <Icon name="accessibility_new" className="text-[14px] inline mr-base" />
                      Pose (keypoints corporales)
                    </span>
                  </label>
                  <label className="flex items-center gap-sm cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={showFullMesh}
                      onChange={(e) => setShowFullMesh(e.target.checked)}
                      className="w-4 h-4 accent-primary rounded"
                    />
                    <span className="text-label-sm text-on-surface">
                      <Icon name="face" className="text-[14px] inline mr-base" />
                      Mesh completo (468 pts)
                    </span>
                  </label>
                </div>
              </Card>
            )}

            {/* C-30: Panel de señales de visión — interpretación en lenguaje claro (DD-29-03, tasks 5.1–5.7) */}
            <Card className="space-y-md">
              <div className="flex items-start justify-between gap-sm flex-wrap">
                <SectionTitle sub={engineMode === 'real-active' ? 'Valores reales del motor MediaPipe' : 'Iniciá la cámara para ver valores reales'}>
                  Señales de visión
                </SectionTitle>
                {/* C-30: badge REAL / SIM */}
                {engineMode === 'real-active' ? (
                  <span className="inline-flex items-center gap-base px-sm py-base rounded-full bg-success-container text-success text-label-sm font-bold border border-success/30 shrink-0">
                    <Icon name="sensors" className="text-[14px]" />
                    REAL
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-base px-sm py-base rounded-full bg-surface-container text-on-surface-variant text-label-sm font-bold border border-outline-variant/40 shrink-0">
                    <Icon name="videocam_off" className="text-[14px]" />
                    EN ESPERA
                  </span>
                )}
              </div>

              {rawSignals.faceDetection === null ? (
                <div className="text-center py-md text-on-surface-variant space-y-base">
                  <Icon name="face" className="text-[32px]" />
                  <p className="text-label-sm">Sin datos — inicia la cámara para ver señales.</p>
                </div>
              ) : (
                <div className="space-y-sm">
                  {/* ---- Tarjetas de interpretación en lenguaje claro (tasks 5.2–5.4) ---- */}
                  {/* Tarjeta: Rostros */}
                  <div className={`flex items-center gap-sm p-sm rounded-xl border ${
                    rawSignals.faceDetection.face_count === 0
                      ? 'bg-warning-container/40 border-warning/30'
                      : rawSignals.faceDetection.face_count >= 2
                      ? 'bg-error-container/40 border-error/30'
                      : 'bg-success-container/40 border-success/30'
                  }`}>
                    <Icon
                      name={rawSignals.faceDetection.face_count === 1 ? 'person' : rawSignals.faceDetection.face_count === 0 ? 'person_off' : 'group'}
                      className={`text-[20px] shrink-0 ${
                        rawSignals.faceDetection.face_count === 1 ? 'text-success'
                        : rawSignals.faceDetection.face_count === 0 ? 'text-warning'
                        : 'text-error'
                      }`}
                      fill
                    />
                    <span className="text-label-md font-semibold text-on-surface">
                      {rawSignals.faceDetection.face_count === 1
                        ? 'Se detectó 1 persona frente a la cámara'
                        : rawSignals.faceDetection.face_count === 0
                        ? 'No se detectó ninguna persona'
                        : `Se detectaron ${rawSignals.faceDetection.face_count} personas`}
                    </span>
                    <span className={`ml-auto text-[10px] uppercase font-bold opacity-80 ${engineMode === 'real-active' ? 'text-success' : 'text-warning'}`}>{engineMode === 'real-active' ? '[REAL]' : '[SIM]'}</span>
                  </div>

                  {/* Tarjeta: Mirada (task 5.3) */}
                  {rawSignals.faceMesh ? (() => {
                    const gazeOk = Math.abs(rawSignals.faceMesh.gaze.x) < 0.15 && Math.abs(rawSignals.faceMesh.gaze.y) < 0.15;
                    return (
                      <div className={`flex items-center gap-sm p-sm rounded-xl border ${
                        gazeOk ? 'bg-success-container/40 border-success/30' : 'bg-warning-container/40 border-warning/30'
                      }`}>
                        <Icon name={gazeOk ? 'visibility' : 'remove_red_eye'} className={`text-[20px] shrink-0 ${gazeOk ? 'text-success' : 'text-warning'}`} fill />
                        <span className="text-label-md font-semibold text-on-surface">
                          {gazeOk ? 'Mirando hacia el frente' : 'Mirando hacia un lado'}
                        </span>
                        <span className={`ml-auto text-[10px] uppercase font-bold opacity-80 ${engineMode === 'real-active' ? 'text-success' : 'text-warning'}`}>{engineMode === 'real-active' ? '[REAL]' : '[SIM]'}</span>
                      </div>
                    );
                  })() : rawSignals.faceDetection.face_count === 0 ? (
                    <div className="flex items-center gap-sm p-sm rounded-xl border bg-surface-container-low border-outline-variant/40">
                      <Icon name="visibility_off" className="text-[20px] text-on-surface-variant shrink-0" />
                      <span className="text-label-sm text-on-surface-variant">Mirada: sin rostro detectado</span>
                    </div>
                  ) : null}

                  {/* Tarjeta: Cuerpo (task 5.4) */}
                  <div className={`flex items-center gap-sm p-sm rounded-xl border ${
                    rawSignals.poseAvailable ? 'bg-success-container/40 border-success/30' : 'bg-surface-container-low border-outline-variant/40'
                  }`}>
                    <Icon
                      name={rawSignals.poseAvailable ? 'accessibility_new' : 'do_not_disturb'}
                      className={`text-[20px] shrink-0 ${rawSignals.poseAvailable ? 'text-success' : 'text-on-surface-variant'}`}
                      fill={rawSignals.poseAvailable}
                    />
                    <span className="text-label-md font-semibold text-on-surface">
                      {rawSignals.poseAvailable ? 'Cuerpo presente' : 'Cuerpo no detectado'}
                    </span>
                    <span className={`ml-auto text-[10px] uppercase font-bold opacity-80 ${engineMode === 'real-active' ? 'text-success' : 'text-warning'}`}>{engineMode === 'real-active' ? '[REAL]' : '[SIM]'}</span>
                  </div>

                  {/* ---- Accordion de datos técnicos crudos (DD-29-02, tasks 5.5–5.7) ---- */}
                  <details open={harnessState === 'running' && rawSignals.faceDetection.face_count !== 1 ? true : undefined}>
                    <summary className="cursor-pointer select-none text-label-sm text-on-surface-variant hover:text-primary flex items-center gap-base py-base">
                      <Icon name="expand_more" className="text-[16px]" />
                      Ver detalle técnico (coordenadas)
                    </summary>
                    <div className="space-y-sm mt-sm">
                      {/* Bounding boxes */}
                      {rawSignals.faceDetection.faces.length > 0 ? (
                        <div>
                          <p className="text-label-sm text-on-surface-variant mb-base font-semibold uppercase tracking-wide">
                            <Term termKey="bounding_box">Bounding boxes</Term>
                          </p>
                          <div className="space-y-base">
                            {rawSignals.faceDetection.faces.map((face, i) => (
                              <div key={i} className={`p-sm rounded-lg bg-surface-container-low border text-label-sm font-mono space-y-base ${
                                rawSignals.faceDetection!.face_count >= 2 ? 'border-error/40' : 'border-outline-variant/40'
                              }`}>
                                <div className="flex items-center justify-between">
                                  <span className="text-on-surface-variant text-[10px] uppercase">Rostro {i + 1}</span>
                                  <span className="text-success font-semibold">{(face.confidence * 100).toFixed(1)}% conf.</span>
                                </div>
                                <div className="grid grid-cols-2 gap-base">
                                  <span><span className="text-on-surface-variant">x:</span> {face.x.toFixed(3)}</span>
                                  <span><span className="text-on-surface-variant">y:</span> {face.y.toFixed(3)}</span>
                                  <span><span className="text-on-surface-variant">w:</span> {face.width.toFixed(3)}</span>
                                  <span><span className="text-on-surface-variant">h:</span> {face.height.toFixed(3)}</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null}

                      {/* Gaze numérico */}
                      {rawSignals.faceMesh ? (
                        <div className="p-sm rounded-lg bg-surface-container-low border border-outline-variant/40 text-label-sm font-mono space-y-base">
                          <p className="text-on-surface-variant text-[10px] uppercase font-semibold tracking-wide">
                            <Term termKey="gaze_vector">Vector gaze</Term>
                          </p>
                          <div className="grid grid-cols-2 gap-base">
                            <span><span className="text-on-surface-variant">x:</span> {rawSignals.faceMesh.gaze.x.toFixed(4)}</span>
                            <span><span className="text-on-surface-variant">y:</span> {rawSignals.faceMesh.gaze.y.toFixed(4)}</span>
                          </div>
                        </div>
                      ) : rawSignals.faceDetection.face_count === 0 ? (
                        <div className="p-sm rounded-lg bg-surface-container-low border border-outline-variant/40 text-label-sm text-on-surface-variant">
                          Gaze: sin rostro detectado
                        </div>
                      ) : null}

                      {/* Pose keypoints */}
                      <div className="p-sm rounded-lg bg-surface-container-low border border-outline-variant/40 text-label-sm flex items-center gap-sm">
                        <Icon name={rawSignals.poseAvailable ? 'accessibility_new' : 'do_not_disturb'} className={`text-[18px] ${rawSignals.poseAvailable ? 'text-success' : 'text-on-surface-variant'}`} />
                        <span className="text-on-surface">
                          <Term termKey="pose_keypoints">Pose keypoints</Term>: {rawSignals.poseAvailable ? 'disponibles' : engineMode === 'real-active' ? 'no detectados en este frame' : 'no disponibles (iniciá la cámara)'}
                        </span>
                      </div>
                    </div>
                  </details>
                </div>
              )}
            </Card>

            {/* C-25: Panel de señales de entorno en vivo (tasks 6.1, 6.2) */}
            <Card className="space-y-md">
              <div className="flex items-start justify-between gap-sm flex-wrap">
                <SectionTitle sub="Detectores de contexto reales del navegador">Señales de entorno</SectionTitle>
                {/* task 6.2: badge "Señal REAL" */}
                <span className="inline-flex items-center gap-base px-sm py-base rounded-full bg-success-container text-success text-label-sm font-bold border border-success/30 shrink-0">
                  <Icon name="sensors" className="text-[14px]" />
                  Señal REAL
                </span>
              </div>

              {harnessState !== 'running' ? (
                <div className="text-center py-md text-on-surface-variant space-y-base">
                  <Icon name="sensors_off" className="text-[32px]" />
                  <p className="text-label-sm">Inicia la cámara para activar los detectores de entorno.</p>
                </div>
              ) : (
                <div className="space-y-base">
                  {/* Foco de ventana */}
                  <div className={`flex items-start justify-between p-sm rounded-xl border text-label-sm ${
                    envSignals.focusLost
                      ? 'bg-warning-container/60 border-warning/40 text-warning'
                      : 'bg-surface-container-low border-outline-variant/40 text-on-surface-variant'
                  }`}>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-base">
                        <Icon name={envSignals.focusLost ? 'visibility_off' : 'visibility'} className="text-[16px]" />
                        <span className="font-semibold">Foco de ventana</span>
                      </div>
                      <p className="text-[11px] mt-px ml-[22px] opacity-80">Detecta si el alumno abandonó la ventana del examen.</p>
                    </div>
                    <span className="shrink-0 ml-sm">{envSignals.focusLost ? 'PERDIDO' : 'activo'}</span>
                  </div>

                  {/* Cambio de pestaña */}
                  <div className={`flex items-start justify-between p-sm rounded-xl border text-label-sm ${
                    envSignals.tabChanged
                      ? 'bg-warning-container/60 border-warning/40 text-warning'
                      : 'bg-surface-container-low border-outline-variant/40 text-on-surface-variant'
                  }`}>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-base">
                        <Icon name="tab" className="text-[16px]" />
                        <span className="font-semibold">Cambio de pestaña</span>
                      </div>
                      <p className="text-[11px] mt-px ml-[22px] opacity-80">Detecta si el alumno abrió otro sitio o aplicación.</p>
                    </div>
                    <span className="shrink-0 ml-sm">{envSignals.tabChanged ? 'OCULTA' : 'visible'}</span>
                  </div>

                  {/* Pantalla completa */}
                  <div className={`flex items-start justify-between p-sm rounded-xl border text-label-sm ${
                    envSignals.fullscreenExited
                      ? 'bg-warning-container/60 border-warning/40 text-warning'
                      : 'bg-surface-container-low border-outline-variant/40 text-on-surface-variant'
                  }`}>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-base">
                        <Icon name={envSignals.fullscreenExited ? 'fullscreen_exit' : 'fullscreen'} className="text-[16px]" />
                        <span className="font-semibold">Pantalla completa</span>
                      </div>
                      <p className="text-[11px] mt-px ml-[22px] opacity-80">Detecta si el alumno salió de la vista de examen completa.</p>
                    </div>
                    <span className="shrink-0 ml-sm">{envSignals.fullscreenExited ? 'SALIDA detectada' : 'activa o no usada'}</span>
                  </div>

                  {/* Clipboard */}
                  <div className={`flex items-start justify-between p-sm rounded-xl border text-label-sm ${
                    envSignals.clipboardAction
                      ? 'bg-error-container/60 border-error/40 text-on-error-container'
                      : 'bg-surface-container-low border-outline-variant/40 text-on-surface-variant'
                  }`}>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-base">
                        <Icon name="content_paste" className="text-[16px]" />
                        <span className="font-semibold">Portapapeles</span>
                      </div>
                      <p className="text-[11px] mt-px ml-[22px] opacity-80">Detecta si el alumno intentó copiar o pegar contenido.</p>
                    </div>
                    <span className="shrink-0 ml-sm">
                      {envSignals.clipboardAction
                        ? `DETECTADO: ${envSignals.clipboardAction.toUpperCase()}`
                        : 'sin actividad'}
                    </span>
                  </div>

                  {/* C-32 Task 6.3: tarjeta de monitores con flujo de permiso */}
                  {monitorPermission === 'unsupported' && (
                    <div className="flex items-start gap-sm p-sm rounded-xl border text-label-sm bg-surface-container-low border-outline-variant/40 text-on-surface-variant">
                      <Icon name="info" className="text-[16px] shrink-0 mt-px text-primary" fill />
                      <div className="min-w-0">
                        <span className="font-semibold block">Monitor adicional</span>
                        <p className="text-[11px] mt-px opacity-80">
                          La detección de pantallas adicionales no está disponible en este navegador.
                          Requiere Chrome o Edge sobre HTTPS.
                        </p>
                      </div>
                    </div>
                  )}

                  {monitorPermission === 'idle' && (
                    <div className="flex items-start gap-sm p-sm rounded-xl border text-label-sm bg-surface-container-low border-outline-variant/40 text-on-surface-variant">
                      <Icon name="monitor" className="text-[16px] shrink-0 mt-px" />
                      <div className="min-w-0 flex-1">
                        <span className="font-semibold block">Monitor adicional</span>
                        <p className="text-[11px] mt-px opacity-80">
                          Para detectar si hay más de un monitor conectado, el navegador necesita tu permiso.
                        </p>
                        <button
                          type="button"
                          onClick={handleRequestMonitorPermission}
                          className="mt-sm inline-flex items-center gap-base px-sm py-base rounded-lg bg-primary text-on-primary text-label-sm font-semibold hover:opacity-90 transition-opacity"
                        >
                          <Icon name="monitor" className="text-[14px]" />
                          Detectar pantallas
                        </button>
                      </div>
                    </div>
                  )}

                  {monitorPermission === 'requesting' && (
                    <div className="flex items-start gap-sm p-sm rounded-xl border text-label-sm bg-primary-container/40 border-primary/30 text-on-primary-container">
                      <Icon name="progress_activity" className="text-[16px] shrink-0 mt-px text-primary animate-spin" />
                      <div className="min-w-0">
                        <span className="font-semibold block">Monitor adicional</span>
                        <p className="text-[11px] mt-px opacity-80">Solicitando permiso al navegador…</p>
                        <button
                          type="button"
                          disabled
                          className="mt-sm inline-flex items-center gap-base px-sm py-base rounded-lg bg-primary/50 text-on-primary text-label-sm font-semibold opacity-60 cursor-not-allowed"
                        >
                          <Icon name="progress_activity" className="text-[14px] animate-spin" />
                          Detectar pantallas
                        </button>
                      </div>
                    </div>
                  )}

                  {monitorPermission === 'denied' && (
                    <div className="flex items-start gap-sm p-sm rounded-xl border text-label-sm bg-warning-container/40 border-warning/40 text-warning">
                      <Icon name="block" className="text-[16px] shrink-0 mt-px" />
                      <div className="min-w-0 flex-1">
                        <span className="font-semibold block">Monitor adicional</span>
                        <p className="text-[11px] mt-px opacity-80">Permiso denegado. Podés intentarlo de nuevo.</p>
                        <button
                          type="button"
                          onClick={handleRequestMonitorPermission}
                          className="mt-sm inline-flex items-center gap-base px-sm py-base rounded-lg bg-warning text-white text-label-sm font-semibold hover:opacity-90 transition-opacity"
                        >
                          <Icon name="refresh" className="text-[14px]" />
                          Reintentar
                        </button>
                      </div>
                    </div>
                  )}

                  {monitorPermission === 'granted' && (
                    <div className={`flex items-start justify-between p-sm rounded-xl border text-label-sm ${
                      envSignals.extraMonitor === true
                        ? 'bg-error-container/60 border-error/40 text-on-error-container'
                        : 'bg-surface-container-low border-outline-variant/40 text-on-surface-variant'
                    }`}>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-base">
                          <Icon name="desktop_windows" className="text-[16px]" />
                          <span className="font-semibold">Monitor adicional</span>
                        </div>
                        <p className="text-[11px] mt-px ml-[22px] opacity-80">Detecta si hay más de una pantalla conectada.</p>
                      </div>
                      <span className="shrink-0 ml-sm">
                        {envSignals.extraMonitor === true
                          ? 'MONITOR ADICIONAL detectado'
                          : envSignals.extraMonitor === false
                          ? 'solo un monitor'
                          : 'determinando…'}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </Card>

            {/* Panel de configuración de umbrales (tasks 5.1, 5.2, 5.3) */}
            <Card className="space-y-md">
              <SectionTitle sub="Cambios aplican al siguiente frame sin reiniciar el motor">
                Configuración de umbrales
              </SectionTitle>

              {/* C-32 Tasks 4.1–4.3: clearLabel como etiqueta principal; clave técnica como texto secundario */}
              {(
                [
                  {
                    field: 'face_absent_ms' as const,
                    clearLabel: 'Segundos sin rostro para alertar',
                    label: 'face_absent_ms',
                    unit: 'ms',
                    hint: 'Tiempo sin detectar un rostro antes de emitir una alerta (en milisegundos)',
                  },
                  {
                    field: 'multiple_faces_frames' as const,
                    clearLabel: 'Fotogramas con varios rostros para alertar',
                    label: 'multiple_faces_frames',
                    unit: 'frames',
                    hint: 'Cantidad de fotogramas consecutivos con más de un rostro para emitir una alerta',
                  },
                  {
                    field: 'gaze_deviation_threshold' as const,
                    clearLabel: 'Sensibilidad de mirada desviada',
                    label: 'gaze_deviation_threshold',
                    unit: '0..1',
                    hint: 'Cuán lejos del centro puede mirar el alumno antes de que se considere desviado (0 = muy sensible, 1 = tolerante)',
                  },
                  {
                    field: 'gaze_sustained_ms' as const,
                    clearLabel: 'Tiempo de mirada desviada para alertar',
                    label: 'gaze_sustained_ms',
                    unit: 'ms',
                    hint: 'Tiempo continuo mirando hacia un lado antes de emitir una alerta (en milisegundos)',
                  },
                  {
                    field: 'gaze_fixation_tolerance' as const,
                    clearLabel: 'Tolerancia de fijación de mirada',
                    label: 'gaze_fixation_tolerance',
                    unit: '0..1',
                    hint: 'Variación permitida en la dirección de la mirada para considerarla sostenida en el mismo punto',
                  },
                ] as { field: keyof TransitionConfig; clearLabel: string; label: string; unit: string; hint: string }[]
              ).map(({ field, clearLabel, unit, hint }) => (
                <div key={field} className="space-y-base">
                  <label>
                    {/* Task 4.2: nombre claro como etiqueta principal */}
                    <span className="text-label-sm font-semibold text-on-surface block">
                      {clearLabel} <span className="text-on-surface-variant font-normal">({unit})</span>
                    </span>
                  </label>
                  {/* Task 4.3: hint con redacción clara, sin jerga */}
                  <p className="text-[11px] text-on-surface-variant">{hint}</p>
                  <input
                    type="number"
                    step="any"
                    value={configDraft[field]}
                    onChange={(e) => applyConfigChange(field, e.target.value)}
                    className={`w-full px-sm py-base text-label-md rounded-xl border bg-surface-container-lowest outline-none font-mono
                      ${configErrors[field] ? 'border-error focus:border-error' : 'border-outline-variant focus:border-primary-container'}`}
                  />
                  {configErrors[field] && (
                    <p className="text-label-sm text-error">{configErrors[field]}</p>
                  )}
                </div>
              ))}

              <div className="flex gap-sm pt-sm border-t border-outline-variant/40">
                <Button
                  variant="outline"
                  icon="restart_alt"
                  onClick={resetRules}
                  className="flex-1"
                  disabled={harnessState !== 'running'}
                >
                  Resetear estado
                </Button>
                <Button
                  variant="ghost"
                  icon="undo"
                  onClick={() => {
                    setConfigDraft({ ...DEFAULT_CONFIG });
                    setConfig({ ...DEFAULT_CONFIG });
                    setConfigErrors({});
                    if (engineRef.current && sinkRef.current) {
                      pipelineRef.current = createPipeline(engineRef.current, sinkRef.current, DEFAULT_CONFIG);
                    }
                  }}
                  title="Restaurar valores por defecto"
                >
                  Default
                </Button>
              </div>
            </Card>

            {/* ================================================================
                C-33: MEDIDOR DE RIESGO DIAGNÓSTICO
                Estado local — no modifica store.scorePropio (D-1).
                Semántica L2.5: prioriza para revisión humana, NUNCA sanciona.
            ================================================================ */}
            <Card className="space-y-md">
              <SectionTitle sub="Score acumulado de esta sesión de diagnóstico">
                Medidor de riesgo
              </SectionTitle>

              {/* Gauge — barra de progreso */}
              <div className="space-y-sm">
                <div className="flex items-center justify-between gap-sm">
                  <span className="text-label-sm text-on-surface-variant">Score acumulado</span>
                  <span className={`font-headline text-headline-sm font-bold ${gaugeTextColor(harnessScore, riskThreshold)}`}>
                    {harnessScore}%
                  </span>
                </div>
                <div className="bg-surface-container-high rounded-full h-3 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${gaugeColor(harnessScore, riskThreshold)}`}
                    style={{ width: `${harnessScore}%` }}
                    role="progressbar"
                    aria-valuenow={harnessScore}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label="Score de riesgo acumulado"
                  />
                </div>
              </div>

              {/* Banner de umbral superado — semántica L2.5 explícita */}
              {harnessScore >= riskThreshold && (
                <div className="flex items-start gap-sm p-sm rounded-xl bg-error-container text-on-error-container border border-error/30" role="alert">
                  <Icon name="flag" className="text-[18px] shrink-0 mt-px text-error" fill />
                  <span className="text-label-sm font-semibold">
                    Superaría el umbral — priorizaría para revisión humana
                  </span>
                </div>
              )}

              {/* Input de umbral configurable */}
              <div className="space-y-base">
                <label>
                  <span className="text-label-sm font-semibold text-on-surface block">
                    Umbral de riesgo (%)
                  </span>
                  <span className="text-[11px] text-on-surface-variant">
                    Cuando el score supera este valor, la sesión priorizaría revisión humana.
                  </span>
                </label>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={riskThreshold}
                  onChange={(e) => {
                    const raw = parseInt(e.target.value, 10);
                    const clamped = isNaN(raw) ? 1 : Math.max(1, Math.min(100, raw));
                    setRiskThreshold(clamped);
                  }}
                  className="w-full px-sm py-base text-label-md rounded-xl border border-outline-variant bg-surface-container-lowest outline-none font-mono focus:border-primary-container"
                />
              </div>

              {/* Botón Resetear riesgo — independiente del pipeline */}
              <div className="pt-sm border-t border-outline-variant/40">
                <Button
                  variant="outline"
                  icon="restart_alt"
                  onClick={() => setHarnessScore(0)}
                  className="w-full"
                >
                  Resetear riesgo
                </Button>
              </div>
            </Card>
          </div>

          {/* ---- Columna derecha (2 cols): log de eventos + store counter ---- */}
          <div className="lg:col-span-2 space-y-lg">

            {/* Contador del store (tasks 7.1, 7.2) */}
            <Card className="flex items-center justify-between gap-md flex-wrap">
              <div className="flex items-center gap-sm">
                <div className="w-10 h-10 rounded-xl bg-primary-fixed text-primary flex items-center justify-center shrink-0">
                  <Icon name="storage" />
                </div>
                <div>
                  <p className="text-label-sm text-on-surface-variant uppercase tracking-wide">store.anomaliasVivo</p>
                  <p className="font-headline text-headline-md text-on-surface">
                    {anomaliasVivo.length} <span className="text-label-sm text-on-surface-variant font-normal">/ 50 (límite)</span>
                  </p>
                </div>
              </div>
              {anomaliasVivo.length >= 50 && (
                <Badge tone="warning" dot>Store lleno — overflow activo</Badge>
              )}
            </Card>

            {/* Log de eventos (tasks 6.1, 6.2, 6.3, 8.1, 8.2) */}
            <Card className="space-y-md">
              <div className="flex items-start justify-between gap-md flex-wrap">
                <SectionTitle sub={
                  isFilterActive
                    ? `${logEntries.length} eventos (${filteredEntries.length} visibles)`
                    : `${logEntries.length} evento${logEntries.length !== 1 ? 's' : ''}`
                }>
                  Log de eventos
                </SectionTitle>
                <div className="flex items-center gap-sm flex-wrap">
                  <Button variant="outline" icon="download" onClick={exportLog} className="h-9 px-md text-label-sm">
                    Exportar log
                  </Button>
                </div>
              </div>

              {logTruncated && (
                <div className="flex items-center gap-base p-sm rounded-lg bg-warning-container/40 border border-warning/30 text-label-sm text-warning">
                  <Icon name="warning" className="text-[16px] shrink-0" fill />
                  Log truncado a {LOG_MAX} entradas. Las entradas más antiguas fueron descartadas.
                </div>
              )}

              {/* Filtro por severidad (task 8.1) */}
              <div className="flex items-center gap-base flex-wrap">
                <span className="text-label-sm text-on-surface-variant">Filtrar:</span>
                {SEVERITY_ORDER.map((sev) => (
                  <button
                    key={sev}
                    onClick={() => toggleSeverityFilter(sev)}
                    className={`px-sm py-base rounded-full text-label-sm font-semibold border transition-all ${
                      severityFilter.has(sev)
                        ? `${SEVERITY_BADGE_COLORS[sev]} border-transparent`
                        : 'bg-surface-container text-on-surface-variant border-outline-variant/40 opacity-50'
                    }`}
                  >
                    {SEVERIDAD_LABEL[sev]}
                  </button>
                ))}
                {isFilterActive && (
                  <button
                    onClick={showAllSeverities}
                    className="text-label-sm text-primary hover:underline"
                  >
                    Mostrar todos
                  </button>
                )}
              </div>

              {/* Lista de eventos */}
              <div className="space-y-base max-h-[520px] overflow-y-auto">
                {filteredEntries.length === 0 ? (
                  <div className="text-center py-xl text-on-surface-variant space-y-sm">
                    <Icon name="check_circle" className="text-success text-[36px]" fill />
                    {/* "Sin eventos aún" si han pasado más de 10s y el harness está corriendo (task 6.3) */}
                    {harnessState === 'running' && elapsed >= 10 ? (
                      <p className="text-label-sm">Sin eventos aún — señales dentro de umbrales</p>
                    ) : (
                      <p className="text-label-sm">
                        {harnessState === 'idle' || harnessState === 'stopped'
                          ? 'Iniciá la cámara para comenzar el diagnóstico.'
                          : 'Esperando eventos…'}
                      </p>
                    )}
                  </div>
                ) : (
                  filteredEntries.map((entry) => {
                    const relTs = formatRelativeTs(entry.event.ts_ms, sessionStart);
                    const isExpanded = expandedPayloads.has(entry.id);
                    const tipo = entry.event.tipo as TipoEvento;
                    const sev = entry.event.severidad as Severidad;

                    return (
                      <div
                        key={entry.id}
                        className={`rounded-xl border p-sm space-y-base transition-all ${
                          sev === 'alta' || sev === 'critica'
                            ? 'bg-error-container/20 border-error/30'
                            : 'bg-surface-container-low border-outline-variant/40'
                        }`}
                      >
                        {/* Fila principal */}
                        <div className="flex items-start justify-between gap-sm flex-wrap">
                          <div className="flex items-center gap-sm flex-wrap">
                            <span className="text-label-md font-semibold text-on-surface">
                              {TIPO_EVENTO_LABEL[tipo] ?? tipo}
                            </span>
                            <SeverityBadge severidad={sev} />
                            {entry.event.trigger_evidence && (
                              <Badge tone="error" dot>dispara evidencia</Badge>
                            )}
                            {entry.storeOverflow && (
                              <Badge tone="warning">store: overflow, evento anterior descartado</Badge>
                            )}
                          </div>
                          <span className="text-label-sm text-on-surface-variant font-mono">{relTs}</span>
                        </div>

                        {/* Indicadores de sink e inStore */}
                        <div className="flex items-center gap-sm flex-wrap">
                          {entry.sinkStatus === 'ok' ? (
                            <span className="inline-flex items-center gap-base text-label-sm text-success">
                              <Icon name="check_circle" className="text-[14px]" fill /> emitido al sink
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-base text-label-sm text-error">
                              <Icon name="cancel" className="text-[14px]" fill /> error en sink: {entry.sinkError}
                            </span>
                          )}
                          {entry.inStore ? (
                            <span className="inline-flex items-center gap-base text-label-sm text-primary">
                              <Icon name="inventory_2" className="text-[14px]" fill /> en store
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-base text-label-sm text-on-surface-variant">
                              <Icon name="inventory_2" className="text-[14px]" /> no en store
                            </span>
                          )}
                        </div>

                        {/* Payload colapsable */}
                        {Object.keys(entry.event.payload).length > 0 && (
                          <div>
                            <button
                              onClick={() =>
                                setExpandedPayloads((prev) => {
                                  const next = new Set(prev);
                                  if (next.has(entry.id)) { next.delete(entry.id); } else { next.add(entry.id); }
                                  return next;
                                })
                              }
                              className="text-label-sm text-on-surface-variant hover:text-primary flex items-center gap-base"
                            >
                              <Icon name={isExpanded ? 'expand_less' : 'expand_more'} className="text-[16px]" />
                              payload
                            </button>
                            {isExpanded && (
                              <pre className="mt-base text-label-sm font-mono bg-surface-container rounded-lg p-sm overflow-x-auto text-on-surface-variant">
                                {JSON.stringify(entry.event.payload, null, 2)}
                              </pre>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </Card>
          </div>
        </div>

        {/* ================================================================
            C-25: CHECKLIST DE COBERTURA INTEGRAL (6.1, 6.2, 6.3, 6.4)
        ================================================================ */}
        <Card className="space-y-md">
          <div className="flex items-start justify-between gap-md flex-wrap">
            <SectionTitle sub="Ejercitá cada tipo en esta sesión para confirmar captura y registro">
              Cobertura integral de actividad sospechosa
            </SectionTitle>
            {(() => {
              // C-32 Task 6.5: monitorApiUnavailable reemplazado por monitorPermission === 'unsupported'
              const testableCatalog = SUSPICIOUS_ACTIVITY_CATALOG.filter(
                (e) => !(e.requiereApiOpcional && monitorPermission === 'unsupported'),
              );
              const captured = testableCatalog.filter((e) => coverage[e.tipo]);
              const allDone = testableCatalog.length > 0 && captured.length === testableCatalog.length;
              return allDone ? (
                <span className="inline-flex items-center gap-base px-md py-sm rounded-xl bg-success-container text-success font-bold text-label-md border border-success/30">
                  <Icon name="verified" className="text-[18px]" fill />
                  Cobertura completa
                </span>
              ) : (
                <span className="text-label-sm text-on-surface-variant font-mono">
                  {captured.length}/{testableCatalog.length} tipos cubiertos
                </span>
              );
            })()}
          </div>

          <div className="space-y-base">
            {SUSPICIOUS_ACTIVITY_CATALOG.map((entry) => {
              const cap = coverage[entry.tipo];
              // C-32 Task 6.5: reemplazado por monitorPermission === 'unsupported'
              const isUntestable = entry.requiereApiOpcional && monitorPermission === 'unsupported';
              return (
                <div
                  key={entry.tipo}
                  className={`flex items-start justify-between gap-sm p-sm rounded-xl border text-label-sm ${
                    isUntestable
                      ? 'bg-surface-container border-outline-variant/40 opacity-60'
                      : cap
                      ? 'bg-success-container/30 border-success/30'
                      : 'bg-surface-container-low border-outline-variant/40'
                  }`}
                >
                  <div className="flex items-start gap-sm">
                    <Icon
                      name={isUntestable ? 'info' : cap ? 'check_circle' : 'radio_button_unchecked'}
                      className={`text-[18px] shrink-0 mt-px ${
                        isUntestable
                          ? 'text-on-surface-variant'
                          : cap
                          ? 'text-success'
                          : 'text-on-surface-variant'
                      }`}
                      fill={!isUntestable && !!cap}
                    />
                    <div className="space-y-px">
                      <div className="flex items-center gap-sm flex-wrap">
                        <span className={`font-semibold ${cap ? 'text-on-surface' : 'text-on-surface-variant'}`}>
                          {entry.label}
                        </span>
                        <span className={`text-[10px] uppercase tracking-wide px-base py-px rounded-full font-bold ${
                          entry.categoria === 'vision'
                            ? 'bg-primary-fixed/60 text-primary'
                            : 'bg-secondary-container text-on-secondary-container'
                        }`}>
                          {entry.categoria === 'vision' ? 'Visión' : 'Navegador'}
                        </span>
                        <span className="text-[10px] text-on-surface-variant uppercase">sev: {entry.severidad}</span>
                      </div>
                      <p className="text-[11px] text-on-surface-variant">{entry.descripcion}</p>
                    </div>
                  </div>
                  <div className="shrink-0 text-right">
                    {isUntestable ? (
                      <span className="text-[10px] text-on-surface-variant italic">no testeable en este navegador</span>
                    ) : cap ? (
                      <span className="text-[10px] text-success font-semibold font-mono">
                        +{((cap.capturedAt - sessionStart) / 1000).toFixed(1)}s
                      </span>
                    ) : (
                      <span className="text-[10px] text-on-surface-variant">pendiente</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="flex items-center gap-base p-sm rounded-lg bg-surface-container border border-outline-variant/40 text-label-sm text-on-surface-variant">
            <Icon name="lock" className="text-[14px] shrink-0" fill />
            Aislamiento D-4: todos los eventos de esta sesión permanecen en el sink local. Ninguno se envía al backend de producción.
          </div>
        </Card>

        {/* ================================================================
            AVISO LEGAL L2.5
        ================================================================ */}
        <div className="bg-primary-fixed/40 rounded-xl p-sm text-label-sm text-on-primary-fixed-variant flex items-start gap-base">
          <Icon name="shield" className="text-[18px] shrink-0" fill />
          <span>
            Herramienta diagnóstica — sin examen real, sin sesión de alumno, sin sanción automática (<Term termKey="l2_5" />).
            El sistema nunca toma decisiones disciplinarias: prioriza señales para revisión humana.
            Los eventos generados aquí NO se almacenan en el backend de producción.
          </span>
        </div>
      </div>

      {/* Toast (task 8.2) */}
      {toast && (
        <div className="fixed bottom-20 left-1/2 -translate-x-1/2 z-[110] bg-inverse-surface text-inverse-on-surface px-lg py-sm rounded-xl shadow-card-lg text-label-md animate-in fade-in slide-in-from-bottom-4">
          {toast}
        </div>
      )}
    </StaffShell>
  );
}
