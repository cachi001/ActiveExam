/**
 * scoringWeights — fuente unica de pesos por tipo de evento.
 *
 * Reemplaza el hardcoded `PESO_SCORE` (por severidad) de `riskWeights.ts`. Los
 * pesos se leen de la BD (`evento_score_config`, migracion 0011) via el endpoint
 * `GET /api/v1/scoring/weights` y se cachean en memoria por la duracion de la
 * sesion del navegador.
 *
 * Politicas:
 *  - Tipos activos -> usan su peso configurado.
 *  - Tipos inactivos / no en la BD -> se loguea el evento pero suma 0 al score
 *    (la prioridad de la cola sigue siendo del backend, no del cliente).
 *  - Si la API falla (red caida, 401, etc.) -> fallback al mapa por severidad
 *    de `riskWeights.ts` para que el examen siga corriendo.
 *
 * Llamar `loadScoringWeights()` UNA vez al iniciar el examen / harness; despues
 * `pesoEvento(tipo, severidad)` es O(1) sin red.
 */

import type { Severidad } from '../lib/types';
import { api } from '../lib/api';
import { PESO_SCORE } from './riskWeights';

// Mapa { tipo_evento -> peso } (solo tipos ACTIVOS).
let weightsByTipo: Record<string, number> | null = null;
// Promesa en vuelo para deduplicar llamadas concurrentes al iniciar.
let inflight: Promise<void> | null = null;

/**
 * Descarga el mapa de pesos desde el backend y lo cachea. Idempotente:
 * llamadas concurrentes comparten la misma promesa. No bloquea — si falla,
 * deja el cache nulo y los callers recurren al fallback por severidad.
 */
export async function loadScoringWeights(): Promise<void> {
  if (weightsByTipo !== null) return;
  if (inflight) return inflight;
  inflight = (async () => {
    try {
      const res = await api.obtenerScoringWeights();
      weightsByTipo = res.weights;
    } catch (err) {
      // Mantener cache nulo: pesoEvento() caera al fallback por severidad.
      console.warn('[scoring] No se pudieron cargar pesos del backend; usando fallback por severidad.', err);
      weightsByTipo = null;
    } finally {
      inflight = null;
    }
  })();
  return inflight;
}

/**
 * Resetea el cache. Util para tests o para forzar una recarga manual desde la
 * pantalla admin (#10) cuando admin guarda un cambio.
 */
export function resetScoringWeightsCache(): void {
  weightsByTipo = null;
  inflight = null;
}

/**
 * Peso del evento (0-100) que se suma al score acumulado.
 *
 * Orden de resolucion:
 *   1. Cache cargado y el tipo esta activo en la BD -> usa ese peso.
 *   2. Cache cargado pero el tipo NO esta (inactivo / no existe) -> 0.
 *   3. Cache vacio (no se llamo loadScoringWeights, o fallo la API) -> fallback
 *      al peso por severidad de riskWeights.ts.
 */
export function pesoEvento(tipo: string, severidad: Severidad): number {
  if (weightsByTipo !== null) {
    return weightsByTipo[tipo] ?? 0;
  }
  return PESO_SCORE[severidad] ?? 0;
}

/**
 * Devuelve el snapshot actual del cache (o null si no se cargo). Util para
 * pantallas que necesitan mostrar los pesos sin volver a pedir a la API.
 */
export function snapshotPesos(): Record<string, number> | null {
  return weightsByTipo === null ? null : { ...weightsByTipo };
}
