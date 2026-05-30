/**
 * Reglas de transicion de estado (C-11, RN-EV-01..RN-EV-06, US-006).
 *
 * Convierte SENALES CONTINUAS de los detectores (rostro ausente, multiples rostros,
 * mirada, contexto del navegador) en EVENTOS DISCRETOS con severidad, usando
 * umbrales temporales, fotogramas consecutivos y patrones sostenidos. Filtra el
 * ruido instantaneo (un parpadeo, mirar al techo para pensar) que generaria falsos
 * positivos masivos a escala (RN-SC-05).
 *
 * La IA NO decide "fraude": produce SENALES; estas reglas producen EVENTOS. NINGUNA
 * transicion deriva una sancion automatica (L2.5, RN-EV-01, RN-RV-07). Los eventos
 * son conformes al ``event-schema-contract`` de C-10 (tipo, severidad, payload) y se
 * emiten por el StudentEventChannel.
 *
 * Logica PURA: el reloj entra como parametro (``ts_ms``), no se lee del entorno, para
 * testear umbrales temporales de forma determinista.
 */

/** Severidad de un evento (conforme al contrato de C-10). */
export type Severidad = "baseline" | "baja" | "media" | "alta" | "critica";

/** Senales continuas observadas en un frame (entrada de las reglas). */
export interface FrameSignals {
  /** Marca temporal del frame en milisegundos (reloj inyectado). */
  ts_ms: number;
  /** Cantidad de rostros detectados por Face Detection. */
  face_count: number;
  /** Direccion de la mirada normalizada (-1..1); ausente si no hay rostro. */
  gaze?: { x: number; y: number };
  /** Senal de contexto: la ventana/pestana perdio el foco. */
  focus_lost?: boolean;
  /** Senal de contexto: se detecto un monitor adicional. */
  extra_monitor?: boolean;
}

/** Evento discreto producido por las reglas (conforme al contrato de C-10). */
export interface DiscreteEvent {
  tipo: string;
  severidad: Severidad;
  /** Momento de emision (ts_ms del frame que dispara la transicion). */
  ts_ms: number;
  payload: Record<string, unknown>;
  /**
   * Indica si este evento debe disparar captura de evidencia (via C-12). Las reglas
   * SOLO marcan el flag; NO ejecutan ninguna sancion (L2.5).
   */
  trigger_evidence: boolean;
}

/**
 * Configuracion de los umbrales por institucion (RN-EV-03). Todos los valores tienen
 * defaults conservadores (minimizan falsos positivos, D4).
 */
export interface TransitionConfig {
  /** Rostro ausente debe sostenerse > este umbral (ms) para emitir evento. */
  face_absent_ms: number;
  /** Multiples rostros (>=2) durante este numero de frames consecutivos -> alta. */
  multiple_faces_frames: number;
  /** Magnitud de mirada (|gaze|) por encima de la cual se considera "desviada". */
  gaze_deviation_threshold: number;
  /** La mirada desviada debe sostenerse > este umbral (ms) para emitir evento. */
  gaze_sustained_ms: number;
  /** Tolerancia de variacion de mirada para considerarla "hacia un punto fijo". */
  gaze_fixation_tolerance: number;
}

export const DEFAULT_CONFIG: TransitionConfig = {
  face_absent_ms: 3000,
  multiple_faces_frames: 5,
  gaze_deviation_threshold: 0.6,
  gaze_sustained_ms: 4000,
  gaze_fixation_tolerance: 0.15,
};

interface AbsentState {
  since_ms: number | null;
  emitted: boolean;
}

interface GazeState {
  since_ms: number | null;
  anchor: { x: number; y: number } | null;
  emitted: boolean;
}

/**
 * Maquina de reglas de transicion. Acumula estado entre frames y emite eventos
 * discretos cuando una senal cruza su umbral sostenido. Configurable por institucion.
 */
export class StateTransitionRules {
  private readonly cfg: TransitionConfig;
  private absent: AbsentState = { since_ms: null, emitted: false };
  private gaze: GazeState = { since_ms: null, anchor: null, emitted: false };
  private multiFaceFrames = 0;
  private multiFaceEmitted = false;

  constructor(config: Partial<TransitionConfig> = {}) {
    this.cfg = { ...DEFAULT_CONFIG, ...config };
  }

  /**
   * Procesa un frame de senales y devuelve los eventos discretos que se disparan en
   * ese frame (0, 1 o varios). NUNCA aplica una sancion: solo produce eventos.
   */
  process(s: FrameSignals): DiscreteEvent[] {
    const events: DiscreteEvent[] = [];
    this.evalFaceAbsent(s, events);
    this.evalMultipleFaces(s, events);
    this.evalGaze(s, events);
    this.evalContext(s, events);
    return events;
  }

  private evalFaceAbsent(s: FrameSignals, out: DiscreteEvent[]): void {
    if (s.face_count === 0) {
      if (this.absent.since_ms === null) this.absent.since_ms = s.ts_ms;
      const elapsed = s.ts_ms - this.absent.since_ms;
      if (elapsed > this.cfg.face_absent_ms && !this.absent.emitted) {
        this.absent.emitted = true;
        out.push({
          tipo: "rostro_ausente",
          severidad: "media",
          ts_ms: s.ts_ms,
          payload: { sostenido_ms: elapsed },
          trigger_evidence: false,
        });
      }
    } else {
      // Rostro presente: el frame aislado de ausencia previo no genera evento (ruido).
      this.absent = { since_ms: null, emitted: false };
    }
  }

  private evalMultipleFaces(s: FrameSignals, out: DiscreteEvent[]): void {
    if (s.face_count >= 2) {
      this.multiFaceFrames += 1;
      if (this.multiFaceFrames >= this.cfg.multiple_faces_frames && !this.multiFaceEmitted) {
        this.multiFaceEmitted = true;
        out.push({
          tipo: "multiples_rostros",
          severidad: "alta",
          ts_ms: s.ts_ms,
          payload: { face_count: s.face_count, frames_consecutivos: this.multiFaceFrames },
          // Severidad alta -> dispara captura de evidencia (via C-12) + alerta <500ms (C-10).
          trigger_evidence: true,
        });
      }
    } else {
      this.multiFaceFrames = 0;
      this.multiFaceEmitted = false;
    }
  }

  private evalGaze(s: FrameSignals, out: DiscreteEvent[]): void {
    const g = s.gaze;
    const magnitude = g ? Math.hypot(g.x, g.y) : 0;
    const deviated = g !== undefined && magnitude >= this.cfg.gaze_deviation_threshold;
    if (deviated && g) {
      if (this.gaze.since_ms === null) {
        this.gaze.since_ms = s.ts_ms;
        this.gaze.anchor = { x: g.x, y: g.y };
      }
      // Solo cuenta como patron sostenido si la mirada se mantiene hacia un PUNTO FIJO
      // (dentro de la tolerancia del ancla). Mirar al techo y volver no fija un punto.
      const drift = this.gaze.anchor
        ? Math.hypot(g.x - this.gaze.anchor.x, g.y - this.gaze.anchor.y)
        : Infinity;
      if (drift > this.cfg.gaze_fixation_tolerance) {
        // Se desvio a otro punto: reinicia el ancla (no es fijacion sostenida).
        this.gaze.since_ms = s.ts_ms;
        this.gaze.anchor = { x: g.x, y: g.y };
        this.gaze.emitted = false;
      }
      const elapsed = s.ts_ms - (this.gaze.since_ms ?? s.ts_ms);
      if (elapsed > this.cfg.gaze_sustained_ms && !this.gaze.emitted) {
        this.gaze.emitted = true;
        out.push({
          tipo: "mirada_desviada_sostenida",
          severidad: "media",
          ts_ms: s.ts_ms,
          payload: { sostenido_ms: elapsed, gaze: g },
          trigger_evidence: false,
        });
      }
    } else {
      // Mirada normal (al frente, o desviacion breve que vuelve): reinicia, sin evento.
      this.gaze = { since_ms: null, anchor: null, emitted: false };
    }
  }

  private evalContext(s: FrameSignals, out: DiscreteEvent[]): void {
    if (s.focus_lost) {
      out.push({
        tipo: "perdida_de_foco",
        severidad: "baja",
        ts_ms: s.ts_ms,
        payload: {},
        trigger_evidence: false,
      });
    }
    if (s.extra_monitor) {
      out.push({
        tipo: "monitor_adicional",
        severidad: "alta",
        ts_ms: s.ts_ms,
        payload: {},
        trigger_evidence: false,
      });
    }
  }
}
