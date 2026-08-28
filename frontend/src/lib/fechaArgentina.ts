/**
 * La fecha escrita en argentino, para poner al lado de un campo de fecha.
 *
 * POR QUÉ EXISTE. Los campos de fecha usan `<input type="datetime-local">`, y
 * ese control lo dibuja el NAVEGADOR con SU idioma: con el navegador en inglés
 * el mismo valor se ve `08/27/2026 10:49 PM`. El sitio no lo puede cambiar —
 * está verificado: poner `lang="es-AR"` en el documento no altera el control, y
 * `Intl` sigue resolviendo el locale del navegador.
 *
 * Lo que sí se puede es escribir la fecha al lado, sin ambigüedad posible. Un
 * `08/09` puede ser agosto o septiembre según quién lo mire; "8 de septiembre"
 * no.
 */

/** `2026-08-27T22:49` (valor de un datetime-local) → "jue 27 de agosto de 2026, 22:49". */
export function fechaEnArgentino(valorInput: string): string {
  if (!valorInput) return '';
  const d = new Date(valorInput);
  if (Number.isNaN(d.getTime())) return '';
  return new Intl.DateTimeFormat('es-AR', {
    weekday: 'short',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(d);
}
