/**
 * El texto del resultado que ve el alumno al revisar su examen (c-78).
 *
 * Decisión del dueño: **no se le muestra cómo se calcula la nota.** Antes decía
 * "Cada pregunta vale lo mismo; la nota = correctas ÷ total × 10". Esa fórmula
 * no le agrega nada para estudiar y sí invita a discutir el redondeo en vez del
 * contenido.
 *
 * Lo que sí ve: su nota (arriba, aparte) y cuántas acertó sobre el total. Eso es
 * devolución; la fórmula es mecanismo interno.
 *
 * Vive en su propio archivo para poder testear el texto sin montar la pantalla,
 * que pide datos al backend.
 */

export interface DatosResultadoRevision {
  correctas: number;
  total: number;
  notaMaxima?: number | null;
}

export function textoResultadoRevision({
  correctas,
  total,
}: DatosResultadoRevision): string {
  if (!total) {
    // Pasa con un examen mal armado o sin preguntas seleccionadas. Sin esta
    // guarda el porcentaje sale NaN y la frase queda rota justo en la pantalla
    // donde el alumno mira su nota.
    return 'Todavía no hay preguntas para mostrar en esta revisión.';
  }
  const porcentaje = Math.round((correctas / total) * 100);
  return `Acertaste ${correctas} de ${total} (${porcentaje}%).`;
}
