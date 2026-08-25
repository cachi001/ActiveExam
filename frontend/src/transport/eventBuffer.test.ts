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

// ---------------------------------------------------------------------------
// c-78: el buffer tiene que aguantar CAPTURAS, no solo eventos livianos.
//
// Una captura de incidente pesa ~114 KB en base64 (960x540, JPEG 0.7) y viaja
// DENTRO del payload del evento. Eso rompe tres supuestos del buffer original,
// que estaba pensado para mensajes de unos pocos KB.
// ---------------------------------------------------------------------------

/** Payload con un `screenshot_base64` de `kb` kilobytes, como el real. */
function eventoConCaptura(kb: number) {
  return { tipo: "rostro_ausente", screenshot_base64: "x".repeat(kb * 1024) };
}

describe("el orden no se corrompe al recargar la pagina", () => {
  it("un evento nuevo despues del reload va DESPUES de los que quedaron", async () => {
    // El caso real: se corta la conexion, el alumno recarga (o se le reinicia la
    // maquina) y sigue rindiendo. `nextSeq` arrancaba de cero en el buffer nuevo,
    // asi que los eventos post-reload se numeraban encima de los bufferizados y
    // el replay los reenviaba DESORDENADOS.
    const store = new InMemoryEventBufferStore();
    const b1 = new CircularEventBuffer(store);
    await b1.append("e1", {});
    await b1.append("e2", {});

    const b2 = new CircularEventBuffer(store); // reload: mismo store, buffer nuevo
    await b2.append("e3", {});

    expect((await b2.pending()).map((e) => e.id)).toEqual(["e1", "e2", "e3"]);
  });
});

describe("tope por PESO, no solo por cantidad", () => {
  it("el presupuesto en bytes acota el buffer mucho antes que la cantidad", async () => {
    // 10.000 registros de 114 KB serian 1,1 GB: mas de lo que ningun navegador
    // va a conceder. El techo que manda tiene que ser el peso.
    const store = new InMemoryEventBufferStore();
    const buffer = new CircularEventBuffer(store, 10_000, { maxBytes: 300 * 1024 });

    for (let i = 0; i < 5; i++) await buffer.append(`e${i}`, eventoConCaptura(114));

    const ids = (await buffer.pending()).map((e) => e.id);
    expect(ids.length).toBeLessThanOrEqual(2); // ~114 KB cada uno en 300 KB
    expect(ids).toContain("e4"); // el ultimo SIEMPRE entra
    expect(ids).not.toContain("e0"); // el mas viejo salio
  });

  it("libera presupuesto al confirmar, sin necesidad de expulsar", async () => {
    const store = new InMemoryEventBufferStore();
    const buffer = new CircularEventBuffer(store, 10_000, { maxBytes: 300 * 1024 });

    await buffer.append("e0", eventoConCaptura(114));
    await buffer.append("e1", eventoConCaptura(114));
    await buffer.confirm("e0"); // el POST salio bien: deja de ocupar
    await buffer.append("e2", eventoConCaptura(114));

    expect((await buffer.pending()).map((e) => e.id)).toEqual(["e1", "e2"]);
  });
});

describe("costo de guardar un evento", () => {
  it("no deserializa el buffer entero en cada append", async () => {
    // `append` hacia `getAllOrdered()` siempre: con capturas adentro, guardar el
    // evento numero 50 significaba leer y parsear 5,7 MB de base64. En el examen
    // real eso corre en el hilo principal, encima del examen del alumno.
    const store = new InMemoryEventBufferStore();
    let lecturasCompletas = 0;
    const original = store.getAllOrdered.bind(store);
    store.getAllOrdered = async () => {
      lecturasCompletas += 1;
      return original();
    };
    const buffer = new CircularEventBuffer(store);

    for (let i = 0; i < 20; i++) await buffer.append(`e${i}`, eventoConCaptura(114));

    expect(lecturasCompletas).toBeLessThanOrEqual(1); // a lo sumo el scan de arranque
  });
});

describe("cuando el navegador se niega a guardar, se avisa", () => {
  it("no se traga el error de cuota: lo reporta y no rompe el examen", async () => {
    // Antes: `append(...).catch(() => {})` en el llamador. Si IndexedDB tiraba
    // QuotaExceededError, no se guardaba NADA y nadie se enteraba: el alumno
    // seguia rindiendo creyendo que su evidencia estaba a salvo.
    const store = new InMemoryEventBufferStore();
    store.put = async () => {
      throw new DOMException("cuota agotada", "QuotaExceededError");
    };
    const avisos: string[] = [];
    const buffer = new CircularEventBuffer(store, 10_000, {
      alAvisar: (motivo) => avisos.push(motivo),
    });

    await expect(buffer.append("e1", eventoConCaptura(114))).resolves.toBeUndefined();
    expect(avisos).toContain("sin-espacio");
  });

  it("avisa tambien cuando tuvo que expulsar evidencia por presupuesto", async () => {
    const store = new InMemoryEventBufferStore();
    const avisos: string[] = [];
    const buffer = new CircularEventBuffer(store, 10_000, {
      maxBytes: 150 * 1024,
      alAvisar: (motivo) => avisos.push(motivo),
    });

    await buffer.append("e0", eventoConCaptura(114));
    expect(avisos).toEqual([]); // entra sin expulsar a nadie
    await buffer.append("e1", eventoConCaptura(114)); // expulsa e0

    expect(avisos).toContain("expulsado");
  });
});
