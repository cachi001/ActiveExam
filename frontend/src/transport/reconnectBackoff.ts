/**
 * Backoff exponencial + jitter del 20% para la reconexion del WS (C-14, RN-HB-05).
 *
 * Ante la caida del WebSocket, el cliente reconecta con intervalos que crecen
 * exponencialmente; cada intervalo se aleatoriza con un jitter del +-20% para
 * evitar el "thundering herd" de miles de clientes reconectando al unisono.
 *
 * Logica PURA: ``random`` es inyectable para testear el jitter de forma
 * determinista (sin DOM, sin reloj real).
 */

export const DEFAULT_BASE_DELAY_MS = 1000;
export const DEFAULT_MAX_DELAY_MS = 30_000;
/** Fraccion de jitter: +-20% (RN-HB-05). */
export const JITTER_FRACTION = 0.2;

export interface BackoffOptions {
  /** Retardo base del primer reintento (ms). */
  baseDelayMs?: number;
  /** Techo del retardo exponencial antes del jitter (ms). */
  maxDelayMs?: number;
  /** Fuente de aleatoriedad en [0,1); inyectable para tests. Default ``Math.random``. */
  random?: () => number;
}

/**
 * Retardo (ms) para el intento ``attempt`` (0-indexado).
 *
 * Exponencial acotado: ``base * 2^attempt`` saturado en ``maxDelayMs``; luego se
 * aplica un jitter multiplicativo en ``[1 - 0.2, 1 + 0.2]``. El primer intento
 * (``attempt`` 0) usa el retardo base. Nunca devuelve un valor negativo.
 */
export function backoffDelayMs(attempt: number, options: BackoffOptions = {}): number {
  const base = options.baseDelayMs ?? DEFAULT_BASE_DELAY_MS;
  const max = options.maxDelayMs ?? DEFAULT_MAX_DELAY_MS;
  const random = options.random ?? Math.random;

  const safeAttempt = Math.max(0, Math.floor(attempt));
  const exponential = Math.min(base * 2 ** safeAttempt, max);
  // jitter en [1 - f, 1 + f): random en [0,1) -> factor en [1-f, 1+f)
  const factor = 1 - JITTER_FRACTION + random() * (2 * JITTER_FRACTION);
  return Math.max(0, Math.round(exponential * factor));
}

/**
 * Limites [min, max] del retardo (sin jitter aplicado, con el jitter en sus
 * extremos) para el intento dado. Util en tests para acotar el rango esperado.
 */
export function backoffBounds(
  attempt: number,
  options: BackoffOptions = {},
): { min: number; max: number; nominal: number } {
  const base = options.baseDelayMs ?? DEFAULT_BASE_DELAY_MS;
  const max = options.maxDelayMs ?? DEFAULT_MAX_DELAY_MS;
  const safeAttempt = Math.max(0, Math.floor(attempt));
  const nominal = Math.min(base * 2 ** safeAttempt, max);
  return {
    min: Math.round(nominal * (1 - JITTER_FRACTION)),
    max: Math.round(nominal * (1 + JITTER_FRACTION)),
    nominal,
  };
}
