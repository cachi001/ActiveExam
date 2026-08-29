/**
 * Traducción del filtro "Estado" de Gestión de usuarios a parámetro de query.
 *
 * Vive aparte de la pantalla porque es lógica con una trampa: el backend NO
 * trata "sin parámetro" como "sin filtro". `GET /users/` declara
 * `estado: str | None = "activo"`, así que omitir `estado` devuelve solo los
 * usuarios activos. Cualquier opción tiene que viajar EXPLÍCITA, incluida
 * "todos" — que el backend entiende como "no filtrar por `eliminado_en`".
 */

/** Opciones válidas del desplegable (espejo de `OPCIONES_ESTADO`). */
export type FiltroEstado = 'activo' | 'inactivo' | 'todos';

/**
 * Default de la pantalla. Coincide a propósito con el default del backend: si
 * difirieran, la primera carga mostraría una opción y pediría otra.
 */
export const ESTADO_INICIAL: FiltroEstado = 'activo';

/**
 * Valor que viaja en la query para la opción elegida.
 *
 * Nunca devuelve `undefined`: el cliente HTTP omite los parámetros indefinidos y
 * ahí es donde el default del backend pisaba en silencio lo elegido.
 */
export function paramsDeEstado(opcion: string): FiltroEstado {
  if (opcion === 'todos' || opcion === 'inactivo' || opcion === 'activo') return opcion;
  return ESTADO_INICIAL;
}
