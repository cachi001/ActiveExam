/**
 * severityRanges — fuente única de los rangos institucionales de peso por
 * severidad. Sincronizado con el backend (SEVERITY_RANGES en
 * `app/domain/scoring/risk_score.py`).
 *
 * Las pantallas que muestran o editan pesos por evento (Configuración →
 * Scoring, Test Detección → CoverageChecklist) deben importar de acá — no
 * duplicar las tablas.
 */

import type { Severidad } from '../lib/types';

export type SeveridadEditable = Exclude<Severidad, 'baseline'>;

export interface RangoSeveridad {
  sev: SeveridadEditable;
  min: number;
  max: number;
}

/** Rangos ordenados de menor a mayor severidad. */
export const RANGOS_SEVERIDAD: readonly RangoSeveridad[] = [
  { sev: 'baja', min: 1, max: 10 },
  { sev: 'media', min: 11, max: 30 },
  { sev: 'alta', min: 31, max: 60 },
  { sev: 'critica', min: 61, max: 100 },
] as const;

/** Etiqueta capitalizada en español (no usar `capitalize` CSS porque "crítica"
 * tiene tilde que rompe el casing automático). */
export const SEV_LABEL: Record<SeveridadEditable, string> = {
  baja: 'Baja',
  media: 'Media',
  alta: 'Alta',
  critica: 'Crítica',
};

/** Severidad que corresponde a un peso (a más peso, más severa). */
export function severidadParaPeso(peso: number): SeveridadEditable {
  for (const r of RANGOS_SEVERIDAD) {
    if (peso <= r.max) return r.sev;
  }
  return 'critica';
}

/** Rango (min/max) de una severidad. */
export function rangoDeSeveridad(sev: SeveridadEditable): { min: number; max: number } {
  const r = RANGOS_SEVERIDAD.find((x) => x.sev === sev);
  return r ? { min: r.min, max: r.max } : { min: 1, max: 100 };
}

/** Clampea un peso al rango global válido (1..100). */
export function clampPeso(peso: number): number {
  if (peso < 1) return 1;
  if (peso > 100) return 100;
  return peso;
}
