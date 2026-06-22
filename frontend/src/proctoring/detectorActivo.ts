/**
 * detectorActivo — helper PURO para filtrar eventos según detectores_activos.
 *
 * Política fail-open:
 *  - Si `detectoresActivos` es undefined o null (config no cargada), devuelve true:
 *    NO se suprimen eventos cuando no hay config (el examen sigue funcionando).
 *  - Si la lista existe y contiene el tipo, devuelve true.
 *  - Si la lista existe pero NO contiene el tipo, devuelve false: el evento debe
 *    descartarse (detector inactivo según la config del sistema).
 *
 * @param tipo              - Tipo de evento a evaluar (ej. 'rostro_ausente').
 * @param detectoresActivos - Lista de tipos activos de la config efectiva, o undefined.
 * @returns true si el evento debe procesarse; false si debe descartarse.
 */
export function detectorActivo(
  tipo: string,
  detectoresActivos: string[] | undefined | null,
): boolean {
  // Fail-open: sin config, no suprimir nada.
  if (detectoresActivos == null) return true;
  return detectoresActivos.includes(tipo);
}
