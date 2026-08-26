/**
 * Cómo se nombra a una persona en pantalla (c-78).
 *
 * EL PROBLEMA QUE CIERRA: el alumno que entra desde Moodle se provisiona con un
 * username SINTÉTICO — `lti:{deployment}:{sub}`, por ejemplo `lti:1:7`. No es un
 * nombre: es una clave interna que garantiza unicidad y reconocimiento entre
 * launches, y se crea ANTES de que la persona pueda elegir nada (la fila tiene
 * que existir para poder emitirle sesión y recién ahí mostrarle la pantalla de
 * "elegí tu usuario").
 *
 * Esa clave se filtraba a la interfaz: después de crear su usuario y contraseña,
 * el alumno entraba al Perfil y ahí veía `lti:1:7` como su nombre de usuario.
 *
 * Hay dos capas de arreglo y ésta es la SEGUNDA:
 *   1. `GET /auth/me` devuelve el username de la FILA, no el del token (que
 *      queda viejo tras el renombre), y `change-password` re-emite el token.
 *   2. Esto: aunque un valor sintético llegue igual — cuenta vieja que nunca
 *      eligió username, token cacheado, backend desactualizado — NUNCA se
 *      dibuja. Se cae a algo que sí le dice algo a la persona.
 *
 * Funciones PURAS: sin React, sin red. Se testean solas.
 */

/** Prefijo del username sintético que genera el provisioning LTI. */
const PREFIJO_LTI = 'lti:';

/**
 * EL texto, uno solo para todo el sistema.
 *
 * Antes había dos reglas (al alumno se le mostraba su email, al admin un estado)
 * y eso daba cuatro textos distintos para el mismo caso. Es una sola situación:
 * la persona entró desde Moodle y no terminó de elegir su usuario. Se dice
 * igual en todos lados.
 */
export const USUARIO_SIN_COMPLETAR = 'Sin completar';

/**
 * La explicación larga, para donde hay lugar (Detalle de usuario) o para un
 * tooltip. El texto corto dice QUÉ pasa; éste dice POR QUÉ y qué se puede hacer.
 */
export const USUARIO_SIN_COMPLETAR_DETALLE =
  'Entró desde Moodle y no llegó a elegir su usuario. No puede usar el sistema ' +
  'hasta que lo haga: la próxima vez que entre, se le vuelve a pedir.';

/**
 * `true` si el username es una clave interna del provisioning, no un nombre que
 * la persona haya elegido.
 *
 * Se compara case-insensitive: el backend lo genera en minúscula, pero un valor
 * que llegue de otra fuente no tiene por qué respetarlo, y equivocarse acá
 * significa mostrar la clave interna igual.
 */
export function esUsernameSintetico(username: string | null | undefined): boolean {
  if (!username) return false;
  return username.trim().toLowerCase().startsWith(PREFIJO_LTI);
}

/**
 * Qué mostrar en el campo "Usuario" de una pantalla.
 *
 * Orden: el username elegido → el email → un guion. NUNCA el sintético: si esa
 * es la única identidad que hay, es preferible el email (que la persona
 * reconoce) o el guion (que no afirma nada) antes que un `lti:1:7` que no le
 * dice nada y encima parece un error del sistema.
 */
export function usernameVisible(
  username: string | null | undefined,
  email?: string | null,
): string {
  if (username && !esUsernameSintetico(username)) return username;
  // MISMO texto que ve el admin: es la misma situación y se dice igual.
  //
  // Para el alumno este caso casi no existe: `RequireAuth` no lo deja entrar a
  // ninguna pantalla mientras no elija su usuario. Queda como cinturón de
  // seguridad por si el token quedó viejo.
  if (esUsernameSintetico(username)) return USUARIO_SIN_COMPLETAR;
  if (email) return email;
  return '—';
}

/**
 * Cómo se llama la persona: nombre y apellido si están, si no lo que sirva.
 *
 * Reusa `usernameVisible` para el último recurso, así el sintético tampoco se
 * cuela por acá (que es como llegaba a los listados de alumnos y a los
 * selectores del panel de administración).
 */
export function nombreVisible(persona: {
  nombre?: string | null;
  apellido?: string | null;
  username?: string | null;
  email?: string | null;
}): string {
  const completo = [persona.nombre, persona.apellido].filter(Boolean).join(' ').trim();
  if (completo) return completo;
  return usernameVisible(persona.username, persona.email);
}


/**
 * Texto normalizado del username para las pantallas de ADMINISTRACIÓN.
 *
 * En Usuarios y Detalle de usuario se dibujaba `u.username` crudo, así que una
 * cuenta a medio completar mostraba `lti:1:7` — una clave interna que parece un
 * dato roto y no le dice al admin lo que realmente pasa.
 *
 * Lo que realmente pasa es esto: esa persona entró desde Moodle, el sistema le
 * creó la cuenta para poder mostrarle la pantalla de registro, y ahí abandonó
 * sin elegir su usuario. No puede usar el sistema (el gate de
 * `debe_cambiar_password` le bloquea todas las rutas hasta que lo elija), pero
 * la fila queda. Se dice eso, en vez de mostrar la clave.
 *
 * Devuelve `pendiente` para que la UI lo estilice distinto: un estado no se
 * dibuja igual que un identificador (nada de `font-mono`, que sugiere "esto es
 * un dato que podés copiar").
 */
export function usernameAdmin(username: string | null | undefined): {
  texto: string;
  pendiente: boolean;
} {
  if (esUsernameSintetico(username)) {
    return { texto: USUARIO_SIN_COMPLETAR, pendiente: true };
  }
  return { texto: username || '—', pendiente: false };
}
