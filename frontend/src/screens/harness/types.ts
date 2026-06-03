/**
 * Tipos locales del AdminDetectionHarness (C-23).
 *
 * Extraídos sin cambios desde AdminDetectionHarness.tsx para el refactor
 * estructural. La lógica del sink/pipeline vive en useDetectionHarness.ts.
 */

import type { FaceDetectionSignal, FaceMeshSignal, PoseSignal } from '../../vision/VisionEngine';
import type { DiscreteEvent, TransitionConfig } from '../../proctoring/stateTransitionRules';
import type { EventSink } from '../../proctoring/visionPipeline';

// ---------------------------------------------------------------------------
// Constantes
// ---------------------------------------------------------------------------

/** Límite de entradas del log local (independiente del límite de 50 de anomaliasVivo). */
export const LOG_MAX = 200;

/** FPS objetivo del bucle de frames del harness. */
export const FRAME_INTERVAL_MS = 200; // ~5 fps — suficiente para diagnóstico

// ---------------------------------------------------------------------------
// Tipos locales
// ---------------------------------------------------------------------------

export type HarnessState = 'idle' | 'initializing' | 'running' | 'stopped';

/**
 * C-30: estado del motor de visión en el harness.
 * - simulated: estado inicial, motor stub (C-29)
 * - loading: se está cargando el motor real MediaPipe
 * - real-active: motor real inicializado y procesando frames
 * - load-error: init() falló (WebGL ausente, modelo faltante, etc.)
 */
export type EngineMode = 'simulated' | 'loading' | 'real-active' | 'load-error';

/** Señales crudas del frame actual (actualizadas por cada frame). */
export interface RawSignals {
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
export interface EnvSignals {
  focusLost: boolean;
  tabChanged: boolean;
  fullscreenExited: boolean;
  clipboardAction: 'copy' | 'paste' | null;
  /** null = API no disponible o denegada (no determinable). */
  extraMonitor: boolean | null;
}

/** Entrada del log de eventos del harness con estado del sink. */
export interface HarnessLogEntry {
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
  /** C-46: estado del envío al backend slim ('ok' | 'net-error' | undefined=sin envío) */
  networkBadge?: 'ok' | 'net-error';
  /** C-46: veredicto de re-inferencia del servidor (si networkBadge === 'ok') */
  verdictServer?: string | null;
  /** C-46: face_count reportado por el servidor */
  faceCountServer?: number | null;
}

/** Tipo del callback de notificación del LocalHarnessEventSink. */
export type SinkEventCallback = (
  rawEvent: { id: string; tipo: string; severidad: string; payload?: Record<string, unknown> },
  sinkStatus: 'ok' | 'error',
  sinkError?: string,
) => void;

export type ConfigErrors = Partial<Record<keyof TransitionConfig, string>>;

/** C-25: entrada del checklist de cobertura integral. */
export type CoverageEntry = { capturedAt: number; severidad: string };

/** Estado del permiso de detección de monitores. */
export type MonitorPermission = 'idle' | 'requesting' | 'granted' | 'denied' | 'unsupported';

/**
 * RESTRICCIÓN DE AISLAMIENTO (D-4, C-23):
 * Este sink implementa la interfaz EventSink del pipeline de visión (visionPipeline.ts)
 * acumulando eventos en memoria local y empujando al store Zustand.
 *
 * NO instancia StudentEventChannel ni ResilientStudentEventChannel.
 * NO realiza ninguna llamada HTTP ni WebSocket al backend de producción.
 * Es "air-gapped" del transporte real: puro diagnóstico local.
 */
export class LocalHarnessEventSink implements EventSink {
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
