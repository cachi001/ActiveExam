/**
 * Tests del buffer circular de eventos (C-14, RN-HB-02, D1). Formato Vitest.
 *
 * Verifica: persistencia del evento en buffer, guardado mientras el WS esta caido,
 * supervivencia a "reload" (re-leer del mismo store simulando reapertura), buffer
 * circular acotado, orden por seq, idempotencia por id y purga post-confirmacion.
 */

import { describe, expect, it } from "vitest";

import {
  CircularEventBuffer,
  InMemoryEventBufferStore,
} from "./eventBuffer";

function buf(capacity?: number) {
  const store = new InMemoryEventBufferStore();
  return { store, buffer: new CircularEventBuffer(store, capacity) };
}

describe("persistencia en buffer", () => {
  it("persiste un evento en el buffer (1.1)", async () => {
    const { buffer } = buf();
    await buffer.append("e1", { id: "e1", tipo: "x" });
    const pending = await buffer.pending();
    expect(pending).toHaveLength(1);
    expect(pending[0].id).toBe("e1");
    expect(pending[0].message).toEqual({ id: "e1", tipo: "x" });
  });

  it("guarda los eventos mientras el WS esta caido, sin perdida (1.2)", async () => {
    const { buffer } = buf();
    // WS caido => el llamador solo bufferiza (no envia); el buffer no pierde nada
    for (let i = 0; i < 5; i++) await buffer.append(`e${i}`, { id: `e${i}` });
    expect(await buffer.size()).toBe(5);
  });
});

describe("supervivencia a refresh/cierre (1.3)", () => {
  it("los eventos siguen disponibles re-abriendo el store (simula reload)", async () => {
    const store = new InMemoryEventBufferStore();
    const b1 = new CircularEventBuffer(store);
    await b1.append("e1", { id: "e1" });
    await b1.append("e2", { id: "e2" });
    // "reload": nuevo buffer sobre el MISMO store (en prod, IndexedDB persistente)
    const b2 = new CircularEventBuffer(store);
    const pending = await b2.pending();
    expect(pending.map((e) => e.id)).toEqual(["e1", "e2"]);
  });
});

describe("buffer circular acotado (1.4)", () => {
  it("no crece sin techo: descarta el mas viejo al superar la capacidad", async () => {
    const { buffer } = buf(3);
    await buffer.append("e1", {});
    await buffer.append("e2", {});
    await buffer.append("e3", {});
    await buffer.append("e4", {}); // expulsa e1
    const ids = (await buffer.pending()).map((e) => e.id);
    expect(ids).toEqual(["e2", "e3", "e4"]);
    expect(await buffer.size()).toBe(3);
  });
});

describe("orden e idempotencia", () => {
  it("mantiene el orden de produccion por seq", async () => {
    const { buffer } = buf();
    await buffer.append("a", {});
    await buffer.append("b", {});
    await buffer.append("c", {});
    expect((await buffer.pending()).map((e) => e.id)).toEqual(["a", "b", "c"]);
  });

  it("re-bufferizar el mismo id no duplica (idempotente)", async () => {
    const { buffer } = buf();
    await buffer.append("a", { v: 1 });
    await buffer.append("a", { v: 2 });
    const pending = await buffer.pending();
    expect(pending).toHaveLength(1);
  });
});

describe("purga post-confirmacion (3.4)", () => {
  it("confirm() borra solo el evento confirmado", async () => {
    const { buffer } = buf();
    await buffer.append("a", {});
    await buffer.append("b", {});
    await buffer.confirm("a");
    expect((await buffer.pending()).map((e) => e.id)).toEqual(["b"]);
  });
});
