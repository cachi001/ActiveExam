/**
 * Duración e intervalo de muestreo por PUNTO de calibración de mirada.
 *
 * Antes había tres constantes independientes, una por lugar que calibra (paso
 * previo del alumno: 6000/200; respaldo dentro del examen: 3000/200; harness
 * de admin: 3000/100) — medían distinto sin que nadie lo hubiera decidido así.
 *
 * Ahora los tres reusan estas dos, sobre UN punto cada vez (el paso previo y el
 * harness llaman 4 veces, una por esquina; el respaldo llama una sola vez). Con
 * ~13 muestras por punto alcanza para un promedio estable sin que calibrar las
 * 4 esquinas se sienta largo (4 × 2 s = 8 s totales).
 */
export const CALIBRACION_DURACION_MS = 2000;
export const CALIBRACION_INTERVALO_MS = 150;
