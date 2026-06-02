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
  /** Senal de contexto: la VENTANA perdio el foco del SO (blur). */
  focus_lost?: boolean;
  /** Senal de contexto: se detecto un monitor adicional. */
  extra_monitor?: boolean;
  /**
   * C-25: la PESTANA del examen dejo de estar visible (visibilitychange).
   * Distinto de focus_lost (blur de ventana OS).
   */
  tab_changed?: boolean;
  /** C-25: el documento salio del modo pantalla completa (fullscreenchange). */
  fullscreen_exited?: boolean;
  /** C-25: accion de portapapeles detectada ('copy' | 'paste'). SIN contenido. */
  clipboard_action?: 'copy' | 'paste';
  /**
   * C-35: Yaw de cabeza en grados (0 = frontal, + = derecha, - = izquierda).
   * Opcional; si undefined, se ignora en evalGaze().
   * Extraido de PoseSignal en el harness (aproximado via landmarks de hombros).
   * Retrocompatible: Examen.tsx no lo pasa y el comportamiento no cambia.
   */
  head_yaw_deg?: number;
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

/**
 * C-35: Umbral de yaw de cabeza para activar la condicion de mirada desviada.
 * Si |head_yaw_deg| supera este valor, evalGaze() lo considera desviacion aunque
 * el iris no supere gaze_deviation_threshold. 20 grados es conservador — un giro
 * leve de cabeza (nod, ajuste de postura) no dispara; un giro lateral visible si.
 * Puede promoverse a TransitionConfig en un change posterior si se requiere configurabilidad
 * por institucion.
 */
const HEAD_YAW_THRESHOLD_DEG = 20;

/**
 * Configuracion por defecto de los umbrales de deteccion.
 *
 * C-46 (ajuste fino basado en observaciones del harness con motor MediaPipe real):
 * - gaze_deviation_threshold: 0.25 → 0.20. Reduce falsos positivos de mirada
 *   desviada al exigir una desviacion mas grande antes de disparar el evento.
 *   El motor MediaPipe real produce desviaciones de ~0.18–0.22 en movimientos
 *   naturales de cabeza; 0.20 las filtra sin ignorar desviaciones laterales reales.
 * - face_absent_ms: 3000 ms (sin cambio — ya calibrado en C-35). Dar mas margen
 *   antes de disparar "rostro ausente" reduce alertas por oclusiones momentaneas.
 *
 * C-35: otros campos recalibrados (gaze_sustained_ms, gaze_fixation_tolerance).
 * Todos los valores son sobreescribibles por UI en el harness diagnostico.
 */
export const DEFAULT_CONFIG: TransitionConfig = {
  face_absent_ms: 3000,
  multiple_faces_frames: 5,
  // C-46: Ajustado de 0.25 a 0.20 para reducir falsos positivos de mirada.
  // Con el motor MediaPipe real, valores de 0.20–0.25 capturan desviaciones
  // laterales visibles sin disparar en movimientos naturales de cabeza.
  gaze_deviation_threshold: 0.20,
  // C-35: Recalibrado de 4000 ms a 2500 ms.
  gaze_sustained_ms: 2500,
  // C-35: Recalibrado de 0.15 a 0.25 para absorber ruido natural de cabeza.
  gaze_fixation_tolerance: 0.25,
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

  // C-25: estado de de-duplicacion para senales de navegador instantaneas.
  // Previene re-emision mientras la senal persiste; se resetea cuando la senal se limpia.
  private tabChangedEmitted = false;
  private fullscreenExitedEmitted = false;
  // clipboard_action es stateless (cada evento copy/paste es discreto); no necesita de-dupe.

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
    // C-35: la condicion "desviado" combina dos fuentes de senal:
    //   1. Vector iris: magnitud >= gaze_deviation_threshold (senal principal).
    //   2. Head yaw (opcional): |head_yaw_deg| > HEAD_YAW_THRESHOLD_DEG (senal complementaria).
    //      Cubre el caso en que el alumno gira la cabeza sin mover los ojos.
    //      Si head_yaw_deg no esta definido (undefined), se ignora — retrocompatible.
    // El ancla y la logica de fijacion sostenida siguen operando sobre el vector iris (g),
    // no sobre head_yaw_deg — mide si la mirada permanece en "esa direccion general".
    const irisDeviated = g !== undefined && magnitude >= this.cfg.gaze_deviation_threshold;
    const yawDeviated = s.head_yaw_deg !== undefined && Math.abs(s.head_yaw_deg) > HEAD_YAW_THRESHOLD_DEG;
    const deviated = irisDeviated || yawDeviated;
    if (deviated) {
      // Cuando el iris esta disponible, usarlo para ancla y deteccion de fijacion sostenida.
      // Cuando solo el yaw dispara (g ausente), se usa un vector neutro (0,0) como ancla —
      // el fijacion tolerance no aplica de forma significativa (el drift es siempre 0 en ese caso).
      const effectiveGaze = g ?? { x: 0, y: 0 };
      if (this.gaze.since_ms === null) {
        this.gaze.since_ms = s.ts_ms;
        this.gaze.anchor = { x: effectiveGaze.x, y: effectiveGaze.y };
      }
      // Solo cuenta como patron sostenido si la mirada se mantiene hacia un PUNTO FIJO
      // (dentro de la tolerancia del ancla). Mirar al techo y volver no fija un punto.
      // Nota: la logica de ancla opera sobre el vector iris (g) para evitar reiniciar
      // el contador cuando el alumno mantiene la mirada pero mueve la cabeza levemente.
      const drift = this.gaze.anchor
        ? Math.hypot(effectiveGaze.x - this.gaze.anchor.x, effectiveGaze.y - this.gaze.anchor.y)
        : Infinity;
      if (drift > this.cfg.gaze_fixation_tolerance) {
        // Se desvio a otro punto: reinicia el ancla (no es fijacion sostenida).
        this.gaze.since_ms = s.ts_ms;
        this.gaze.anchor = { x: effectiveGaze.x, y: effectiveGaze.y };
        this.gaze.emitted = false;
      }
      const elapsed = s.ts_ms - (this.gaze.since_ms ?? s.ts_ms);
      if (elapsed > this.cfg.gaze_sustained_ms && !this.gaze.emitted) {
        this.gaze.emitted = true;
        out.push({
          tipo: "mirada_desviada_sostenida",
          severidad: "media",
          ts_ms: s.ts_ms,
          payload: { sostenido_ms: elapsed, gaze: g ?? effectiveGaze },
          trigger_evidence: false,
        });
      }
    } else {
      // Mirada normal (al frente, o desviacion breve que vuelve): reinicia, sin evento.
      this.gaze = { since_ms: null, anchor: null, emitted: false };
    }
  }

  private evalContext(s: FrameSignals, out: DiscreteEvent[]): void {
    // --- Senales existentes (retrocompat) ---
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

    // --- C-25: cambio_pestana (de-dup: un evento por transicion hidden->visible) ---
    if (s.tab_changed) {
      if (!this.tabChangedEmitted) {
        this.tabChangedEmitted = true;
        out.push({
          tipo: "cambio_pestana",
          severidad: "media",
          ts_ms: s.ts_ms,
          payload: {},
          trigger_evidence: false,
        });
      }
    } else {
      // Pestana visible de nuevo: resetea de-dupe para la proxima salida.
      this.tabChangedEmitted = false;
    }

    // --- C-25: salida_pantalla_completa (de-dup: un evento por salida hasta volver a entrar) ---
    if (s.fullscreen_exited) {
      if (!this.fullscreenExitedEmitted) {
        this.fullscreenExitedEmitted = true;
        out.push({
          tipo: "salida_pantalla_completa",
          severidad: "media",
          ts_ms: s.ts_ms,
          payload: {},
          trigger_evidence: false,
        });
      }
    } else {
      // Volvio a fullscreen: resetea de-dupe para la proxima salida.
      this.fullscreenExitedEmitted = false;
    }

    // --- C-25: copiar_pegar (cada accion es discreta; sin de-dup, sin contenido) ---
    if (s.clipboard_action) {
      out.push({
        tipo: "copiar_pegar",
        severidad: "media",
        ts_ms: s.ts_ms,
        payload: { accion: s.clipboard_action },
        trigger_evidence: false,
      });
    }
  }
}
