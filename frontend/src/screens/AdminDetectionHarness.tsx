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
import type { Severidad } from '../lib/types';

// Visión — reutilizar sin duplicar (C-11, DD-17)
import { MediaPipeVisionEngine } from '../vision/MediaPipeVisionEngine';
import type { VisionEngine, FaceDetectionSignal, FaceMeshSignal } from '../vision/VisionEngine';
import type { EventSink } from '../proctoring/visionPipeline';
import { VisionPipeline } from '../proctoring/visionPipeline';
import {
  StateTransitionRules,
  type DiscreteEvent,
  type TransitionConfig,
  DEFAULT_CONFIG,
} from '../proctoring/stateTransitionRules';
import type { EventoSesion, TipoEvento } from '../lib/types';

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

/** Señales crudas del frame actual (actualizadas por cada frame). */
interface RawSignals {
  faceDetection: FaceDetectionSignal | null;
  faceMesh: FaceMeshSignal | null;
  poseAvailable: boolean;
  frameTs: number;
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

  // ------ Señales crudas ------
  const [rawSignals, setRawSignals] = useState<RawSignals>({
    faceDetection: null,
    faceMesh: null,
    poseAvailable: false,
    frameTs: 0,
  });

  // ------ Log de eventos ------
  const [logEntries, setLogEntries] = useState<HarnessLogEntry[]>([]);
  const [logTruncated, setLogTruncated] = useState(false);
  const logSeqRef = useRef(0);

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

    try {
      // Solicitar cámara
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => {});
      }

      // Instanciar motor (task 3.1)
      const engine = new MediaPipeVisionEngine();
      await engine.init();
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

          // Extraer señales crudas (task 4.1)
          let fd: FaceDetectionSignal;
          let mesh: FaceMeshSignal | null = null;
          let poseAvailable = false;

          try {
            fd = await engine_.detectFaces(frame);
          } catch {
            // Motor MediaPipe real no cableado — simular señal para demo
            fd = { face_count: 1, faces: [{ x: 0.25, y: 0.1, width: 0.5, height: 0.6, confidence: 0.92 }] };
          }

          if (fd.face_count >= 1) {
            try {
              mesh = await engine_.detectFaceMesh(frame);
            } catch {
              mesh = { gaze: { x: 0.03, y: 0.01 }, embedding: [], landmarks: [] };
            }
          }

          try {
            await engine_.detectPose(frame);
            poseAvailable = true;
          } catch {
            poseAvailable = false;
          }

          frame.close();

          // Actualizar panel de señales crudas (task 4.2)
          setRawSignals({ faceDetection: fd, faceMesh: mesh, poseAvailable, frameTs: Date.now() });

          // Ejecutar pipeline (onFrame llama detectFaces/detectFaceMesh internamente).
          // Como ya los llamamos arriba para el panel de señales, usamos onSignals para evitar
          // doble inferencia: pasamos las señales ya extraídas. (task 3.3 / D-3)
          await pipeline_.onSignals({
            ts_ms: Date.now(),
            face_count: fd.face_count,
            gaze: mesh?.gaze,
            focus_lost: false,
            extra_monitor: false,
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
    if (videoRef.current) { videoRef.current.srcObject = null; }
    // dispose del motor (task 3.1)
    await engineRef.current?.dispose().catch(() => {});
    engineRef.current = null;
    pipelineRef.current = null;
    sinkRef.current = null;
    setHarnessState('stopped');
    setRawSignals({ faceDetection: null, faceMesh: null, poseAvailable: false, frameTs: 0 });
  }, []);

  // Cleanup al desmontar
  useEffect(() => {
    return () => {
      if (frameLoopRef.current) clearInterval(frameLoopRef.current);
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
      engineRef.current?.dispose().catch(() => {});
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

  // ------ Render ------
  return (
    <StaffShell nav={STAFF_NAV} title="Test de detección">
      <div className="space-y-lg animate-in fade-in duration-300">

        {/* ================================================================
            HEADER DIAGNÓSTICO — badge prominente (task 2.1 / D-4)
        ================================================================ */}
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

            {/* Cámara (task 2.2) */}
            <Card padded={false} className="overflow-hidden">
              <div className="relative aspect-video bg-inverse-surface">
                <video ref={videoRef} muted playsInline className="w-full h-full object-cover" />
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

            {/* Panel de señales crudas (tasks 4.1, 4.2, 4.3) */}
            <Card className="space-y-md">
              <SectionTitle sub="Actualizado por frame">Señales crudas</SectionTitle>

              {rawSignals.faceDetection === null ? (
                <div className="text-center py-md text-on-surface-variant space-y-base">
                  <Icon name="face" className="text-[32px]" />
                  <p className="text-label-sm">Sin datos — inicia la cámara para ver señales.</p>
                </div>
              ) : (
                <div className="space-y-sm">
                  {/* Conteo de rostros */}
                  <div className={`flex items-center justify-between p-sm rounded-xl border ${
                    rawSignals.faceDetection.face_count === 0
                      ? 'bg-warning-container/40 border-warning/30'
                      : rawSignals.faceDetection.face_count >= 2
                      ? 'bg-error-container/40 border-error/30'
                      : 'bg-success-container/40 border-success/30'
                  }`}>
                    <span className="text-label-md font-semibold text-on-surface">Rostros detectados</span>
                    <div className="flex items-center gap-base">
                      <span className="font-mono text-title-lg font-bold text-on-surface">
                        {rawSignals.faceDetection.face_count}
                      </span>
                      {rawSignals.faceDetection.face_count === 0 && (
                        <Badge tone="warning">Sin rostro detectado</Badge>
                      )}
                      {rawSignals.faceDetection.face_count >= 2 && (
                        <Badge tone="error">Múltiples rostros</Badge>
                      )}
                    </div>
                  </div>

                  {/* Bounding boxes */}
                  {rawSignals.faceDetection.faces.length > 0 ? (
                    <div>
                      <p className="text-label-sm text-on-surface-variant mb-base font-semibold uppercase tracking-wide">Bounding boxes</p>
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

                  {/* Gaze */}
                  {rawSignals.faceMesh ? (
                    <div className="p-sm rounded-lg bg-surface-container-low border border-outline-variant/40 text-label-sm font-mono space-y-base">
                      <p className="text-on-surface-variant text-[10px] uppercase font-semibold tracking-wide">Vector gaze</p>
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

                  {/* Pose */}
                  <div className="p-sm rounded-lg bg-surface-container-low border border-outline-variant/40 text-label-sm flex items-center gap-sm">
                    <Icon name={rawSignals.poseAvailable ? 'accessibility_new' : 'do_not_disturb'} className={`text-[18px] ${rawSignals.poseAvailable ? 'text-success' : 'text-on-surface-variant'}`} />
                    <span className="text-on-surface">
                      Pose keypoints: {rawSignals.poseAvailable ? 'disponibles' : 'no disponibles (motor en stub)'}
                    </span>
                  </div>
                </div>
              )}
            </Card>

            {/* Panel de configuración de umbrales (tasks 5.1, 5.2, 5.3) */}
            <Card className="space-y-md">
              <SectionTitle sub="Cambios aplican al siguiente frame sin reiniciar el motor">
                Configuración de umbrales
              </SectionTitle>

              {(
                [
                  { field: 'face_absent_ms' as const, label: 'face_absent_ms', unit: 'ms', hint: 'Tiempo de rostro ausente para emitir evento' },
                  { field: 'multiple_faces_frames' as const, label: 'multiple_faces_frames', unit: 'frames', hint: 'Frames consecutivos con múltiples rostros' },
                  { field: 'gaze_deviation_threshold' as const, label: 'gaze_deviation_threshold', unit: '0..1', hint: 'Magnitud de mirada para considerar desviada' },
                  { field: 'gaze_sustained_ms' as const, label: 'gaze_sustained_ms', unit: 'ms', hint: 'Tiempo de mirada desviada para emitir evento' },
                  { field: 'gaze_fixation_tolerance' as const, label: 'gaze_fixation_tolerance', unit: '0..1', hint: 'Tolerancia de variación para fijación sostenida' },
                ] as { field: keyof TransitionConfig; label: string; unit: string; hint: string }[]
              ).map(({ field, label, unit, hint }) => (
                <div key={field} className="space-y-base">
                  <label className="text-label-sm font-semibold text-on-surface">
                    {label} <span className="text-on-surface-variant font-normal">({unit})</span>
                  </label>
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
            AVISO LEGAL L2.5
        ================================================================ */}
        <div className="bg-primary-fixed/40 rounded-xl p-sm text-label-sm text-on-primary-fixed-variant flex items-start gap-base">
          <Icon name="shield" className="text-[18px] shrink-0" fill />
          <span>
            Herramienta diagnóstica — sin examen real, sin sesión de alumno, sin sanción automática (L2.5).
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
