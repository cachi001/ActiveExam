/**
 * El filtro "Estado" de Gestión de usuarios tiene que pedir lo que muestra.
 *
 * ## El defecto
 *
 * La pantalla arrancaba con el desplegable en **"Todos"**, pero la llamada
 * traducía `'todos'` a `undefined` y el cliente HTTP omite los parámetros
 * `undefined`. Sin `estado` en la query, el backend aplica su default, que es
 * `estado="activo"` (ver `users/router.py`: `estado: str | None = "activo"`).
 *
 * Resultado: el filtro decía "Todos" y la tabla mostraba SOLO los activos. Los
 * usuarios dados de baja eran invisibles, y elegir "Todos" a mano no cambiaba
 * nada porque mandaba exactamente lo mismo: nada. La opción no funcionaba en
 * ningún caso.
 *
 * El backend sí soporta `estado=todos` (no aplica filtro sobre `eliminado_en`):
 * el que nunca lo mandaba era el front.
 *
 * ## Qué fija este test
 *
 * `paramsDeEstado` es la traducción de la opción elegida a lo que viaja en la
 * query. Se extrajo para poder probarla sin montar la pantalla ni la red.
 */

import { describe, expect, it } from 'vitest';

import { paramsDeEstado, ESTADO_INICIAL } from './GestionUsuarios.filtros';

describe('filtro de estado de usuarios', () => {
  it('"todos" viaja explícito: es la única forma de ver también las bajas', () => {
    expect(paramsDeEstado('todos')).toBe('todos');
  });

  it('"activo" e "inactivo" viajan tal cual', () => {
    expect(paramsDeEstado('activo')).toBe('activo');
    expect(paramsDeEstado('inactivo')).toBe('inactivo');
  });

  it('nunca devuelve undefined: omitir el parámetro deja decidir al backend', () => {
    // Ese era el bug: sin parámetro, el default del backend ("activo") pisaba
    // en silencio lo que decía el desplegable.
    for (const opcion of ['todos', 'activo', 'inactivo', '']) {
      expect(paramsDeEstado(opcion)).not.toBeUndefined();
    }
  });

  it('un valor vacío cae al default declarado, no a "sin filtro"', () => {
    expect(paramsDeEstado('')).toBe(ESTADO_INICIAL);
  });

  it('el default de la pantalla coincide con el del backend', () => {
    // Si difieren, la primera carga vuelve a mostrar una cosa y pedir otra.
    expect(ESTADO_INICIAL).toBe('activo');
  });
});
