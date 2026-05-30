/**
 * Canal WebSocket del estudiante (C-10, Flujo 3, DD-16).
 *
 * Abre el WS con handshake (``session_id`` + ``access_token`` JWT + ``last_event_id``),
 * firma cada evento/heartbeat con la clave de sesion (C-09) y emite un HEARTBEAT
 * FIRMADO cada 5 s (RN-HB-01). Recibe acks y comandos backend->cliente.
 *
 * El cliente es un SENSOR NO CONFIABLE (RN-GLB-01): el backend re-valida la firma
 * server-side antes de persistir. Este canal es FIJO (DD-16), separado del panel.
 *
 * ``WebSocketCtor`` y el reloj (``setIntervalImpl``) son inyectables para tests.
 */

import { canonicalMessage, type SignableEvent, signEvent } from "./eventSignature";

export const HEARTBEAT_INTERVAL_MS = 5000;
export const SCHEMA_VERSION = 1;

export interface StudentEventChannelOptions {
  wsUrl: string;
  sessionId: string;
  examId: string;
  accessToken: string;
  sessionKey: string;
  lastEventId?: string;
  webSocketCtor?: typeof WebSocket;
  subtle?: SubtleCrypto;
  /** Inyectable para tests; default ``setInterval``. */
  setIntervalImpl?: (fn: () => void, ms: number) => ReturnType<typeof setInterval>;
  clearIntervalImpl?: (id: ReturnType<typeof setInterval>) => void;
  /** Reloj inyectable para ``ts_client`` (default ``Date``). */
  now?: () => string;
  onCommand?: (command: unknown) => void;
}

export class StudentEventChannel {
  private ws: WebSocket | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private readonly opts: Required<
    Pick<StudentEventChannelOptions, "webSocketCtor" | "subtle" | "setIntervalImpl" | "clearIntervalImpl" | "now">
  > &
    StudentEventChannelOptions;

  constructor(options: StudentEventChannelOptions) {
    this.opts = {
      webSocketCtor: options.webSocketCtor ?? WebSocket,
      subtle: options.subtle ?? crypto.subtle,
      setIntervalImpl: options.setIntervalImpl ?? setInterval,
      clearIntervalImpl: options.clearIntervalImpl ?? clearInterval,
      now: options.now ?? (() => new Date().toISOString()),
      ...options,
    };
  }

  /** Abre el canal con el handshake (session_id + JWT + last_event_id). */
  connect(): void {
    const params = new URLSearchParams({
      session_id: this.opts.sessionId,
      access_token: this.opts.accessToken,
    });
    if (this.opts.lastEventId) params.set("last_event_id", this.opts.lastEventId);
    const url = `${this.opts.wsUrl}?${params.toString()}`;
    this.ws = new this.opts.webSocketCtor(url);
    this.ws.onmessage = (ev: MessageEvent) => this.handleMessage(ev);
    this.ws.onopen = () => this.startHeartbeat();
    this.ws.onclose = () => this.stopHeartbeat();
  }

  /** Firma y envia un evento de telemetria por el canal. */
  async sendEvent(args: {
    id: string;
    tipo: string;
    severidad: string;
    payload?: Record<string, unknown>;
  }): Promise<void> {
    const base: SignableEvent = {
      id: args.id,
      session_id: this.opts.sessionId,
      exam_id: this.opts.examId,
      tipo: args.tipo,
      severidad: args.severidad,
      ts_client: this.opts.now(),
      schema_version: SCHEMA_VERSION,
    };
    const firma = await signEvent(base, this.opts.sessionKey, this.opts.subtle);
    this.rawSend({ ...base, payload: args.payload ?? {}, firma });
  }

  /** Construye, firma y envia un heartbeat (prueba de vida). */
  async sendHeartbeat(): Promise<void> {
    await this.sendEvent({
      id: `hb-${this.opts.now()}`,
      tipo: "heartbeat",
      severidad: "baseline",
    });
  }

  /** Cierra el canal y detiene el heartbeat. */
  close(): void {
    this.stopHeartbeat();
    this.ws?.close();
  }

  /** Mensaje canonico de un evento (util para tests/diagnostico). */
  static canonical(ev: SignableEvent): string {
    return canonicalMessage(ev);
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = this.opts.setIntervalImpl(() => {
      void this.sendHeartbeat();
    }, HEARTBEAT_INTERVAL_MS);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer !== null) {
      this.opts.clearIntervalImpl(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private handleMessage(ev: MessageEvent): void {
    let data: unknown;
    try {
      data = JSON.parse(ev.data as string);
    } catch {
      return;
    }
    // Comandos backend->cliente (canal bidireccional, DD-16).
    if (data && typeof data === "object" && "cmd" in (data as Record<string, unknown>)) {
      this.opts.onCommand?.(data);
    }
  }

  private rawSend(message: object): void {
    this.ws?.send(JSON.stringify(message));
  }
}
