/**
 * Decide a dónde llevar al alumno cuando toca «Rendir» / «Continuar examen».
 *
 * ## El problema que resuelve
 *
 * «Continuar examen» lo dejaba al principio del ingreso —consentimiento,
 * biometría, calibración, sala de espera— con el botón final diciendo «Comenzar
 * examen». Prometía retomar y arrancaba de cero. Y de paso descartaba el id de la
 * sesión viva, así que se abría un intento nuevo mientras el cronómetro de la
 * sesión original seguía corriendo del lado del servidor.
 *
 * ## Por qué se puede saltear la verificación al retomar
 *
 * Porque ya la pasó: esa sesión existe justamente porque el alumno completó el
 * ingreso. No es que se confíe menos, es que la identidad durante la rendición la
 * vigila el proctoring en vivo —detección de rostro cuadro a cuadro— y no el
 * trámite de entrada. Repetirlo le come minutos del examen con el reloj andando.
 *
 * ## La excepción
 *
 * Si la sesión existe pero el examen NUNCA arrancó (`examen_iniciado_en` en null),
 * el alumno se cayó en el medio del ingreso: nunca vio una pregunta ni empezó a
 * correr el tiempo. Ahí hay que hacerle el ingreso completo, o entraría a rendir
 * sin haber pasado nunca la verificación.
 */

import type { SesionEnCurso } from '../../lib/apiProctoring/sesion';

export interface DestinoRendicion {
  /** Ruta a la que navegar. */
  ruta: '/pre-examen' | '/examen';
  /** Sesión a reusar, o `null` para abrir una nueva. */
  sessionId: string | null;
}

export function destinoDeRendicion(sesion: SesionEnCurso | null): DestinoRendicion {
  if (!sesion) return { ruta: '/pre-examen', sessionId: null };
  // Se cayó durante el ingreso: la sesión se reusa (no gasta otro intento), pero
  // la verificación se hace igual.
  if (!sesion.examen_iniciado_en) {
    return { ruta: '/pre-examen', sessionId: sesion.session_id };
  }
  return { ruta: '/examen', sessionId: sesion.session_id };
}
