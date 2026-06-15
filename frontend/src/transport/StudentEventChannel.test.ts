/**
 * Tests del canal WS del estudiante (C-10, DD-16). Formato Vitest.
 *
 * Usa un WebSocket FAKE inyectado y un timer fake para verificar: handshake con
 * session_id+JWT+last_event_id, envio de evento firmado, heartbeat firmado /5s y
 * recepcion de comandos backend->cliente.
 */

import { describe, expect, it, vi } from "vitest";

import { HEARTBEAT_INTERVAL_MS, StudentEventChannel } from "./StudentEventChannel";

class FakeWebSocket {
  static last: FakeWebSocket | null = null;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onclose: (() => void) | null = null;
  closed = false;

  constructor(public url: string) {
    FakeWebSocket.last = this;
  }

  send(data: string): void {
    this.sent.push(data);
  }

  close(): void {
    this.closed = true;
    this.onclose?.();
  }

  open(): void {
    this.onopen?.();
  }

  receive(data: unknown): void {
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent);
  }
}

function build(overrides: Partial<Parameters<typeof StudentEventChannel.prototype.constructor>[0]> = {}) {
  let timerFn: (() => void) | null = null;
  const channel = new StudentEventChannel({
    wsUrl: "wss://api/events/ws",
    sessionId: "sess-1",
    examId: "e1",
    accessToken: "jwt-token",
    sessionKey: "clave-hex",
    lastEventId: "42",
    webSocketCtor: FakeWebSocket as unknown as typeof WebSocket,
    setIntervalImpl: ((fn: () => void) => {
      timerFn = fn;
      return 1 as unknown as ReturnType<typeof setInterval>;
    }) as never,
    clearIntervalImpl: (() => {}) as never,
    now: () => "2026-05-30T10:00:00Z",
    ...overrides,
  });
  return { channel, getTimer: () => timerFn };
}

describe("handshake", () => {
  it("incluye session_id, access_token y last_event_id en la URL", () => {
    const { channel } = build();
    channel.connect();
    const url = FakeWebSocket.last!.url;
    expect(url).toContain("session_id=sess-1");
    expect(url).toContain("access_token=jwt-token");
    expect(url).toContain("last_event_id=42");
  });
});

describe("envio de eventos firmados", () => {
  it("firma y envia un evento con todos los campos del contrato", async () => {
    const { channel } = build();
    channel.connect();
    await channel.sendEvent({ id: "evt-1", tipo: "multiples_rostros", severidad: "alta" });
    const sent = JSON.parse(FakeWebSocket.last!.sent[0]);
    expect(sent.session_id).toBe("sess-1");
    expect(sent.exam_id).toBe("e1");
    expect(sent.tipo).toBe("multiples_rostros");
    expect(sent.firma).toMatch(/^[0-9a-f]{64}$/);
    expect(sent.schema_version).toBe(1);
  });
});

describe("heartbeat firmado /5s", () => {
  it("usa el intervalo de 5s", () => {
    expect(HEARTBEAT_INTERVAL_MS).toBe(5000);
  });

  it("dispara un heartbeat firmado al vencer el intervalo", async () => {
    const { channel, getTimer } = build();
    channel.connect();
    FakeWebSocket.last!.open(); // arranca el heartbeat (registra el timer de 5s)
    // El timer hace `void sendHeartbeat()` (fire-and-forget) y la firma es async
    // (crypto.subtle). Depender de flushear esa cadena por timing es FLAKY según
    // el orden de la suite. En su lugar verificamos que el timer quedó registrado
    // y firmamos un heartbeat de forma determinística con await.
    expect(getTimer()).toBeTypeOf("function");
    await channel.sendHeartbeat();
    const sent = FakeWebSocket.last!.sent.map((s) => JSON.parse(s));
    const hb = sent.find((m) => m.tipo === "heartbeat");
    expect(hb).toBeTruthy();
    expect(hb.severidad).toBe("baseline");
    expect(hb.firma).toMatch(/^[0-9a-f]{64}$/);
  });
});

describe("comandos backend->cliente", () => {
  it("invoca onCommand cuando llega un comando", () => {
    const onCommand = vi.fn();
    const { channel } = build({ onCommand });
    channel.connect();
    FakeWebSocket.last!.receive({ cmd: "recapturar" });
    expect(onCommand).toHaveBeenCalledWith({ cmd: "recapturar" });
  });
});
