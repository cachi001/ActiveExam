import { afterEach, describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { CategoriasTree } from './CategoriasTree';
import type { CategoriaPregunta } from '../../lib/apiAdmin/bancoPreguntasApi';

afterEach(cleanup);

// Árbol de 3 niveles: Unidad 1 → Tema 1.1 → Subtema 1.1.1
const CAT_RAIZ: CategoriaPregunta = {
  id: 'a',
  nombre: 'Unidad 1',
  materia_id: 'm1',
  categoria_padre_id: null,
  creada_en: '2026-01-01T00:00:00',
};
const CAT_NIVEL2: CategoriaPregunta = {
  id: 'b',
  nombre: 'Tema 1.1',
  materia_id: 'm1',
  categoria_padre_id: 'a',
  creada_en: '2026-01-01T00:00:00',
};
const CAT_NIVEL3: CategoriaPregunta = {
  id: 'c',
  nombre: 'Subtema 1.1.1',
  materia_id: 'm1',
  categoria_padre_id: 'b',
  creada_en: '2026-01-01T00:00:00',
};

const noOp = () => {};

describe('CategoriasTree', () => {
  it('4.6a renderiza árbol de 3 niveles expandido por defecto', () => {
    render(
      <CategoriasTree
        categorias={[CAT_RAIZ, CAT_NIVEL2, CAT_NIVEL3]}
        seleccionada={null}
        onSeleccionar={noOp}
        onCrear={noOp}
        onRenombrar={noOp}
        onBorrar={noOp}
      />,
    );
    expect(screen.getAllByText('Unidad 1').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Tema 1.1').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Subtema 1.1.1').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/sin clasificar/i).length).toBeGreaterThan(0);
  });

  it('4.6b seleccionar categoría llama onSeleccionar con su id', () => {
    const spy = vi.fn();
    render(
      <CategoriasTree
        categorias={[CAT_RAIZ, CAT_NIVEL2]}
        seleccionada={null}
        onSeleccionar={spy}
        onCrear={noOp}
        onRenombrar={noOp}
        onBorrar={noOp}
      />,
    );
    fireEvent.click(screen.getAllByText('Unidad 1')[0]);
    expect(spy).toHaveBeenCalledWith('a');
  });

  it('4.6c seleccionar "Sin clasificar" llama onSeleccionar con null', () => {
    const spy = vi.fn();
    render(
      <CategoriasTree
        categorias={[CAT_RAIZ]}
        seleccionada="a"
        onSeleccionar={spy}
        onCrear={noOp}
        onRenombrar={noOp}
        onBorrar={noOp}
      />,
    );
    fireEvent.click(screen.getAllByText(/sin clasificar/i)[0]);
    expect(spy).toHaveBeenCalledWith(null);
  });
});
