/**
 * Metricas de la resiliencia de transporte (C-14, DD-12, RN-GLB-05).
 *
 * Contadores/medidas para observabilidad del buffer y la reconexion: tamaño del
 * buffer, reconexiones, eventos reenviados, duplicados deduplicados y cortes
 * prolongados (> 5 min). Estructura PURA y serializable; el sink (Prometheus,
 * OpenTelemetry, etc.) se conecta aparte — aca solo se acumulan.
 */

export interface ResilienceMetrics {
  /** Tamaño actual del buffer (gauge). */
  buffer_size: number;
  /** Total de reconexiones realizadas (counter). */
  reconnections_total: number;
  /** Eventos reenviados durante replays (counter). */
  events_replayed_total: number;
  /** Duplicados que el backend dedup-eo (counter). */
  duplicates_deduplicated_total: number;
  /** Cortes > 5 min detectados (counter). */
  prolonged_outages_total: number;
}

export function newResilienceMetrics(): ResilienceMetrics {
  return {
    buffer_size: 0,
    reconnections_total: 0,
    events_replayed_total: 0,
    duplicates_deduplicated_total: 0,
    prolonged_outages_total: 0,
  };
}

export function recordReconnection(m: ResilienceMetrics): void {
  m.reconnections_total += 1;
}

export function recordReplay(
  m: ResilienceMetrics,
  result: { persisted: string[]; deduplicated: string[] },
): void {
  m.events_replayed_total += result.persisted.length + result.deduplicated.length;
  m.duplicates_deduplicated_total += result.deduplicated.length;
}

export function recordProlongedOutage(m: ResilienceMetrics): void {
  m.prolonged_outages_total += 1;
}

export function setBufferSize(m: ResilienceMetrics, size: number): void {
  m.buffer_size = size;
}
