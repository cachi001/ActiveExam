/**
 * Capa de resiliencia de red sin perdida sobre el canal WS del estudiante
 * (C-14, Flujo 5). EXTIENDE el ``StudentEventChannel`` de C-10 (lo compone, no lo
 * duplica): el canal sigue siendo el unico transporte; esta clase le agrega
 * buffer IndexedDB, reconexion con backoff+jitter, replay ordenado con dedup y la
 * politica por duracion del corte.
 *
 * Responsabilidades (todas delegadas a modulos puros/portados, testeados aparte):
 *   - persistir cada evento en el buffer ANTES de enviarlo (RN-HB-02);
 *   - ante caida del WS, reconectar con backoff exponencial + jitter 20% (RN-HB-05)
 *     reusando el handshake con ``last_event_id`` que ya expone el canal de C-10;
 *   - al reconectar, drenar el buffer en orden y deduplicar por ``event_id`` contra
 *     el backend (exactly-once logico, RN-HB-03);
 *   - clasificar el corte: > 5 min emite un evento critico (señal, NO sancion, L2.5).
 *
 * Todo el I/O (WS, IndexedDB, reloj) entra por puertos inyectables: testeable sin
 * DOM. NUNCA deriva una sancion (invariante L2.5).
 */

import { CircularEventBuffer, type EventBufferStore } from "./eventBuffer";
import { backoffDelayMs, type BackoffOptions } from "./reconnectBackoff";
import { classifyOutage, type ProlongedOutageEvent } from "./outagePolicy";
import { drainAndReplay, type ReplaySender } from "./replayCoordinator";
import {
  newResilienceMetrics,
  recordProlongedOutage,
  recordReconnection,
  recordReplay,
  type ResilienceMetrics,
  setBufferSize,
} from "./resilienceMetrics";
import type { StudentEventChannel } from "./StudentEventChannel";

/** Construye el canal C-10 con el ``lastEventId`` del handshake de reconexion. */
export type ChannelFactory = (lastEventId: string | undefined) => StudentEventChannel;

export interface ResilientChannelOptions {
  store: EventBufferStore;
  channelFactory: ChannelFactory;
  /** Envia un evento bufferizado durante el replay y espera el ack del backend. */
  replaySender: ReplaySender;
  bufferCapacity?: number;
  backoff?: BackoffOptions;
  /** Reloj inyectable (ms) para medir la duracion del corte. Default ``Date.now``. */
  nowMs?: () => number;
  /** Programador de reintentos inyectable. Default ``setTimeout``. */
  scheduleImpl?: (fn: () => void, ms: number) => unknown;
  /** Se invoca con el evento critico cuando el corte supera 5 min (señal al panel). */
  onProlongedOutage?: (event: ProlongedOutageEvent) => void;
}

export class ResilientStudentEventChannel {
  private readonly buffer: CircularEventBuffer;
  private readonly nowMs: () => number;
  private readonly schedule: (fn: () => void, ms: number) => unknown;
  private channel: StudentEventChannel | null = null;
  private attempt = 0;
  private lastEventId: string | undefined;
  private lastHeartbeatMs: number;
  /** Metricas de resiliencia (DD-12, RN-GLB-05). */
  readonly metrics: ResilienceMetrics = newResilienceMetrics();

  constructor(private readonly opts: ResilientChannelOptions) {
    this.buffer = new CircularEventBuffer(opts.store, opts.bufferCapacity);
    this.nowMs = opts.nowMs ?? (() => Date.now());
    this.schedule =
      opts.scheduleImpl ?? ((fn, ms) => setTimeout(fn, ms) as unknown);
    this.lastHeartbeatMs = this.nowMs();
  }

  /** Conecta el canal C-10; al abrir, drena el buffer pendiente. */
  async connect(): Promise<void> {
    this.channel = this.opts.channelFactory(this.lastEventId);
    this.channel.connect();
  }

  /**
   * Persiste el evento en el buffer (RN-HB-02) y, si el canal esta abierto, lo
   * envia. Si el WS esta caido, queda solo bufferizado para el replay posterior.
   */
  async sendEvent(args: {
    id: string;
    tipo: string;
    severidad: string;
    payload?: Record<string, unknown>;
  }): Promise<void> {
    // bufferiza ANTES de enviar: si el envio falla, el evento no se pierde
    await this.buffer.append(args.id, args);
    this.lastEventId = args.id;
    if (this.channel) {
      try {
        await this.channel.sendEvent(args);
      } catch {
        // queda en el buffer; se reenvia al reconectar
      }
    }
  }

  /** Registra la llegada de un heartbeat (reloj del corte, RN-HB-01). */
  markHeartbeat(): void {
    this.lastHeartbeatMs = this.nowMs();
  }

  /**
   * Maneja la caida del WS: clasifica el corte por duracion y programa la
   * reconexion con backoff + jitter. Pensado para cablearse al ``onclose`` del WS.
   */
  handleDisconnect(): void {
    const delay = backoffDelayMs(this.attempt, this.opts.backoff);
    this.attempt += 1;
    this.schedule(() => void this.reconnect(), delay);
  }

  /**
   * Reconecta: evalua la politica de corte (emite evento critico si > 5 min),
   * reabre el canal con ``last_event_id`` y drena el buffer en orden con dedup.
   */
  async reconnect(): Promise<void> {
    const outage = classifyOutage(this.lastHeartbeatMs, this.nowMs());
    if (outage) {
      // SEÑAL al panel, NUNCA sancion (L2.5): se bufferiza y enviara como evento
      const criticalId = `outage-${this.nowMs()}`;
      await this.buffer.append(criticalId, outage);
      recordProlongedOutage(this.metrics);
      this.opts.onProlongedOutage?.(outage);
    }

    this.channel = this.opts.channelFactory(this.lastEventId);
    this.channel.connect();
    this.attempt = 0; // reconexion exitosa: reinicia el backoff
    this.lastHeartbeatMs = this.nowMs();
    recordReconnection(this.metrics);

    await this.drain();
  }

  /** Drena el buffer en orden reenviando pendientes con dedup exactly-once logico. */
  async drain(): Promise<{ persisted: string[]; deduplicated: string[] }> {
    const res = await drainAndReplay(this.buffer, this.opts.replaySender);
    recordReplay(this.metrics, res);
    setBufferSize(this.metrics, await this.buffer.size());
    return { persisted: res.persisted, deduplicated: res.deduplicated };
  }

  /** Cantidad de eventos pendientes en el buffer (diagnostico/metricas). */
  async pendingCount(): Promise<number> {
    return this.buffer.size();
  }

  /** Nro. de intento de reconexion actual (diagnostico/metricas). */
  get reconnectAttempt(): number {
    return this.attempt;
  }
}
