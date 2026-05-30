/**
 * Tests de las metricas de resiliencia (C-14, DD-12, RN-GLB-05). Formato Vitest.
 *
 * Verifica que los contadores reflejen reconexiones, replays, duplicados
 * deduplicados, cortes prolongados y el tamaño del buffer.
 */

import { describe, expect, it } from "vitest";

import {
  newResilienceMetrics,
  recordProlongedOutage,
  recordReconnection,
  recordReplay,
  setBufferSize,
} from "./resilienceMetrics";

describe("metricas de resiliencia (5.2)", () => {
  it("arranca en cero", () => {
    const m = newResilienceMetrics();
    expect(m).toEqual({
      buffer_size: 0,
      reconnections_total: 0,
      events_replayed_total: 0,
      duplicates_deduplicated_total: 0,
      prolonged_outages_total: 0,
    });
  });

  it("acumula reconexiones, replays, duplicados y cortes largos", () => {
    const m = newResilienceMetrics();
    recordReconnection(m);
    recordReconnection(m);
    recordReplay(m, { persisted: ["a", "b"], deduplicated: ["c"] });
    recordProlongedOutage(m);
    setBufferSize(m, 7);

    expect(m.reconnections_total).toBe(2);
    expect(m.events_replayed_total).toBe(3); // 2 persisted + 1 dedup
    expect(m.duplicates_deduplicated_total).toBe(1);
    expect(m.prolonged_outages_total).toBe(1);
    expect(m.buffer_size).toBe(7);
  });
});
