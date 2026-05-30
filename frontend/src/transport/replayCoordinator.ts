/**
 * Coordinador de replay ordenado + deduplicacion exactly-once logico (C-14,
 * RN-HB-03, Flujo 5, D3).
 *
 * Al reconectar, el cliente:
 *   1. Drena el buffer IndexedDB EN ORDEN (seq ascendente) reenviando los
 *      pendientes — sin alterar la secuencia de produccion.
 *   2. Marca como confirmado y PURGA del buffer SOLO lo que el backend confirma
 *      como persistido (ack), de modo que un evento ya persistido reenviado no
 *      genere duplicado: la AUTORIDAD de deduplicacion es el backend (por
 *      ``event_id``), no el cliente (D3).
 *
 * El backend ya conoce ``last_event_id`` (handshake de C-10) y deduplica por
 * ``event_id`` contra la hypertable: reenviar un evento ya persistido devuelve
 * ack "duplicate" -> se purga igual (ya esta a salvo), exactly-once logico.
 *
 * Logica PURA respecto del transporte: ``sender`` (que envia y espera ack) es
 * inyectable; el buffer esta detras de su propio puerto. Sin DOM.
 */

import type { BufferedEvent, CircularEventBuffer } from "./eventBuffer";

/** Resultado del envio de un evento durante el replay (lo decide el backend). */
export type ReplayAck =
  | { status: "persisted"; id: string }
  | { status: "duplicate"; id: string };

/** Envia un evento bufferizado y resuelve con el ack del backend. */
export type ReplaySender = (record: BufferedEvent) => Promise<ReplayAck>;

export interface ReplayResult {
  /** Eventos enviados, en el orden en que se drenaron. */
  sentInOrder: string[];
  /** Eventos que el backend reporto como recien persistidos. */
  persisted: string[];
  /** Eventos que el backend reconocio como duplicados (ya estaban). */
  deduplicated: string[];
}

/**
 * Drena el buffer en orden, reenvia cada pendiente y purga los confirmados
 * (persisted o duplicate). Garantiza exactly-once logico: ni perdida (todo lo
 * pendiente se reenvia) ni duplicados (el backend deduplica por ``event_id`` y el
 * cliente purga ambos casos).
 */
export async function drainAndReplay(
  buffer: CircularEventBuffer,
  send: ReplaySender,
): Promise<ReplayResult> {
  const pending = await buffer.pending(); // ya ordenado por seq (orden de produccion)
  const result: ReplayResult = { sentInOrder: [], persisted: [], deduplicated: [] };

  for (const record of pending) {
    const ack = await send(record);
    result.sentInOrder.push(record.id);
    if (ack.status === "persisted") result.persisted.push(record.id);
    else result.deduplicated.push(record.id);
    // En ambos casos el evento ya esta a salvo en el backend -> purgar del buffer.
    await buffer.confirm(record.id);
  }

  return result;
}
