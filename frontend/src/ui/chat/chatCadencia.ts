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
 * no hay nada que refrescar seguido: se pregunta cada 8 s. En cuanto aparece uno,
 * la conversación está viva y se vuelve a 3,5 s. El costo real es que el mensaje
 * que ABRE una conversación puede tardar hasta 8 s en aparecerle al alumno; a
 * partir de ahí, y por los cinco minutos siguientes a cada mensaje, va a la
 * velocidad de siempre.
 *
 * Ese es el intercambio: hasta 8 s de demora al abrir una conversación que casi
 * nunca ocurre, a cambio de ~16 req/s de margen para que el examen de todos los
 * demás no se ponga lento.
 *
 * La solución de fondo, para cuando haya tiempo: que el aviso de "hay mensajes
 * nuevos" viaje colgado del autoguardado que el alumno hace igual. Ahí el chat
 * pasa a costar cero requests extra y puede ser inmediato.
 */

/** Conversación viva: la cadencia de siempre. */
export const POLL_CHAT_ACTIVO_MS = 3500;

/**
 * Nadie escribió todavía (o hace rato que no): alcanza con mirar de vez en cuando.
 *
 * 8 s baja el costo del poller a menos de la mitad (de ~29 a 12,5 req/s con 100
 * alumnos, y a 5 req/s con los 40 que son el escenario probable) sin que el aviso
 * del tutor se haga esperar de más.
 *
 * Estuvo en 15 s y se bajó: 15 s ahorraba un poco más, pero el tutor escribe para
 * avisar algo AHORA ("levantá la cámara", "se te ve otra pantalla"), y un cuarto
 * de minuto de demora en eso es mucho. El ahorro que faltaba no se paga con una
 * persona esperando; se paga con la decisión de dónde corre el examen, que es lo
 * que de verdad mueve el techo (medido: 9,7 req/s con 0,1 CPU, holgado con 0,5).
 */
export const POLL_CHAT_INACTIVO_MS = 8_000;

/**
 * Cuánto sigue considerándose "viva" una conversación después del último mensaje.
 *
 * Cinco minutos. Con dos, una charla con pausas normales se caía a lento en el
 * medio: el alumno tardaba en contestar, el tutor insistía, y esa insistencia le
 * llegaba con la espera completa encima. Estirarlo es casi gratis porque solo
 * mantiene el ritmo rápido en las sesiones donde alguien efectivamente habló.
 */
export const VENTANA_CONVERSACION_VIVA_MS = 5 * 60 * 1000;

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
