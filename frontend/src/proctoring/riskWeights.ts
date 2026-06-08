/**
 * Pesos de score de riesgo por severidad (C-33).
 *
 * Fuente de verdad compartida entre Examen.tsx (examen real del alumno)
 * y AdminDetectionHarness.tsx (medidor de riesgo diagnóstico).
 *
 * **Alineado con el backend** (`app/application/proctoring/scoring.py::PESOS_SEVERIDAD`):
 *   bajo=5, medio=20, alto=50, critico=100.
 * El frontend usa severidades en femenino (baja/media/alta/critica) + baseline
 * y un mapeo en `api.enviarEventoProctoring` traduce a las del backend al enviar.
 * Los pesos numéricos deben ser idénticos en ambos lados para que el score que
 * muestra el harness coincida con el que la sesión presenta luego en Sesiones
 * grabadas / Detalle.
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
  media: 20,
  alta: 50,
  critica: 100,
};
