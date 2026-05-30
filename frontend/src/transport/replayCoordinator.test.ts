/**
 * Tests del replay ordenado + dedup exactly-once logico (C-14, RN-HB-03).
 * Formato Vitest.
 *
 * Verifica: drenaje en orden (3.1), reenvio de id ya persistido no duplica (3.2),
 * replay completo con solape -> exactly-once (3.3), purga post-confirmacion (3.4).
 */

import { describe, expect, it } from "vitest";

import {
  CircularEventBuffer,
  InMemoryEventBufferStore,
} from "./eventBuffer";
import { drainAndReplay, type ReplayAck, type ReplaySender } from "./replayCoordinator";

function setup() {
  const store = new InMemoryEventBufferStore();
  const buffer = new CircularEventBuffer(store);
  return { store, buffer };
}

describe("drenaje en orden (3.1)", () => {
  it("reenvia los pendientes en el orden de produccion", async () => {
    const { buffer } = setup();
    await buffer.append("a", {});
    await buffer.append("b", {});
    await buffer.append("c", {});

    const seen: string[] = [];
    const send: ReplaySender = async (r) => {
      seen.push(r.id);
      return { status: "persisted", id: r.id };
    };
    const res = await drainAndReplay(buffer, send);
    expect(seen).toEqual(["a", "b", "c"]);
    expect(res.sentInOrder).toEqual(["a", "b", "c"]);
  });
});

describe("dedup por event_id (3.2)", () => {
  it("un id que el backend marca duplicate no cuenta como persistido", async () => {
    const { buffer } = setup();
    await buffer.append("a", {});
    const send: ReplaySender = async (r) => ({ status: "duplicate", id: r.id });
    const res = await drainAndReplay(buffer, send);
    expect(res.deduplicated).toEqual(["a"]);
    expect(res.persisted).toEqual([]);
    // igualmente se purga del buffer (ya esta a salvo en backend)
    expect(await buffer.size()).toBe(0);
  });
});

describe("replay completo con solape -> exactly-once (3.3)", () => {
  it("eventos ya confirmados se deduplican y los nuevos se persisten una vez", async () => {
    const { buffer } = setup();
    // a,b ya estaban persistidos (solape); c,d son nuevos
    for (const id of ["a", "b", "c", "d"]) await buffer.append(id, {});
    const alreadyPersisted = new Set(["a", "b"]);
    const persistedCount = new Map<string, number>();

    const send: ReplaySender = async (r): Promise<ReplayAck> => {
      if (alreadyPersisted.has(r.id)) return { status: "duplicate", id: r.id };
      persistedCount.set(r.id, (persistedCount.get(r.id) ?? 0) + 1);
      return { status: "persisted", id: r.id };
    };

    const res = await drainAndReplay(buffer, send);
    expect(res.deduplicated).toEqual(["a", "b"]);
    expect(res.persisted).toEqual(["c", "d"]);
    // exactly-once: cada nuevo se persiste UNA sola vez; nada se pierde
    expect([...persistedCount.values()].every((n) => n === 1)).toBe(true);
    expect(await buffer.size()).toBe(0); // buffer drenado por completo
  });
});

describe("purga post-confirmacion (3.4)", () => {
  it("solo purga lo efectivamente confirmado; si el envio falla, queda en buffer", async () => {
    const { buffer } = setup();
    await buffer.append("a", {});
    await buffer.append("b", {});

    // 'b' falla el envio -> debe permanecer en el buffer para reintento
    const send: ReplaySender = async (r) => {
      if (r.id === "b") throw new Error("network");
      return { status: "persisted", id: r.id };
    };

    await expect(drainAndReplay(buffer, send)).rejects.toThrow("network");
    const remaining = (await buffer.pending()).map((e) => e.id);
    expect(remaining).toContain("b"); // no se perdio
    expect(remaining).not.toContain("a"); // 'a' si se confirmo y purgo
  });
});
