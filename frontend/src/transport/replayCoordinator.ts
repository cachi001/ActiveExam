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

/** Envia una TANDA completa y resuelve con un ack por evento, en la misma posicion. */
export type LoteSender = (records: BufferedEvent[]) => Promise<ReplayAck[]>;

/** Cuantos eventos van por request. El backend tiene un tope duro de 200. */
const TAMANO_TANDA_DEFAULT = 50;

export interface OpcionesLote {
  tamanoTanda?: number;
}

/**
 * Drena el buffer EN TANDAS: un request por tanda en vez de uno por evento.
 *
 * Por que (c-78 §16.1f): de a uno, el drenaje espera el ack de cada evento.
 * Medido contra Render el 26/8/2026, una caida de 30 s tardaba **35,6 s de media
 * y hasta 1m01s** en drenarse — el plan free responde a 3 a 5 s por request y el
 * drenaje los paga en serie. No se perdia evidencia, pero durante esos 35 s el
 * alumno podia cerrar la pestana y llevarse lo que faltaba mandar.
 *
 * Mantiene las MISMAS garantias que `drainAndReplay`:
 *   - orden de produccion (las tandas van en orden y cada una respeta su orden)
 *   - purga SOLO lo confirmado, y por id, nunca por posicion a ciegas: si el
 *     backend devuelve menos acks que eventos, lo que no vino sigue en el buffer
 *   - una tanda que falla no se da por enviada, y no se lleva puesta la anterior
 */
export async function drainAndReplayEnLote(
  buffer: CircularEventBuffer,
  send: LoteSender,
  opciones: OpcionesLote = {},
): Promise<ReplayResult> {
  const tamano = Math.max(1, opciones.tamanoTanda ?? TAMANO_TANDA_DEFAULT);
  const pending = await buffer.pending(); // ordenado por seq
  const result: ReplayResult = { sentInOrder: [], persisted: [], deduplicated: [] };

  for (let i = 0; i < pending.length; i += tamano) {
    const tanda = pending.slice(i, i + tamano);
    // Si esto tira, la excepcion sube SIN purgar la tanda: lo que no se confirmo
    // queda en el buffer para el proximo intento. Las tandas anteriores ya
    // confirmadas quedan purgadas, que es correcto: ya estan a salvo.
    const acks = await send(tanda);

    const porId = new Map(acks.map((a) => [a.id, a]));
    for (const record of tanda) {
      const ack = porId.get(record.id);
      if (!ack) continue; // el backend no lo confirmo: se queda en el buffer
      result.sentInOrder.push(record.id);
      if (ack.status === "persisted") result.persisted.push(record.id);
      else result.deduplicated.push(record.id);
      await buffer.confirm(record.id);
    }
  }

  return result;
}
