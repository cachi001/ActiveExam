/**
 * Pipeline de vision del cliente (C-11): cablea motor abstraido -> reglas de
 * transicion -> emision por el StudentEventChannel (C-10).
 *
 * El pipeline depende SOLO de la interfaz ``VisionEngine`` (DD-17), nunca de
 * MediaPipe: sustituir el motor (ONNX Runtime Web) no cambia el pipeline. Convierte
 * las senales del motor + contexto en frames de senales para las reglas, y emite los
 * eventos discretos resultantes. Los eventos de severidad alta con ``trigger_evidence``
 * disparan la captura de evidencia (via C-12) ademas de emitirse por el canal.
 *
 * NO aplica sanciones (L2.5): solo produce y emite senales/eventos.
 */

import type { VisionEngine } from "../vision/VisionEngine";
import type { ContextSignal } from "./contextDetectors";
import {
  type DiscreteEvent,
  type FrameSignals,
  StateTransitionRules,
  type TransitionConfig,
} from "./stateTransitionRules";

/** Emisor de eventos al transporte de C-10 (StudentEventChannel u otro doble). */
export interface EventSink {
  sendEvent(args: {
    id: string;
    tipo: string;
    severidad: string;
    payload?: Record<string, unknown>;
  }): Promise<void>;
}

/** Disparador de captura de evidencia (cableado a C-12). */
export type EvidenceTrigger = (event: DiscreteEvent) => void;

export interface VisionPipelineOptions {
  engine: VisionEngine;
  sink: EventSink;
  rules?: StateTransitionRules;
  config?: Partial<TransitionConfig>;
  onEvidence?: EvidenceTrigger;
  /** Generador de id de evento (inyectable para tests). */
  idGen?: () => string;
}

export class VisionPipeline {
  private readonly engine: VisionEngine;
  private readonly sink: EventSink;
  private readonly rules: StateTransitionRules;
  private readonly onEvidence?: EvidenceTrigger;
  private readonly idGen: () => string;
  private seq = 0;

  constructor(opts: VisionPipelineOptions) {
    this.engine = opts.engine;
    this.sink = opts.sink;
    this.rules = opts.rules ?? new StateTransitionRules(opts.config);
    this.onEvidence = opts.onEvidence;
    this.idGen = opts.idGen ?? (() => `evt-${(this.seq += 1)}`);
  }

  /**
   * Procesa un frame: corre los detectores del motor (via la interfaz), combina con
   * el contexto del navegador, evalua las reglas y emite los eventos resultantes.
   * Devuelve los eventos emitidos en este frame.
   */
  async onFrame(
    frame: ImageBitmap | VideoFrame,
    ctx: ContextSignal = {},
    ts_ms: number = Date.now(),
  ): Promise<DiscreteEvent[]> {
    // Solo la interfaz VisionEngine: el pipeline NO referencia MediaPipe (DD-17).
    const fd = await this.engine.detectFaces(frame);
    let gaze: { x: number; y: number } | undefined;
    if (fd.face_count >= 1) {
      const mesh = await this.engine.detectFaceMesh(frame);
      gaze = mesh.gaze;
    }
    const signals: FrameSignals = {
      ts_ms,
      face_count: fd.face_count,
      gaze,
      focus_lost: ctx.focus_lost,
      extra_monitor: ctx.extra_monitor,
    };
    return this.emit(this.rules.process(signals));
  }

  /**
   * Evalua reglas sobre senales ya extraidas (util para tests y para inyectar las
   * senales de contexto sin un motor). Emite y devuelve los eventos.
   */
  async onSignals(signals: FrameSignals): Promise<DiscreteEvent[]> {
    return this.emit(this.rules.process(signals));
  }

  private async emit(events: DiscreteEvent[]): Promise<DiscreteEvent[]> {
    for (const e of events) {
      // Disparo de evidencia (C-12) ANTES de awaitear el envio para no demorar la
      // alerta de <500ms; la captura corre en paralelo.
      if (e.trigger_evidence) this.onEvidence?.(e);
      await this.sink.sendEvent({
        id: this.idGen(),
        tipo: e.tipo,
        severidad: e.severidad,
        payload: e.payload,
      });
    }
    return events;
  }
}
