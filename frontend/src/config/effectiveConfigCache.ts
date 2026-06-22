/**
 * effectiveConfigCache — cache de la config efectiva del sistema.
 *
 * Generaliza el patrón de `scoringWeights.ts` para toda la config efectiva.
 * Cachea por `version` (ETag del backend): si la version no cambió, no hay
 * round-trip innecesario.
 *
 * USO:
 *   import { loadEffectiveConfig, resetEffectiveConfigCache, getEffectiveConfig } from './effectiveConfigCache';
 *
 *   // Al iniciar el examen / harness:
 *   await loadEffectiveConfig();
 *   const cfg = getEffectiveConfig();
 *
 *   // Tras guardar config en el admin (invalida el cache):
 *   resetEffectiveConfigCache();
 */

import { api, patchDemoExamenFromConfig } from '../lib/api';
import { seedScoringWeights, seedScoringSeveridades, resetScoringWeightsCache as _resetScoringWeightsCache } from '../proctoring/scoringWeights';
import type { Severidad } from '../lib/types';
import { seedUmbralAlto } from '../screens/proctoring/helpers';

export interface ConfigEfectivaSnapshot {
  version: number;
  face_absent_ms: number;
  multiple_faces_frames: number;
  gaze_deviation_threshold: number;
  gaze_sustained_ms: number;
  gaze_fixation_tolerance: number;
  umbral_cola_revision: number;
  retencion_dias_default: number;
  consent_version_vigente: string;
  detectores_activos: string[];
  scoring_weights: Record<string, number>;
  // El backend devuelve strings; se castean a Severidad al sembrar el cache.
  scoring_severidades?: Record<string, string>;
}

// Cache en memoria — nulo hasta que se carga.
let _cache: ConfigEfectivaSnapshot | null = null;
// Promesa en vuelo (deduplicación de concurrentes).
let _inflight: Promise<void> | null = null;

/**
 * Carga la config efectiva desde el backend y la cachea.
 * Idempotente: si ya está cacheada (misma versión), no hace round-trip.
 * Si falla, el cache queda nulo y `getEffectiveConfig()` devuelve null.
 */
export async function loadEffectiveConfig(): Promise<void> {
  if (_cache !== null) return;
  if (_inflight) return _inflight;

  _inflight = (async () => {
    try {
      const data = await api.obtenerConfigEfectiva();
      _cache = data;
      // Siembra el cache de scoring weights con los pesos de la config efectiva.
      // Así, pesoEvento() usa los pesos vivos sin un segundo round-trip a /scoring/weights.
      if (data.scoring_weights && Object.keys(data.scoring_weights).length > 0) {
        seedScoringWeights(data.scoring_weights);
      }
      // Siembra las severidades configuradas por tipo (para mostrar la severidad
      // vigente en el log de eventos, no la del catalogo hardcodeado del cliente).
      if (data.scoring_severidades && Object.keys(data.scoring_severidades).length > 0) {
        seedScoringSeveridades(data.scoring_severidades as Record<string, Severidad>);
      }
      // Siembra el umbral de riesgo alto desde la config efectiva.
      // nivelRiesgo() y las vistas usan getUmbralAlto() en lugar del const hardcodeado.
      seedUmbralAlto(data.umbral_cola_revision);
      // En modo demo, actualiza el examen demo para que refleje la config actualizada.
      patchDemoExamenFromConfig({
        umbral_cola_revision: data.umbral_cola_revision,
        detectores_activos: data.detectores_activos,
        retencion_dias_default: data.retencion_dias_default,
      });
    } catch (err) {
      console.warn('[effectiveConfig] No se pudo cargar la config efectiva; usando fallback.', err);
      _cache = null;
    } finally {
      _inflight = null;
    }
  })();

  return _inflight;
}

/**
 * Devuelve el snapshot cacheado, o null si no fue cargado o la carga falló.
 * O(1) — no hace red.
 */
export function getEffectiveConfig(): ConfigEfectivaSnapshot | null {
  return _cache;
}

/**
 * Invalida el cache. Llamar tras guardar cualquier cambio de config en el admin.
 * La próxima llamada a `loadEffectiveConfig()` hará un nuevo fetch.
 * También invalida el cache de scoring weights para que pesoEvento() vuelva al
 * fallback hasta que el nuevo fetch siembre el nuevo mapa de pesos.
 */
export function resetEffectiveConfigCache(): void {
  _cache = null;
  _inflight = null;
  // Invalida también el cache de pesos de scoring (serán re-sembrados en el próximo load).
  _resetScoringWeightsCache();
}

/**
 * Alias de compatibilidad para los callers que usaban resetScoringWeightsCache().
 * Ambos nombres son válidos — prefiere `resetEffectiveConfigCache` para código nuevo.
 */
export { resetEffectiveConfigCache as resetScoringWeightsCache };
