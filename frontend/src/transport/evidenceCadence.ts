/**
 * Cadencia de captura de evidencia por screenshot (C-24, DD-24-02).
 *
 * Implementa los DOS disparadores de captura definidos en el change:
 *
 *   1. EVENT-DRIVEN: captura un screenshot en el instante en que un detector
 *      emite un evento de severidad ALTA o CRITICA (RN-CC-01). La captura corre
 *      en paralelo al envío del evento (no bloquea la alerta <500 ms de C-10).
 *
 *   2. HEARTBEAT: captura un screenshot periódico de BAJA FRECUENCIA como línea
 *      base de la sesión. La frecuencia es configurable por examen y respeta la
 *      minimización de datos (Ley 25.326, proporcionalidad L2.5).
 *
 * PROPORCIONALIDAD (DD-24-02, tarea 2.4):
 *   - Default conservador: HEARTBEAT_DEFAULT_SEC = 120 s (2 min).
 *   - Tope máximo configurable: HEARTBEAT_MAX_SEC = 30 s (1 captura cada 30 s).
 *     Configurar por encima del tope (menor intervalo → mayor frecuencia) es
 *     rechazado; así se garantiza minimización de datos.
 *   - Desactivar el heartbeat (intervaloSeg = 0 | false) es válido: solo opera
 *     el mecanismo event-driven.
 *
 * NO HAY GRABACIÓN DE VIDEO CONTINUO en ningún punto (C-24, tarea 1.4).
 * El screenshot es insumo para REVISIÓN HUMANA; NO dispara sanción (L2.5).
 *
 * CADENA DE CUSTODIA: cada screenshot capturado aquí pasa por ``capturarEvidencia``
 * (evidenceCapture.ts), que implementa hash SHA-256 + firma HMAC de sesión +
 * upload directo por presigned URL (etapa 1 de RN-CC-02/04). Las etapas 2 y 3
 * (backend + worker) operan server-side sobre el mismo binario.
 */

import type { DiscreteEvent } from "../proctoring/stateTransitionRules";
import {
  capturarEvidencia,
  capturarFrame,
  type CaptureDeps,
  type EvidenceNotification,
} from "./evidenceCapture";

// ---------------------------------------------------------------------------
// Constantes de cadencia (DD-24-02, tarea 2.3 y 2.4)
// ---------------------------------------------------------------------------

/** Intervalo de heartbeat por defecto (segundos). Conservador = 1 captura / 2 min. */
export const HEARTBEAT_DEFAULT_SEC = 120;

/**
 * Tope MÍNIMO de intervalo permitido (segundos). Un intervalo más corto
 * (mayor frecuencia) viola la minimización → es rechazado (tarea 2.4).
 *
 * Equivale a 1 screenshot cada 30 s como máximo permitido.
 */
export const HEARTBEAT_MAX_FREQ_SEC = 30;

// ---------------------------------------------------------------------------
// Tipos públicos
// ---------------------------------------------------------------------------

/**
 * Configuración de cadencia, normalmente proveniente de la configuración del
 * examen (params de backend) o de la variable de entorno VITE_EVIDENCE_HEARTBEAT_SEC.
 *
 * ``heartbeatSeg = 0`` desactiva el heartbeat (solo opera event-driven).
 */
export interface CadenceConfig {
  /**
   * Intervalo de heartbeat en segundos.
   * 0 = desactivado; valor > 0 activa el heartbeat.
   * Valores entre 1 y HEARTBEAT_MAX_FREQ_SEC - 1 son rechazados (tope de
   * frecuencia máxima, tarea 2.4).
   */
  heartbeatSeg: number;
}

/** Callback que recibe la notificación de evidencia tras cada captura exitosa. */
export type EvidenceReadyCallback = (notification: EvidenceNotification) => void;

// ---------------------------------------------------------------------------
// Helpers de validación de cadencia
// ---------------------------------------------------------------------------

/**
 * Valida la cadencia. Devuelve null si es válida; un mensaje de error si no.
 *
 * Regla de proporcionalidad (tarea 2.4):
 *   - heartbeatSeg = 0 → desactivado (válido).
 *   - heartbeatSeg >= HEARTBEAT_MAX_FREQ_SEC → válido (frecuencia dentro del tope).
 *   - 0 < heartbeatSeg < HEARTBEAT_MAX_FREQ_SEC → inválido (frecuencia excesiva).
 */
export function validarCadencia(cfg: CadenceConfig): string | null {
  const { heartbeatSeg } = cfg;
  if (heartbeatSeg === 0) return null; // desactivado: siempre válido
  if (heartbeatSeg < HEARTBEAT_MAX_FREQ_SEC) {
    return (
      `Intervalo de heartbeat demasiado corto (${heartbeatSeg} s). ` +
      `El mínimo permitido es ${HEARTBEAT_MAX_FREQ_SEC} s para respetar ` +
      `la minimización de datos (Ley 25.326, proporcionalidad L2.5).`
    );
  }
  return null; // válido
}

/**
 * Resuelve el intervalo efectivo de heartbeat (en ms) aplicando:
 *   1. La variable de entorno VITE_EVIDENCE_HEARTBEAT_SEC (si está definida y es válida).
 *   2. El parámetro ``cfg.heartbeatSeg`` del examen.
 *   3. El default conservador HEARTBEAT_DEFAULT_SEC.
 *
 * Si el valor resuelto viola el tope de frecuencia máxima, lanza un Error.
 * Devuelve 0 si el heartbeat debe desactivarse.
 */
export function resolverIntervalMs(cfg?: Partial<CadenceConfig>): number {
  // 1. Variable de entorno (override de desarrollo/ops)
  const envRaw = typeof import.meta !== "undefined"
    ? (import.meta.env?.VITE_EVIDENCE_HEARTBEAT_SEC as string | undefined)
    : undefined;
  let seg: number;

  if (envRaw !== undefined && envRaw !== "") {
    const parsed = Number(envRaw);
    if (!Number.isFinite(parsed) || parsed < 0) {
      throw new Error(`VITE_EVIDENCE_HEARTBEAT_SEC inválido: "${envRaw}"`);
    }
    seg = parsed;
  } else if (cfg?.heartbeatSeg !== undefined) {
    seg = cfg.heartbeatSeg;
  } else {
    seg = HEARTBEAT_DEFAULT_SEC;
  }

  if (seg === 0) return 0; // desactivado

  const error = validarCadencia({ heartbeatSeg: seg });
  if (error) throw new Error(error);

  return seg * 1000;
}

// ---------------------------------------------------------------------------
// EvidenceCadenceController — orquesta event-driven + heartbeat
// ---------------------------------------------------------------------------

/**
 * Orquesta la cadencia de captura de evidencia (C-24).
 *
 * Uso:
 *   const ctrl = new EvidenceCadenceController(videoEl, deps, onReady, cfg);
 *   ctrl.start();
 *   // ...desde visionPipeline.ts (onEvidence hook):
 *   ctrl.onEventDriven(discreteEvent);
 *   // ...al cerrar la sesión:
 *   ctrl.stop();
 *
 * RESTRICCIÓN: NO graba video; cada captura es un frame único (canvas snapshot).
 * RESTRICCIÓN: NO sanciona automáticamente; el resultado es insumo de revisión humana.
 */
export class EvidenceCadenceController {
  private readonly videoEl: HTMLVideoElement;
  private readonly deps: CaptureDeps;
  private readonly onReady: EvidenceReadyCallback;
  private readonly intervalMs: number;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;

  constructor(
    videoEl: HTMLVideoElement,
    deps: CaptureDeps,
    onReady: EvidenceReadyCallback,
    cfg?: Partial<CadenceConfig>,
  ) {
    this.videoEl = videoEl;
    this.deps = deps;
    this.onReady = onReady;
    this.intervalMs = resolverIntervalMs(cfg);
  }

  /**
   * Inicia el heartbeat periódico (si está activado).
   * Llama a start() al iniciar el examen.
   */
  start(): void {
    if (this.heartbeatTimer !== null) return; // ya iniciado
    if (this.intervalMs === 0) return; // heartbeat desactivado

    this.heartbeatTimer = setInterval(async () => {
      await this.capturarYNotificar("heartbeat", "baseline");
    }, this.intervalMs);
  }

  /** Detiene el heartbeat. Llamar al cerrar la sesión. */
  stop(): void {
    if (this.heartbeatTimer !== null) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  /**
   * Disparador EVENT-DRIVEN (tarea 2.1).
   *
   * Llamar desde el hook ``onEvidence`` de ``VisionPipeline`` cuando un evento
   * de severidad alta/critica lo active. La captura corre en paralelo (no awaited
   * por el pipeline) para no demorar la alerta <500 ms de C-10.
   *
   * Eventos de severidad media/baja/baseline son ignorados (RN-CC-01).
   */
  onEventDriven(event: DiscreteEvent): void {
    // Disparar en paralelo (fire-and-forget con manejo de error).
    void this.capturarYNotificar("event", event.severidad);
  }

  // ---------------------------------------------------------------------------
  // Privados
  // ---------------------------------------------------------------------------

  /**
   * Captura el frame actual del video y ejecuta la cadena de custodia (etapa 1).
   * Los errores son logueados pero no relanzados: una captura fallida no debe
   * interrumpir el examen.
   */
  private async capturarYNotificar(
    trigger: "event" | "heartbeat",
    severidad: string,
  ): Promise<void> {
    try {
      const bytes = await capturarFrame(this.videoEl);
      const notification = await capturarEvidencia(severidad, bytes, this.deps, trigger);
      if (notification) {
        this.onReady(notification);
      }
    } catch (err) {
      // Una captura fallida no interrumpe el examen (graceful degradation).
      // En producción este error debería registrarse en el sistema de observabilidad.
      console.warn("[EvidenceCadenceController] captura de evidencia fallida:", err);
    }
  }
}
