/**
 * La columna Tutor mostraba los nombres concatenados. Con dos o tres tutores la
 * celda crecía sin techo, empujaba la tabla más allá del ancho de la card y el
 * scroll horizontal terminaba escondiendo esa misma columna detrás de la de
 * Acciones, que está anclada a la derecha. Un dato que empuja hasta volverse
 * ilegible sirve de poco.
 *
 * Decisión del owner (27/8/2026): en la fila va la CANTIDAD, que ocupa un ancho
 * fijo, y los nombres pasan a "Ver detalle".
 *
 * TDD: RED (la función no existe) → GREEN.
 */

import { describe, it, expect } from 'vitest';
import { resumenTutores } from './resumenTutores';

describe('resumenTutores', () => {
  it('sin tutores avisa que falta asignar, no dice "0 tutores"', () => {
    // Sin tutor las notas de la comisión no se sincronizan al campus: el vacío
    // es un pendiente, y como tal se nombra.
    expect(resumenTutores([])).toBe('Sin asignar');
    expect(resumenTutores(undefined)).toBe('Sin asignar');
  });

  it('con un solo tutor usa el singular', () => {
    expect(resumenTutores([{ id: 't1', nombre: 'Tutor Prueba' }])).toBe('1 tutor');
  });

  it('con varios tutores cuenta, sin importar cuán largos sean los nombres', () => {
    const tutores = [
      { id: 't1', nombre: 'Tutor Prueba' },
      { id: 't2', nombre: 'Maria Fernanda Gonzalez Iturralde' },
      { id: 't3', nombre: 'Juan Ignacio Rodriguez de la Fuente' },
    ];
    expect(resumenTutores(tutores)).toBe('3 tutores');
    // El largo del texto no depende del largo de los nombres: eso es lo que
    // mantiene la columna en un ancho previsible.
    expect(resumenTutores(tutores).length).toBeLessThan(12);
  });
});
