/**
 * Lógica pura de navegación de preguntas en el examen (C-69).
 *
 * Exportada separadamente de Examen.tsx para poder testarla sin renderizar
 * el componente (sin @testing-library/react). Funciones puras, sin side effects.
 */

import type { PreguntaRendicion } from '../lib/examTakingApi';

/** Retorna true si el alumno puede ir a la pregunta anterior (no está en la primera). */
export function puedeIrAnterior(indice: number): boolean {
  return indice > 0;
}

/** Retorna true si el alumno puede ir a la siguiente pregunta (no está en la última). */
export function puedeIrSiguiente(indice: number, totalPreguntas: number): boolean {
  return indice < totalPreguntas - 1;
}

/** Avanza al índice siguiente, clampea en el límite superior. */
export function avanzarPregunta(indice: number, totalPreguntas: number): number {
  return Math.min(indice + 1, Math.max(0, totalPreguntas - 1));
}

/** Retrocede al índice anterior, clampea en 0. */
export function retrocederPregunta(indice: number): number {
  return Math.max(indice - 1, 0);
}

/** Obtiene la pregunta en el índice actual. null si no hay preguntas. */
export function preguntaEnIndice(
  preguntas: PreguntaRendicion[],
  indice: number,
): PreguntaRendicion | null {
  if (preguntas.length === 0) return null;
  const idx = Math.min(Math.max(indice, 0), preguntas.length - 1);
  return preguntas[idx];
}

/**
 * Retorna el conjunto de índices 0-based de las preguntas que tienen una
 * respuesta seleccionada en el mapa `respuestas`.
 *
 * Usado por QuestionNavigator para colorear los botones respondidos.
 */
export function indicesRespondidos(
  preguntas: Array<{ id: number | string }>,
  respuestas: Record<string | number, number | string>,
): Set<number> {
  const result = new Set<number>();
  preguntas.forEach((p, i) => {
    if (respuestas[p.id] !== undefined) {
      result.add(i);
    }
  });
  return result;
}

/**
 * Valida que `indice` esté dentro del rango [0, total-1].
 * Retorna el índice si es válido, null si está fuera de rango.
 *
 * Permite al componente QuestionNavigator rechazar saltos inválidos antes
 * de actualizar el estado.
 */
export function irAIndice(indice: number, total: number): number | null {
  if (total <= 0) return null;
  if (indice < 0 || indice >= total) return null;
  return indice;
}
