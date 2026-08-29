/**
 * Tope de score a partir del cual se dejan de guardar capturas.
 *
 * ## Por qué
 *
 * El score se capa en 100 (`Math.min(100, ...)` en el cliente, `SCORE_CAP`
 * server-side). Una vez ahí, cada imagen nueva no mueve la priorización: la sesión
 * ya está en lo más alto de la cola de revisión, y sumar fotos no la sube más.
 * Solo ocupan lugar — y el 99% del costo de almacenamiento son las imágenes
 * (~85 KB cada una contra ~200 B de la fila del evento).
 *
 * ## Qué se pierde, dicho explícito
 *
 * Si un alumno llega a 100 en el minuto 5, no quedan imágenes de los 55 minutos
 * siguientes. Es el costo que el dueño aceptó el 29/8/2026 ("cualquier cosa en un
 * futuro lo cambiamos"), después de haber pedido lo contrario esa misma mañana.
 *
 * ## Qué NO se toca
 *
 * Los EVENTOS se siguen detectando, registrando y posteando siempre. Frenarlos
 * sería un exploit: al alumno le convendría disparar el detector a propósito al
 * empezar para quedar sin registro el resto del examen. Acá solo se deja de
 * adjuntar la imagen, así que el revisor humano sigue viendo QUÉ pasó y cuándo.
 */

/** Score en el que el acumulado queda topeado y las capturas dejan de aportar. */
export const SCORE_TOPE = 100;

/**
 * ¿Vale la pena guardar la imagen de este evento?
 *
 * @param scoreActual Score acumulado ANTES de este evento (0..100).
 */
export function debeGuardarCaptura(scoreActual: number): boolean {
  return scoreActual < SCORE_TOPE;
}

/**
 * ¿Vale la pena registrar y enviar este evento?
 *
 * Con el score en el tope, un evento nuevo no cambia nada de lo que el sistema
 * hace con él: la sesión ya está en lo más alto de la cola de revisión y no puede
 * subir más. Seguir posteando solo agranda la base sin agregar información que
 * cambie una decisión.
 *
 * El costo, explícito: alguien que llegue a 100 a propósito en los primeros
 * minutos queda sin registro el resto del examen. Lo que lo acota es que llegar a
 * 100 ya dejó la sesión marcada en lo más alto de la cola, así que igual la mira
 * un humano — que es lo que el sistema promete (L2.5: prioriza, no sanciona).
 *
 * NO alcanza a `captura_pausa`, que viaja por su propio camino: el backend
 * verifica que exista una captura dentro de cada ventana de pausa aprobada y sin
 * ella emite `pausa_sin_captura`. Cortarla acá inventaría esa señal.
 *
 * @param scoreActual Score acumulado ANTES de este evento (0..100).
 */
export function debeRegistrarEvento(scoreActual: number): boolean {
  return scoreActual < SCORE_TOPE;
}
