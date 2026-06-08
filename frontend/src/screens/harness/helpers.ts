/**
 * Helpers puros del AdminDetectionHarness (C-23).
 *
 * Validación de TransitionConfig, formato de timestamps y colores del gauge.
 * Extraídos sin cambios desde AdminDetectionHarness.tsx.
 */

import type { TransitionConfig } from '../../proctoring/stateTransitionRules';
import type { Severidad } from '../../lib/types';
import type { ConfigErrors } from './types';

// ---------------------------------------------------------------------------
// Validación de TransitionConfig
// ---------------------------------------------------------------------------

export function validateConfig(cfg: TransitionConfig): ConfigErrors {
  const errors: ConfigErrors = {};
  const positiveFields: Array<keyof TransitionConfig> = [
    'face_absent_ms',
    'multiple_faces_frames',
    'gaze_deviation_threshold',
    'gaze_sustained_ms',
    'gaze_fixation_tolerance',
  ];
  for (const field of positiveFields) {
    const v = cfg[field];
    if (typeof v !== 'number' || isNaN(v)) {
      errors[field] = 'Debe ser un número válido';
    } else if (v <= 0) {
      errors[field] = 'Debe ser mayor a 0';
    }
  }
  return errors;
}

// ---------------------------------------------------------------------------
// Helpers de presentación
// ---------------------------------------------------------------------------

export function formatRelativeTs(eventTs: number, sessionStart: number): string {
  const diff = Math.max(0, eventTs - sessionStart);
  const s = Math.floor(diff / 1000);
  const ms = diff % 1000;
  return `+${s}.${String(ms).padStart(3, '0')}s`;
}

export const SEVERITY_ORDER: Severidad[] = ['baseline', 'baja', 'media', 'alta', 'critica'];

export const SEVERITY_BADGE_COLORS: Record<Severidad, string> = {
  baseline: 'bg-surface-container-high text-on-surface-variant',
  baja: 'bg-success-container text-success',
  media: 'bg-warning-container text-warning',
  alta: 'bg-error-container text-on-error-container',
  critica: 'bg-error text-on-error',
};

/**
 * Clases de Tailwind para pintar la CARD de un evento del log con un fondo
 * suave matching la severidad + un acento de borde izquierdo. Asi se distinguen
 * visualmente sin recargar (las cards grises deprimian la lectura).
 */
export const SEVERITY_CARD_COLORS: Record<Severidad, string> = {
  baseline: 'bg-surface-container-low/60 border-outline-variant/40 border-l-4 border-l-outline-variant',
  baja: 'bg-success-container/30 border-success/20 border-l-4 border-l-success',
  media: 'bg-warning-container/40 border-warning/30 border-l-4 border-l-warning',
  alta: 'bg-error-container/40 border-error/30 border-l-4 border-l-error',
  critica: 'bg-error/15 border-error/50 border-l-4 border-l-error',
};

/**
 * Rangos de score por nivel de severidad — usado por la Leyenda visual.
 * Los pesos se mapean a "rango acumulable" (peso del evento + bono persistencia).
 * Coherente con PESO_SCORE de riskWeights.ts (0/5/20/50/100).
 */
export const SEVERITY_RANGES: Record<Severidad, { label: string; descripcion: string; peso: number }> = {
  baseline: { label: 'Base', descripcion: 'Sin riesgo: estado normal del examen.', peso: 0 },
  baja: { label: 'Baja', descripcion: 'Ruido leve: gestos breves, oclusiones momentaneas.', peso: 5 },
  media: { label: 'Media', descripcion: 'Patron a observar: cambio de pestana, foco perdido, copiar/pegar.', peso: 20 },
  alta: { label: 'Alta', descripcion: 'Incidencia clara: monitor adicional, multiples rostros.', peso: 50 },
  critica: { label: 'Critica', descripcion: 'Incidente bloqueante: requiere intervencion inmediata.', peso: 100 },
};

// ---------------------------------------------------------------------------
// C-33: Helpers de color del gauge de riesgo
// ---------------------------------------------------------------------------

/**
 * Devuelve la clase Tailwind de fondo para la barra de progreso del gauge.
 * - score >= threshold → rojo (bg-error)
 * - score >= threshold * 0.7 → amarillo (bg-warning)
 * - por defecto → verde (bg-success)
 */
export function gaugeColor(score: number, threshold: number): string {
  if (score >= threshold) return 'bg-error';
  if (score >= threshold * 0.7) return 'bg-warning';
  return 'bg-success';
}

/**
 * Devuelve la clase Tailwind de color de texto para el porcentaje del gauge.
 */
export function gaugeTextColor(score: number, threshold: number): string {
  if (score >= threshold) return 'text-error';
  if (score >= threshold * 0.7) return 'text-warning';
  return 'text-success';
}
