/**
 * Durante el examen el alumno RESPONDE, no inicia la conversación.
 *
 * ## Por qué
 *
 * Decisión del dueño (29/8/2026): mientras rinde, el alumno no puede escribirle
 * al tutor por su cuenta; solo puede contestar si el tutor le escribió primero.
 *
 * El canal existe para que quien supervisa pueda preguntar algo puntual, no para
 * abrir una vía de consulta durante la evaluación. Sin este freno, el chat es una
 * puerta para pedir ayuda con el examen.
 *
 * Se habilita en cuanto hay UN mensaje del tutor, y sigue habilitado el resto de
 * la sesión: una vez que la conversación existe, cortarla a la mitad sería peor
 * (el alumno no podría aclarar lo que le preguntaron).
 */

import type { MensajeChat } from '../../lib/types';

/** `true` si el tutor ya escribió y por lo tanto el alumno puede contestar. */
export function puedeResponder(mensajes: MensajeChat[]): boolean {
  return mensajes.some((m) => m.autor === 'tutor');
}

/** Qué se le explica al alumno cuando la caja está bloqueada. */
export const AVISO_SOLO_RESPONDER =
  'Solo podés responder si el tutor te escribe. No podés iniciar la conversación durante el examen.';
