/**
 * Cómo se lee cada tipo de pregunta en pantalla.
 *
 * Vive en un solo lugar porque estaba copiado en tres modales y ninguno cubría
 * `multiple_choice`, que es la grafía que el banco guarda: el docente veía
 * "multiple_choice (8)" en el selector de sorteo. Las dos grafías conviven —
 * Moodle exporta `multichoice` y el importador normaliza a `multiple_choice`—
 * así que las dos tienen que traducir.
 */
const ETIQUETA: Record<string, string> = {
  multichoice: 'Opción múltiple',
  multiple_choice: 'Opción múltiple',
  truefalse: 'Verdadero / Falso',
  true_false: 'Verdadero / Falso',
  cloze: 'Cloze (completar)',
  shortanswer: 'Respuesta corta',
  short_answer: 'Respuesta corta',
  matching: 'Relacionar',
};

/** Un tipo desconocido se muestra crudo: mejor que un renglón vacío. */
export function etiquetaDeTipo(tipo: string): string {
  return ETIQUETA[tipo] ?? tipo;
}
