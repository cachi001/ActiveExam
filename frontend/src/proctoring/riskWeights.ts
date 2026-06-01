/**
 * Pesos de score de riesgo por severidad (C-33).
 *
 * Fuente de verdad compartida entre Examen.tsx (examen real del alumno)
 * y AdminDetectionHarness.tsx (medidor de riesgo diagnóstico).
 *
 * Los valores NO cambian: son parte del dominio de scoring del sistema.
 * Modificar estos pesos afecta TANTO el examen real como el harness.
 *
 * Semántica L2.5: estos pesos alimentan un acumulador de priorización,
 * NUNCA un veredicto automático. La decisión disciplinaria es siempre humana.
 */

import type { Severidad } from '../lib/types';

/**
 * Peso de score asignado a cada nivel de severidad.
 * El score se acumula y se capa a 100 (Math.min).
 */
export const PESO_SCORE: Record<Severidad, number> = {
  baseline: 0,
  baja: 5,
  media: 12,
  alta: 22,
  critica: 30,
};
