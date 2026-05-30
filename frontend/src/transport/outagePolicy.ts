/**
 * Politica por duracion del corte de conectividad (C-14, RN-HB-04, RN-EV-04, D4/D5).
 *
 * El reloj del corte es la AUSENCIA de heartbeats (/5s de C-10): se mide el tiempo
 * entre el ultimo heartbeat confirmado y la reconexion. Umbral del dominio: 5 min.
 *  - corte <= 5 min  -> replay sin perdida, SIN evento adicional.
 *  - corte  > 5 min  -> ademas, evento CRITICO "corte de conectividad prolongado"
 *                       al reconectar.
 *
 * INVARIANTE L2.5 (RN-RV-07): el evento critico es SOLO una SEÑAL para el panel.
 * Esta funcion NUNCA deriva ni representa una sancion; no existe campo "sancion".
 *
 * Logica PURA: sin DOM, sin reloj real (recibe los instantes como argumentos).
 */

export const OUTAGE_THRESHOLD_MS = 5 * 60 * 1000; // 5 minutos

/** Tipo del evento critico emitido al reconectar tras un corte prolongado. */
export const PROLONGED_OUTAGE_EVENT_TIPO = "corte_conectividad_prolongado";

export interface ProlongedOutageEvent {
  tipo: typeof PROLONGED_OUTAGE_EVENT_TIPO;
  severidad: "critica";
  /** Duracion del corte en ms (para contexto del panel). */
  outage_ms: number;
  /** SEÑAL para el panel, nunca sancion (L2.5). Marca explicita y testeable. */
  signal_only: true;
}

/** Duracion (ms) del corte = reconexion - ultimo heartbeat. Nunca negativa. */
export function outageDurationMs(lastHeartbeatMs: number, reconnectMs: number): number {
  return Math.max(0, reconnectMs - lastHeartbeatMs);
}

/** True si el corte supero el umbral de 5 min (corte "largo"). */
export function isProlongedOutage(durationMs: number): boolean {
  return durationMs > OUTAGE_THRESHOLD_MS;
}

/**
 * Clasifica el corte al reconectar. Devuelve el evento critico a emitir SOLO si el
 * corte fue > 5 min; en cortes cortos devuelve ``null`` (replay sin evento extra).
 *
 * El evento, cuando existe, lleva ``signal_only: true`` y severidad ``critica``: es
 * una señal para el panel, jamas una sancion (L2.5, RN-RV-07).
 */
export function classifyOutage(
  lastHeartbeatMs: number,
  reconnectMs: number,
): ProlongedOutageEvent | null {
  const durationMs = outageDurationMs(lastHeartbeatMs, reconnectMs);
  if (!isProlongedOutage(durationMs)) return null;
  return {
    tipo: PROLONGED_OUTAGE_EVENT_TIPO,
    severidad: "critica",
    outage_ms: durationMs,
    signal_only: true,
  };
}
