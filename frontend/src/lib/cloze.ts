/**
 * Utilidades para previews de preguntas cloze (Moodle) en el panel de administración.
 *
 * La sintaxis cloze embebe la respuesta correcta inline, por ejemplo:
 *   "El lenguaje {1:SHORTANSWER:=Python} es genial"
 *   "La capital es {1:MULTICHOICE:=Madrid~Roma~París}"
 *
 * Mostrar ese texto crudo en un preview (banco, selección manual) es ilegible y
 * FILTRA la respuesta correcta (`=Python`), violando el criterio D3 (no exponer
 * `es_correcta`). Este helper reemplaza cada campo cloze por un hueco visible
 * "____" para que el tutor vea el enunciado sin las soluciones.
 *
 * El patrón matchea SOLO campos cloze válidos ({peso?:TIPO:...}) — no toca llaves
 * normales que pudiera contener un enunciado (por ejemplo, código con `{ }`).
 */

// {  peso? : TIPO : contenido }  → TIPO = SHORTANSWER, MULTICHOICE, NUMERICAL, SA, MC, NM, ...
const CAMPO_CLOZE = /\{\d*:[A-Z_]+:[^{}]*\}/gi;

/** Reemplaza cada campo cloze del enunciado por un hueco "____" legible. */
export function limpiarEnunciadoCloze(enunciado: string): string {
  if (!enunciado) return enunciado;
  return enunciado.replace(CAMPO_CLOZE, '____').replace(/[ \t]+/g, ' ').trim();
}
