/**
 * Cadencia adaptativa del poller de pausas del alumno (c-78).
 *
 * ## Por qué existe
 *
 * `PausaAlumno` preguntaba cada 3,5 s durante TODO el examen — dos horas — por
 * algo que casi nunca pasa. Con 100 alumnos eso son **~29 req/s permanentes**
 * sobre un techo medido de 80 req/s. Y cuando el techo satura no se pone lento el
 * chat: se pone lento **todo**, incluido el autoguardado de las respuestas (p50
 * de 280 ms a 875 ms en la medición del 25/8/2026). O sea que el poller de la
 * pausa le estaba compitiendo el ancho de banda al guardado del examen.
 *
 * ## Por qué se puede ir lento sin que el alumno espere más
 *
 * La pausa **siempre la inicia el alumno**: `solicitar_pausa` es el único
 * endpoint que crea una, y el tutor solo aprueba o rechaza. Mientras el alumno no
 * pidió nada, **no puede llegarle nada que no haya pedido** — preguntar seguido no
 * le ahorra un segundo.
 *
 * En cuanto toca el botón, `PausaAlumno` hace `setPausa()` con la respuesta del
 * POST, el estado local pasa a `solicitada` y el intervalo vuelve a 3,5 s **en ese
 * mismo render**. La espera percibida es idéntica a la de antes.
 *
 * ## Lo que NO aplica
 *
 * Esto no sirve para el chat: ahí el que inicia es el TUTOR (el alumno no puede
 * abrir el hilo, solo responder), así que bajarle la frecuencia le haría llegar el
 * mensaje 20 s tarde. El chat se queda rápido.
 */

/** Hay algo en vuelo: se pregunta seguido. Es la cadencia histórica. */
export const POLL_PAUSA_ACTIVO_MS = 3500;

/**
 * No hay nada en vuelo: alcanza con mirar de vez en cuando.
 *
 * 20 s baja el costo del poller a ~1/6 (de ~29 a ~5 req/s con 100 alumnos) y
 * sigue siendo lo bastante seguido como para levantar cualquier cambio que se
 * haya perdido (por ejemplo si el POST de la solicitud falló y el alumno no se
 * enteró).
 */
export const POLL_PAUSA_INACTIVO_MS = 20_000;

/**
 * Estados en los que ya se resolvió todo y no queda nada esperando.
 *
 * Se lista lo RESUELTO, no lo pendiente, para que un estado nuevo caiga del lado
 * seguro (preguntar seguido). Si mañana se agrega uno, el error barato es
 * preguntar de más; el caro es dejar al alumno esperando sin enterarse de nada.
 */
const ESTADOS_RESUELTOS = new Set(['rechazada', 'finalizada']);

/**
 * Cada cuánto conviene preguntar por el estado de la pausa.
 *
 * `estado` es el de la pausa más reciente del alumno, o `null`/`undefined` si no
 * tiene ninguna.
 */
export function intervaloDePolling(estado: string | null | undefined): number {
  if (!estado || ESTADOS_RESUELTOS.has(estado)) return POLL_PAUSA_INACTIVO_MS;
  return POLL_PAUSA_ACTIVO_MS;
}
