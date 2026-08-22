import { describe, it, expect } from 'vitest';
import { aplanarArbolCategorias } from './categoriaArbolPlano';
import type { CategoriaPregunta } from '../../lib/apiAdmin/bancoPreguntasApi';

function cat(id: string, nombre: string, padre: string | null): CategoriaPregunta {
  return { id, nombre, materia_id: 'm1', categoria_padre_id: padre, creada_en: '2026-01-01T00:00:00' };
}

describe('aplanarArbolCategorias', () => {
  it('aplana un árbol de 3 niveles preservando el orden padre → hijos', () => {
    const categorias = [
      cat('a', 'Unidad 1', null),
      cat('b', 'Tema 1.1', 'a'),
      cat('c', 'Subtema 1.1.1', 'b'),
      cat('d', 'Unidad 2', null),
    ];
    const plano = aplanarArbolCategorias(categorias);
    expect(plano.map((p) => p.nombre)).toEqual(['Unidad 1', 'Tema 1.1', 'Subtema 1.1.1', 'Unidad 2']);
  });

  it('asigna la profundidad correcta a cada nivel', () => {
    const categorias = [cat('a', 'Unidad 1', null), cat('b', 'Tema 1.1', 'a'), cat('c', 'Subtema 1.1.1', 'b')];
    const plano = aplanarArbolCategorias(categorias);
    expect(plano.map((p) => p.profundidad)).toEqual([0, 1, 2]);
  });

  it('lista vacía devuelve lista vacía', () => {
    expect(aplanarArbolCategorias([])).toEqual([]);
  });

  it('categorías huérfanas (padre inexistente) se tratan como raíz', () => {
    const categorias = [cat('a', 'Huerfana', 'no-existe')];
    const plano = aplanarArbolCategorias(categorias);
    expect(plano).toEqual([{ id: 'a', nombre: 'Huerfana', profundidad: 0 }]);
  });
});
