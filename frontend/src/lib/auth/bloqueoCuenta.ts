/**
 * Bloqueo de la cuenta por intentos fallidos: detección y cuenta regresiva.
 *
 * Tras 5 intentos fallidos el backend bloquea la cuenta 15 minutos. Hasta ahora el
 * login mostraba «Credenciales inválidas» y punto, así que el usuario no sabía si
 * se había equivocado, si la app estaba rota o cuánto tenía que esperar.
 *
 * Los primeros intentos SIGUEN sin decir cuántos quedan, y es a propósito: avisar
 * «te queda 1» le regala al atacante el umbral exacto para frenar justo antes y
 * seguir probando. Lo que sí se informa, una vez bloqueado, es cuánto falta —
 * cuando el bloqueo ya ocurrió, esconderlo solo perjudica a quien es dueño de la
 * cuenta.
 */

/** Forma del `detail` que manda el backend cuando la cuenta está bloqueada. */
interface DetalleBloqueo {
  error?: unknown;
  segundos_restantes?: unknown;
}

/**
 * Segundos que faltan para el desbloqueo, o `null` si la respuesta no es un
 * bloqueo. Tolera formas inesperadas (backend viejo, proxy que reescribe el
 * cuerpo): ante la duda devuelve `null` y el login sigue mostrando su error de
 * siempre, sin romperse.
 */
export function bloqueoDeLaRespuesta(detail: unknown): number | null {
  if (typeof detail !== 'object' || detail === null) return null;
  const d = detail as DetalleBloqueo;
  if (d.error !== 'cuenta_bloqueada') return null;
  const seg = d.segundos_restantes;
  return typeof seg === 'number' && Number.isFinite(seg) ? seg : null;
}

/**
 * Cómo se lee lo que falta.
 *
 * Bajo el minuto se muestran solo los segundos: cuando falta poco, «9 s» se lee de
 * un vistazo y «00:09» hay que interpretarlo. Es justo el tramo en el que la
 * persona está mirando el reloj.
 */
export function textoDeEspera(segundos: number): string {
  if (segundos <= 0) return 'ya podés intentar';
  if (segundos < 60) return `${segundos} s`;
  const min = Math.floor(segundos / 60);
  const seg = segundos % 60;
  return `${String(min).padStart(2, '0')}:${String(seg).padStart(2, '0')}`;
}
