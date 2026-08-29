/**
 * Sin cámara no se rinde. Tampoco a mitad de examen.
 *
 * ## Por qué
 *
 * El chequeo de requisitos ya no deja entrar sin cámara, pero una vez adentro
 * nadie miraba si seguía viva: desenchufarla (o taparla desde el sistema, o que
 * otra app se la robe) dejaba al alumno rindiendo SIN supervisión y sin que nada
 * lo notara. Decisión del dueño (29/8/2026): el examen se bloquea hasta que la
 * reconecte.
 *
 * Es la misma familia que `MonitorBloqueante`: una condición que no puede
 * coexistir con rendir, así que se tapa el examen y se explica cómo salir.
 *
 * ## Por qué NO se finaliza el examen solo
 *
 * Un cable flojo o un permiso revocado por accidente no son fraude. Cortarle el
 * examen sería una sanción automática, y el sistema no sanciona (regla dura #5).
 * Se bloquea, se avisa, y el alumno sigue cuando la recupera — el tiempo corre
 * igual, así que tampoco es un refugio para hacer tiempo.
 */

/** Estado de la cámara visto desde el examen. */
export interface EstadoCamara {
  /** El stream que el examen tiene tomado, o `null` si nunca se pudo abrir. */
  stream: MediaStream | null;
}

/**
 * ¿Hay que bloquear el examen por falta de cámara?
 *
 * Bloquea si no hay stream, si no tiene pista de video, o si la pista murió
 * (`readyState === 'ended'`, que es lo que pasa al desenchufarla) o quedó
 * deshabilitada.
 */
export function camaraCaida(estado: EstadoCamara): boolean {
  const { stream } = estado;
  if (!stream) return true;
  const pistas = stream.getVideoTracks();
  if (pistas.length === 0) return true;
  // Alcanza con UNA pista viva: algunas cámaras exponen varias.
  return !pistas.some((p) => p.readyState === 'live' && p.enabled);
}
