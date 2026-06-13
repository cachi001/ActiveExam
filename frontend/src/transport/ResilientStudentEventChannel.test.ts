/**
 * Tests e2e de la resiliencia de red (C-14, Flujo 5). Formato Vitest.
 *
 * Cubre el Flujo 5 completo: WS cae -> buffer -> backoff+jitter -> handshake
 * (last_event_id) -> reenvio -> drenaje ordenado -> dedup -> exactly-once; mas la
 * politica por duracion (corte corto sin perdida; corte largo -> evento critico
 * SEÑAL, nunca sancion, L2.5).
 */

import { describe, expect, it, vi } from "vitest";

import { InMemoryEventBufferStore } from "./eventBuffer";
import { PROLONGED_OUTAGE_EVENT_TIPO } from "./outagePolicy";
import type { ReplayAck, ReplaySender } from "./replayCoordinator";
import { ResilientStudentEventChannel } from "./ResilientStudentEventChannel";
import type { StudentEventChannel } from "./StudentEventChannel";

/** Canal C-10 falso: registra el lastEventId del handshake y los envios. */
function fakeChannel() {
  const handshakes: (string | undefined)[] = [];
  const sent: { id: string }[] = [];
  let connected = false;
  const factory = (lastEventId: string | undefined): StudentEventChannel => {
    handshakes.push(lastEventId);
    return {
      connect: () => {
        connected = true;
      },
      sendEvent: async (a: { id: string }) => {
        sent.push(a);
      },
    } as unknown as StudentEventChannel;
  };
  return { factory, handshakes, sent, isConnected: () => connected };
}

const MIN = 60 * 1000;

describe("Flujo 5 e2e (5.1)", () => {
  it("WS cae -> buffer -> reconexion con last_event_id -> replay ordenado -> dedup exactly-once", async () => {
    const { factory, handshakes } = fakeChannel();
    const store = new InMemoryEventBufferStore();

    const backendPersisted = new Set<string>();
    const persistCount = new Map<string, number>();
    const replaySender: ReplaySender = async (r): Promise<ReplayAck> => {
      if (backendPersisted.has(r.id)) return { status: "duplicate", id: r.id };
      backendPersisted.add(r.id);
      persistCount.set(r.id, (persistCount.get(r.id) ?? 0) + 1);
      return { status: "persisted", id: r.id };
    };

    let clock = 1_000_000;
    const ch = new ResilientStudentEventChannel({
      store,
      channelFactory: factory,
      replaySender,
      nowMs: () => clock,
      scheduleImpl: (fn) => fn(), // ejecuta el reintento de inmediato (test)
    });
    await ch.connect();

    // 'a' se confirma online (simulamos que ya quedo persistido en backend)
    await ch.sendEvent({ id: "a", tipo: "x", severidad: "baja" });
    backendPersisted.add("a");

    // WS cae: 'b' y 'c' solo se bufferizan
    ch["channel"] = null as never;
    await ch.sendEvent({ id: "b", tipo: "x", severidad: "baja" });
    await ch.sendEvent({ id: "c", tipo: "x", severidad: "baja" });
    expect(await ch.pendingCount()).toBeGreaterThanOrEqual(2);

    clock += 30 * 1000; // corte de 30s (< 5 min)
    ch.handleDisconnect(); // backoff -> reconnect (scheduleImpl inmediato)
    // El replay drena el buffer con llamados async a replaySender; dos
    // `Promise.resolve()` no alcanzan a persistir 'b'/'c'. Un macrotask deja
    // resolver toda la cadena de reenvío antes de las aserciones.
    await new Promise((r) => setTimeout(r, 0));

    // handshake de reconexion lleva el last_event_id ('c', el ultimo producido)
    expect(handshakes[handshakes.length - 1]).toBe("c");

    // 'a' (ya persistido) se deduplica; 'b','c' se persisten exactamente una vez
    expect([...persistCount.values()].every((n) => n === 1)).toBe(true);
    expect(persistCount.has("b")).toBe(true);
    expect(persistCount.has("c")).toBe(true);
    // buffer drenado por completo (sin perdida ni residuo)
    expect(await ch.pendingCount()).toBe(0);
  });

  it("corte corto < 5 min: replay sin perdida, sin evento critico", async () => {
    const { factory } = fakeChannel();
    const store = new InMemoryEventBufferStore();
    const onProlongedOutage = vi.fn();
    const replaySender: ReplaySender = async (r) => ({ status: "persisted", id: r.id });

    let clock = 0;
    const ch = new ResilientStudentEventChannel({
      store,
      channelFactory: factory,
      replaySender,
      nowMs: () => clock,
      scheduleImpl: (fn) => fn(),
      onProlongedOutage,
    });
    await ch.connect();
    ch.markHeartbeat();
    await ch.sendEvent({ id: "e1", tipo: "x", severidad: "baja" });

    clock += 4 * MIN; // corte de 4 min
    await ch.reconnect();

    expect(onProlongedOutage).not.toHaveBeenCalled();
    expect(await ch.pendingCount()).toBe(0); // todo reenviado, sin perdida
  });

  it("corte largo > 5 min: emite evento critico SEÑAL, nunca sancion (L2.5)", async () => {
    const { factory } = fakeChannel();
    const store = new InMemoryEventBufferStore();
    let emitted: unknown = null;
    const replaySender: ReplaySender = async (r) => ({ status: "persisted", id: r.id });

    let clock = 0;
    const ch = new ResilientStudentEventChannel({
      store,
      channelFactory: factory,
      replaySender,
      nowMs: () => clock,
      scheduleImpl: (fn) => fn(),
      onProlongedOutage: (ev) => {
        emitted = ev;
      },
    });
    await ch.connect();
    ch.markHeartbeat();

    clock += 6 * MIN; // corte de 6 min
    await ch.reconnect();

    expect(emitted).not.toBeNull();
    const ev = emitted as Record<string, unknown>;
    expect(ev.tipo).toBe(PROLONGED_OUTAGE_EVENT_TIPO);
    expect(ev.severidad).toBe("critica");
    expect(ev.signal_only).toBe(true);
    // INVARIANTE L2.5: ningun rastro de sancion automatica
    expect(Object.keys(ev)).not.toContain("sancion");
  });
});

describe("backoff reinicia tras reconexion exitosa", () => {
  it("attempt vuelve a 0 luego de reconectar", async () => {
    const { factory } = fakeChannel();
    const store = new InMemoryEventBufferStore();
    const replaySender: ReplaySender = async (r) => ({ status: "persisted", id: r.id });
    let clock = 0;
    const ch = new ResilientStudentEventChannel({
      store,
      channelFactory: factory,
      replaySender,
      nowMs: () => clock,
      scheduleImpl: (fn) => fn(),
    });
    await ch.connect();
    ch.markHeartbeat();
    ch.handleDisconnect();
    await Promise.resolve();
    expect(ch.reconnectAttempt).toBe(0);
  });
});
