/**
 * Cadencia adaptativa del poller del chat (1/9/2026, antes del examen real).
 *
 * ## Por qué existe
 *
 * `ChatBox` preguntaba cada 3,5 s durante todo el examen. Con 100 alumnos eso son
 * **~29 req/s permanentes** sobre un techo medido de 80 req/s en el plan free: el
 * chat solo se llevaba más de un tercio del presupuesto, para un canal que en la
 * enorme mayoría de las sesiones no se usa nunca.
 *
 * Cuando ese techo satura no se pone lento el chat: se pone lento **todo**,
 * incluido el autoguardado de las respuestas del examen (p50 de 280 ms a 875 ms en
 * la medición del 25/8/2026). El poller del chat le competía el ancho de banda al
 * guardado del examen.
 *
 * ## Por qué se puede ir lento sin romper la conversación
 *
 * Es el mismo patrón que ya usa el poller de pausas (`pausaCadencia.ts`), con una
 * diferencia: en el chat el que abre la conversación es el TUTOR, así que no se
 * puede depender de que el alumno haya iniciado algo.
 *
 * La solución es mirar la conversación misma. Mientras **no hay ningún mensaje**,
 * no hay nada que refrescar seguido: se pregunta cada 15 s. En cuanto aparece uno,
 * la conversación está viva y se vuelve a 3,5 s. El costo real es que el PRIMER
 * mensaje del tutor puede tardar hasta 15 s en aparecerle al alumno; a partir de
 * ahí la conversación va a la velocidad de siempre.
 *
 * Ese es el intercambio: 15 s de demora una sola vez, al principio de una
 * conversación que casi nunca ocurre, a cambio de ~21 req/s de margen para que el
 * examen de todos los demás no se ponga lento.
 */

/** Conversación viva: la cadencia de siempre. */
export const POLL_CHAT_ACTIVO_MS = 3500;

/**
 * Nadie escribió todavía (o hace rato que no): alcanza con mirar de vez en cuando.
 *
 * 15 s baja el costo del poller a menos de un cuarto (de ~29 a ~7 req/s con 100
 * alumnos) y sigue siendo una espera tolerable para el primer aviso del tutor.
 */
export const POLL_CHAT_INACTIVO_MS = 15_000;

/**
 * Cuánto sigue considerándose "viva" una conversación después del último mensaje.
 *
 * Dos minutos cubren de sobra el ida y vuelta de una consulta: nadie contesta un
 * mensaje del tutor dos minutos después y espera que el otro siga esperando.
 */
export const VENTANA_CONVERSACION_VIVA_MS = 2 * 60 * 1000;

/**
 * Cada cuánto conviene preguntar por mensajes nuevos.
 *
 * @param ultimoMensajeIso  Fecha ISO del mensaje más reciente de la sesión, o
 *   `null`/`undefined` si todavía no hay ninguno.
 * @param ahoraMs  Momento actual en ms (inyectable para poder testearlo).
 *
 * Ante una fecha ilegible cae del lado seguro (preguntar seguido): el error barato
 * es preguntar de más, el caro es dejar a alguien esperando una respuesta.
 */
export function intervaloDeChat(
  ultimoMensajeIso: string | null | undefined,
  ahoraMs: number = Date.now(),
): number {
  if (!ultimoMensajeIso) return POLL_CHAT_INACTIVO_MS;

  const ts = new Date(ultimoMensajeIso).getTime();
  if (Number.isNaN(ts)) return POLL_CHAT_ACTIVO_MS;

  const transcurrido = ahoraMs - ts;
  // Un mensaje con fecha futura (relojes desfasados entre cliente y servidor) es
  // recentísimo por definición: conversación viva.
  if (transcurrido < 0) return POLL_CHAT_ACTIVO_MS;

  return transcurrido <= VENTANA_CONVERSACION_VIVA_MS
    ? POLL_CHAT_ACTIVO_MS
    : POLL_CHAT_INACTIVO_MS;
}
