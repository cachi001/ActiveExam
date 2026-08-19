/**
 * useDetectionHarness — TODA la lógica del AdminDetectionHarness (C-23).
 *
 * Pipeline de visión, loop de frames, sink local, detectores de contexto,
 * config de umbrales, medidor de riesgo, log de eventos y envío real-time.
 *
 * Extraído VERBATIM desde AdminDetectionHarness.tsx — sin cambios de lógica.
 * El componente consume este hook y compone los paneles presentacionales.
 *
 * RESTRICCIÓN DE AISLAMIENTO (D-4):
 * NO instancia StudentEventChannel ni ResilientStudentEventChannel.
 * NO realiza llamadas HTTP/WS al backend de producción salvo el envío
 * real-time explícito de modo sesión (api.enviarEventoProctoring).
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { loadScoringWeights } from '../../proctoring/scoringWeights';
import { loadEffectiveConfig, getEffectiveConfig, resetEffectiveConfigCache } from '../../config/effectiveConfigCache';
import { UMBRAL_REVISION_MIN } from '../../config/umbralRevision';
import { useToast } from '../../ui/toast';
import { useApp } from '../../lib/store';
import { api } from '../../lib/api';
import type { Severidad } from '../../lib/types';
import { buildLegendModel, type LegendRow } from './buildLegendModel';

// Visión — reutilizar sin duplicar (C-11, DD-17)
import type { VisionEngine } from '../../vision/VisionEngine';
import type { EventSink } from '../../proctoring/visionPipeline';
import { VisionPipeline } from '../../proctoring/visionPipeline';
import {
  StateTransitionRules,
  type TransitionConfig,
  DEFAULT_CONFIG,
} from '../../proctoring/stateTransitionRules';
// C-25: detector de contexto real para el botón "Detectar pantallas"
// C-32: requestAndDetectExtraMonitor y ScreenPermissionResult
import { requestAndDetectExtraMonitor } from '../../proctoring/contextDetectors';
import type { ScreenPermissionResult } from '../../proctoring/contextDetectors';

import {
  LocalHarnessEventSink,
  type HarnessState,
  type EngineMode,
  type RawSignals,
  type HarnessLogEntry,
  type SinkEventCallback,
  type ConfigErrors,
  type CoverageEntry,
  type MonitorPermission,
} from './types';
import { validateConfig, SEVERITY_ORDER } from './helpers';

/** Severidades que se muestran en el log y en el filtro (baseline excluido). */
const LOG_SEVERITY_ORDER = SEVERITY_ORDER.filter((s) => s !== 'baseline');
import { useContextDetectors } from './useContextDetectors';
import { buildSinkEventHandler } from './sinkEventHandler';
import { useHarnessLifecycle } from './useHarnessLifecycle';

export function useDetectionHarness() {
  // ------ Store ------
  const anomaliasVivo = useApp((s) => s.anomaliasVivo);
  const limpiarAnomalias = useApp((s) => s.limpiarAnomalias);
  const pushAnomalia = useApp((s) => s.pushAnomalia);
  const setProctoringSessionId = useApp((s) => s.setProctoringSessionId);

  // ------ Estado del harness ------
  const [harnessState, setHarnessState] = useState<HarnessState>('idle');
  const [sessionStart, setSessionStart] = useState<number>(0);
  const [elapsed, setElapsed] = useState(0); // segundos desde inicio (para "Sin eventos aún")

  // ------ C-33: Medidor de riesgo ------
  // c-68 task 5.3: el umbral default viene del SISTEMA (Configuración → Scoring),
  // no de un literal local. Si el cache aún no cargó, cae al piso de producto
  // (config/umbralRevision.ts, misma fuente que Configuración y RiskMeter).
  // El admin puede sobreescribirlo localmente para hacer "what-if".
  const [harnessScore, setHarnessScore] = useState(0);
  const [riskThreshold, setRiskThreshold] = useState(
    () => getEffectiveConfig()?.umbral_cola_revision ?? UMBRAL_REVISION_MIN,
  );

  // ------ c-68 task 5.3: leyenda basada en config viva de scoring ------
  const [legendRows, setLegendRows] = useState<LegendRow[]>([]);
  const [legendError, setLegendError] = useState(false);

  // ------ Modo what-if: overrides locales de pesos por evento ------
  // Cuando el admin edita un peso en la leyenda, queda en este mapa y reemplaza
  // al valor del sistema SOLO para esta prueba (no persiste). El sink lee este
  // mapa via ref para evitar recrearlo al cambiar de override.
  const [scoringOverrides, setScoringOverrides] = useState<Record<string, number>>({});
  const scoringOverridesRef = useRef<Record<string, number>>({});
  useEffect(() => { scoringOverridesRef.current = scoringOverrides; }, [scoringOverrides]);

  const setScoringOverride = useCallback((tipoEvento: string, peso: number) => {
    setScoringOverrides((prev) => ({ ...prev, [tipoEvento]: peso }));
  }, []);
  const resetScoringOverrides = useCallback(() => {
    setScoringOverrides({});
  }, []);

  // Detectores activos PARA ESTA PRUEBA (override local del harness). Se siembra de
  // la config del sistema al montar; el usuario puede togglear sin tocar la config real.
  // null = aún no sembrado → fail-open (usa la config persistida).
  const [detectoresActivos, setDetectoresActivos] = useState<string[] | null>(null);
  const detectoresActivosRef = useRef<string[] | null>(null);
  useEffect(() => { detectoresActivosRef.current = detectoresActivos; }, [detectoresActivos]);

  // ------ C-30: Estado del motor de visión ------
  const [engineMode, setEngineMode] = useState<EngineMode>('simulated');
  const [engineError, setEngineError] = useState<string | null>(null);
  // C-32 Task 3.3: true si el motor nunca fue cacheado en esta sesión de página
  // (para mostrar el subtítulo "primera vez" solo en la primera carga).
  const [isFirstEngineLoad, setIsFirstEngineLoad] = useState(true);

  // ------ C-30: Toggles del overlay ------
  const [showPose, setShowPose] = useState(false);
  const [showFullMesh, setShowFullMesh] = useState(true);

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

  // ------ C-25: Checklist de cobertura integral ------
  // Mapea tipo → { capturedAt: timestamp, clipMonitorNA: bool }
  const [coverage, setCoverage] = useState<Partial<Record<string, CoverageEntry>>>({});
  // C-32 Task 6.1: estado del permiso de monitores (reemplaza monitorApiUnavailable)
  // Inicializado según soporte del navegador al montar
  const [monitorPermission, setMonitorPermission] = useState<MonitorPermission>(
    typeof window !== 'undefined' && 'getScreenDetails' in window ? 'idle' : 'unsupported',
  );

  // ------ Filtros y UI ------
  // Inicializar con severidades reales (sin baseline — baseline nunca se muestra en el log)
  const [severityFilter, setSeverityFilter] = useState<Set<Severidad>>(new Set(LOG_SEVERITY_ORDER));
  const [expandedPayloads, setExpandedPayloads] = useState<Set<string>>(new Set());

  // ------ Config de umbrales ------
  const [config, setConfig] = useState<TransitionConfig>({ ...DEFAULT_CONFIG });
  const [configDraft, setConfigDraft] = useState<TransitionConfig>({ ...DEFAULT_CONFIG });
  const [configErrors, setConfigErrors] = useState<ConfigErrors>({});

  // ------ Toast global (sistema reusable) ------
  const toast = useToast();

  // ------ Modo sesión vs modo test ------
  const [modoSesion, setModoSesion] = useState(false);

  // ------ Sesión automática (lifecycle atado a la detección) ------
  /**
   * sessionIdRef: ref estable para que el callback del sink siempre lea el
   * valor actual del sessionId sin recrear el sink (D3 del design.md).
   */
  const sessionIdRef = useRef<string | null>(null);
  /**
   * sessionPromiseRef: permite que onSinkEvent espere a que la sesión esté
   * lista incluso si el primer evento llega antes de que crearSesionProctoring resuelva.
   */
  const sessionPromiseRef = useRef<Promise<string | null> | null>(null);
  /**
   * faceCountRef: último conteo de caras en vivo (fd.face_count) del loop de
   * frames. Sirve de fallback para que TODO evento mande face_count_cliente al
   * backend, aunque el payload del evento no lo incluya explícitamente.
   */
  const faceCountRef = useRef(0);
  // Contador de eventos enviados al backend (real-time — no requiere modo grabación)
  const [eventosEnviados, setEventosEnviados] = useState(0);

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

  // ------ Elapsado para "Sin eventos aún" ------
  useEffect(() => {
    if (harnessState !== 'running') return;
    const t = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(t);
  }, [harnessState]);

  // ------ Cargar config efectiva al montar (pesos + umbrales vivos, task 5.3).
  // Al cargarse, la config efectiva siembra también el cache de scoring weights.
  // Si la API falla, pesoEvento() usa el fallback por severidad (degradación silenciosa).
  // El harness sigue air-gapped para la captura — esta carga es solo para la config baseline.
  useEffect(() => {
    // Invalidamos el cache al montar para tomar SIEMPRE la config vigente,
    // incluso si el admin la cambió desde otra pestaña (igual que Revisor/Perfil).
    resetEffectiveConfigCache();
    void loadEffectiveConfig()
      .then(() => {
        const cfg = getEffectiveConfig();
        if (cfg) {
          // Pre-popular el config del harness con los umbrales vivos del sistema.
          const thresholds = {
            face_absent_ms: cfg.face_absent_ms,
            multiple_faces_frames: cfg.multiple_faces_frames,
            gaze_deviation_threshold: cfg.gaze_deviation_threshold,
            gaze_sustained_ms: cfg.gaze_sustained_ms,
            gaze_fixation_tolerance: cfg.gaze_fixation_tolerance,
          };
          setConfig(thresholds);
          setConfigDraft(thresholds);
          // c-68 task 5.3: el umbral del medidor de riesgo viene del sistema.
          setRiskThreshold(cfg.umbral_cola_revision);
          // Siembra los detectores activos de la prueba desde la config del sistema.
          setDetectoresActivos([...(cfg.detectores_activos ?? [])]);
        }
      })
      .catch(() => void loadScoringWeights());
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ------ c-68 task 5.3: cargar la config viva de scoring para la leyenda ------
  // Air-gapped para la CAPTURA: esto es solo lectura de config baseline.
  // Si falla, marcamos legendError para que la UI avise (no rompe el harness).
  useEffect(() => {
    void api
      .listarScoringConfig()
      .then(({ items }) => {
        const detectoresActivos = getEffectiveConfig()?.detectores_activos;
        setLegendRows(buildLegendModel(items, detectoresActivos));
        setLegendError(false);
      })
      .catch(() => {
        setLegendRows([]);
        setLegendError(true);
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ------ C-25: Detectores de contexto reales (estado + refs + efectos en sub-hook) ------
  const {
    envSignals,
    setEnvSignals,
    envFocusLostRef,
    envTabChangedRef,
    envFullscreenExitedRef,
    envClipboardRef,
    envExtraMonitorRef,
  } = useContextDetectors(harnessState, monitorPermission);

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

  // Redefine onSinkEvent.current en cada render para capturar estado fresco.
  // El cuerpo vive en buildSinkEventHandler (mismas refs/setters estables → mismo flujo).
  onSinkEvent.current = buildSinkEventHandler({
    anomaliasLengthRef,
    sessionIdRef,
    sessionPromiseRef,
    faceCountRef,
    videoRef,
    logSeqRef,
    pushAnomalia,
    setCoverage,
    setHarnessScore,
    setLogEntries,
    setLogTruncated,
    setEventosEnviados,
    scoringOverridesRef,
    detectoresActivosRef,
  });

  // ------ Lifecycle: start/stop + cleanup de desmontaje (sub-hook) ------
  const { startHarness, stopHarness } = useHarnessLifecycle({
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
  });

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
    setSeverityFilter(new Set(LOG_SEVERITY_ORDER));
  }, []);

  // ------ Exportar log (task 8.2) ------
  const exportLog = useCallback(() => {
    const events = logEntries.map((e) => e.event);
    if (events.length === 0) {
      toast.info('El log está vacío — no hay eventos para exportar.');
      return;
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
  }, [logEntries, sessionStart, config, toast]);

  // ------ Entries filtradas — excluye baseline + aplica filtro de severidad ------
  const filteredEntries = logEntries
    .filter((e) => e.event.severidad !== 'baseline')
    .filter((e) => severityFilter.has(e.event.severidad as Severidad));
  const isFilterActive = severityFilter.size !== LOG_SEVERITY_ORDER.length;

  // ------ Estado del panel de propósito (task 4.4) ------
  const [propositoPanelOpen, setPropositoPanelOpen] = useState(false);

  return {
    // refs (DOM)
    videoRef,
    engineRef,
    sinkRef,
    pipelineRef,
    // estado del harness
    harnessState,
    sessionStart,
    elapsed,
    modoSesion,
    eventosEnviados,
    // motor de visión
    engineMode,
    setEngineMode,
    engineError,
    setEngineError,
    isFirstEngineLoad,
    // overlay
    showPose,
    setShowPose,
    showFullMesh,
    setShowFullMesh,
    // señales
    rawSignals,
    envSignals,
    // log
    logEntries,
    logTruncated,
    filteredEntries,
    isFilterActive,
    severityFilter,
    expandedPayloads,
    setExpandedPayloads,
    // cobertura + monitor
    coverage,
    monitorPermission,
    // config umbrales
    config,
    configDraft,
    setConfigDraft,
    configErrors,
    setConfigErrors,
    setConfig,
    // medidor de riesgo
    harnessScore,
    setHarnessScore,
    riskThreshold,
    setRiskThreshold,
    // c-68: leyenda viva
    legendRows,
    legendError,
    // what-if: overrides locales de pesos
    scoringOverrides,
    setScoringOverride,
    resetScoringOverrides,
    // detectores activos para esta prueba (override local, sembrado de la config)
    detectoresActivos,
    setDetectoresActivos,
    // store
    anomaliasVivo,
    limpiarAnomalias,
    // panel propósito
    propositoPanelOpen,
    setPropositoPanelOpen,
    // handlers
    createPipeline,
    startHarness,
    stopHarness,
    applyConfigChange,
    resetRules,
    handleRequestMonitorPermission,
    toggleSeverityFilter,
    showAllSeverities,
    exportLog,
  };
}
