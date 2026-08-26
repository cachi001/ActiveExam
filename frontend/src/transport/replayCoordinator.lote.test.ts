/**
 * Drenaje EN LOTE del buffer al reconectar (c-78 §16.1f).
 *
 * Por qué: el drenaje mandaba un evento por request y esperaba el ack de cada
 * uno. Medido contra Render el 26/8/2026, una caída de 30 s tardaba 35,6 s de
 * media en drenarse (hasta 1m01s), porque el plan free responde a 3 a 5 s por
 * request y el drenaje los paga en serie. No se perdía evidencia, pero durante
 * esos 35 s el alumno podía cerrar la pestaña y llevarse lo que faltaba.
 *
 * `drainAndReplayEnLote` manda tandas en un solo request. Lo que hay que
 * sostener, y es lo que cubre este archivo:
 *   - el ORDEN de producción se respeta (es el contrato del replay)
 *   - solo se purga lo que el backend confirmó, nunca lo que no llegó
 *   - una tanda que falla no se da por enviada
 *   - el tamaño de tanda se respeta (el servidor tiene tope duro)
 */

import { describe, expect, it } from "vitest";

import { CircularEventBuffer, InMemoryEventBufferStore } from "./eventBuffer";
import {
  drainAndReplayEnLote,
  type LoteSender,
} from "./replayCoordinator";

function setup() {
  const store = new InMemoryEventBufferStore();
  const buffer = new CircularEventBuffer(store);
  return { store, buffer };
}

async function conPendientes(n: number) {
  const { buffer } = setup();
  for (let i = 0; i < n; i++) await buffer.append(`e${i}`, { n: i });
  return buffer;
}

describe("drenaje en lote", () => {
  it("manda todo junto en un solo request cuando entra en una tanda", async () => {
    const buffer = await conPendientes(5);
    const tandas: string[][] = [];
    const send: LoteSender = async (records) => {
      tandas.push(records.map((r) => r.id));
      return records.map((r) => ({ status: "persisted" as const, id: r.id }));
    };

    const res = await drainAndReplayEnLote(buffer, send);

    expect(tandas).toEqual([["e0", "e1", "e2", "e3", "e4"]]);
    expect(res.persisted).toEqual(["e0", "e1", "e2", "e3", "e4"]);
    expect(await buffer.size()).toBe(0);
  });

  it("respeta el orden de producción dentro de la tanda", async () => {
    const buffer = await conPendientes(4);
    let recibidos: string[] = [];
    const send: LoteSender = async (records) => {
      recibidos = records.map((r) => r.id);
      return records.map((r) => ({ status: "persisted" as const, id: r.id }));
    };

    await drainAndReplayEnLote(buffer, send);

    expect(recibidos).toEqual(["e0", "e1", "e2", "e3"]);
  });

  it("parte en tandas del tamaño pedido, en orden", async () => {
    const buffer = await conPendientes(7);
    const tandas: string[][] = [];
    const send: LoteSender = async (records) => {
      tandas.push(records.map((r) => r.id));
      return records.map((r) => ({ status: "persisted" as const, id: r.id }));
    };

    await drainAndReplayEnLote(buffer, send, { tamanoTanda: 3 });

    expect(tandas).toEqual([
      ["e0", "e1", "e2"],
      ["e3", "e4", "e5"],
      ["e6"],
    ]);
  });

  it("no purga nada si la tanda falla", async () => {
    const buffer = await conPendientes(3);
    const send: LoteSender = async () => {
      throw new Error("se cayó la red de nuevo");
    };

    await expect(drainAndReplayEnLote(buffer, send)).rejects.toThrow();
    expect(await buffer.size()).toBe(3);
  });

  it("una tanda que falla no se lleva puesta la anterior, que sí llegó", async () => {
    const buffer = await conPendientes(4);
    let vuelta = 0;
    const send: LoteSender = async (records) => {
      vuelta++;
      if (vuelta === 2) throw new Error("se cayó la red en la segunda tanda");
      return records.map((r) => ({ status: "persisted" as const, id: r.id }));
    };

    await expect(
      drainAndReplayEnLote(buffer, send, { tamanoTanda: 2 }),
    ).rejects.toThrow();

    // Los dos primeros ya están a salvo en el backend: purgarlos es correcto.
    // Los dos que no llegaron TIENEN que seguir en el buffer.
    expect(await buffer.size()).toBe(2);
    const quedan = (await buffer.pending()).map((r) => r.id);
    expect(quedan).toEqual(["e2", "e3"]);
  });

  it("un ack duplicate también purga: el evento ya está a salvo", async () => {
    const buffer = await conPendientes(2);
    const send: LoteSender = async (records) =>
      records.map((r) => ({ status: "duplicate" as const, id: r.id }));

    const res = await drainAndReplayEnLote(buffer, send);

    expect(res.deduplicated).toEqual(["e0", "e1"]);
    expect(await buffer.size()).toBe(0);
  });

  it("sin pendientes no toca la red", async () => {
    const { buffer } = setup();
    let llamadas = 0;
    const send: LoteSender = async (records) => {
      llamadas++;
      return records.map((r) => ({ status: "persisted" as const, id: r.id }));
    };

    const res = await drainAndReplayEnLote(buffer, send);

    expect(llamadas).toBe(0);
    expect(res.sentInOrder).toEqual([]);
  });

  it("si el backend devuelve menos acks que eventos, no se purga de más", async () => {
    // El servidor podría cortar la respuesta a mitad de camino. Purgar por
    // posición sin verificar dejaría eventos borrados que nunca se persistieron.
    const buffer = await conPendientes(3);
    const send: LoteSender = async (records) => [
      { status: "persisted" as const, id: records[0].id },
    ];

    const res = await drainAndReplayEnLote(buffer, send);

    expect(res.persisted).toEqual(["e0"]);
    expect(await buffer.size()).toBe(2);
  });
});
