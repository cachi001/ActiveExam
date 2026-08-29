/**
 * Cuándo se pueden pedir las preguntas del examen.
 *
 * En `sorteo_por_intento` el backend sortea en el PRIMER `GET /exam-content/{id}`
 * y ese sorteo necesita una sesión de proctoring ABIERTA del alumno. Sin sesión
 * responde `preguntas: []` y no sortea nada — el alumno se queda con un examen
 * vacío que además no puede entregar.
 *
 * Vive fuera de `Examen.tsx` para poder probar la condición sin montar la
 * pantalla entera (cámara, MediaPipe, store y router).
 */

/** `true` si ya están las dos cosas que el sorteo necesita. */
export function puedeCargarPreguntas(
  examenContenidoId: string | undefined | null,
  sessionId: string | null,
): boolean {
  return Boolean(examenContenidoId) && Boolean(sessionId);
}

/**
 * ¿Hay que reintentar la carga?
 *
 * Red de seguridad además de la guarda de arriba: si por lo que sea el examen
 * llega VACÍO (una carrera que no previmos, un sorteo que falló, un backend que
 * se reinició en el momento justo), el alumno quedaba con la pantalla en cero y
 * sin forma de salir — no podía ni entregar, porque no había nada que enviar.
 *
 * Reintentar es seguro: el sorteo es idempotente. El backend lo resuelve UNA vez
 * y lo persiste en `pregunta_sesion`, así que volver a pedir devuelve exactamente
 * las mismas preguntas, nunca un sorteo nuevo.
 *
 * Se acota a `MAX_REINTENTOS` para no dejar un bucle infinito golpeando la API si
 * el examen de verdad no tiene preguntas (ese caso ya lo bloquea el gate del
 * listado, con su propio motivo).
 */
export const MAX_REINTENTOS_CARGA = 3;

export function debeReintentarCarga(
  cantidadPreguntas: number,
  intentosHechos: number,
  hayExamenYSesion: boolean,
): boolean {
  if (!hayExamenYSesion) return false;
  if (cantidadPreguntas > 0) return false;
  return intentosHechos < MAX_REINTENTOS_CARGA;
}
