/**
 * c-78 E-06 (task 14.1) — ComisionMultiSelect.
 *
 * Lo que se testea es la regla de dominio que el componente impone, no el estilo
 * de los chips: **todas las comisiones elegidas son de la misma materia**. Al
 * elegir la primera, la materia queda fijada y el desplegable deja de ofrecer las
 * de otras materias, porque el examen se arma con el banco de UNA materia.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('../lib/api', () => ({
  api: { comisionesTodas: vi.fn() },
}));

import { ComisionMultiSelect } from './ComisionMultiSelect';
import { api } from '../lib/api';

const COMISIONES = [
  {
    id: 'c-1',
    codigo: 'C1',
    nombre: 'Comisión 1',
    materia_id: 'm-prog1',
    materia_nombre: 'Programación 1',
    materia_codigo: 'PROG1',
  },
  {
    id: 'c-2',
    codigo: 'C2',
    nombre: 'Comisión 2',
    materia_id: 'm-prog1',
    materia_nombre: 'Programación 1',
    materia_codigo: 'PROG1',
  },
  {
    id: 'c-9',
    codigo: 'C9',
    nombre: 'Comisión 9',
    materia_id: 'm-algebra',
    materia_nombre: 'Álgebra',
    materia_codigo: 'ALG',
  },
];

/** Renderiza el componente controlando el estado, como lo hace el modal real. */
function renderControlado(alCambiar?: (ids: string[]) => void) {
  let seleccion: string[] = [];
  const onChange = vi.fn((ids: string[]) => {
    seleccion = ids;
    alCambiar?.(ids);
    rerender(<ComisionMultiSelect value={seleccion} onChange={onChange} />);
  });
  const { rerender } = render(
    <ComisionMultiSelect value={seleccion} onChange={onChange} />,
  );
  return { onChange };
}

function opciones(): string[] {
  return Array.from(
    screen.getByRole('combobox').querySelectorAll('option'),
  ).map((o) => o.textContent ?? '');
}

beforeEach(() => {
  vi.mocked(api.comisionesTodas).mockResolvedValue(COMISIONES as never);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('ComisionMultiSelect', () => {
  it('elegir una comisión la muestra como chip y la saca del desplegable', async () => {
    renderControlado();
    await waitFor(() => expect(opciones()).toContain('C1 - Programación 1'));

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'c-1' } });

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Quitar C1' })).toBeTruthy(),
    );
    expect(opciones()).not.toContain('C1 - Programación 1');
  });

  it('con una comisión elegida, el desplegable solo ofrece las de esa materia', async () => {
    renderControlado();
    await waitFor(() => expect(opciones()).toContain('C9 - Álgebra'));

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'c-1' } });

    // C2 comparte materia con C1 y sigue disponible; C9 es de otra materia y no.
    await waitFor(() => expect(opciones()).toContain('C2 - Programación 1'));
    expect(opciones()).not.toContain('C9 - Álgebra');
  });

  it('quitar el chip devuelve la comisión al desplegable y libera la materia', async () => {
    renderControlado();
    await waitFor(() => expect(opciones()).toContain('C1 - Programación 1'));

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'c-1' } });
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Quitar C1' })).toBeTruthy(),
    );

    fireEvent.click(screen.getByRole('button', { name: 'Quitar C1' }));

    // Sin ninguna elegida, vuelven a estar todas — incluida la de otra materia.
    await waitFor(() => expect(opciones()).toContain('C1 - Programación 1'));
    expect(opciones()).toContain('C9 - Álgebra');
    expect(screen.queryByRole('button', { name: 'Quitar C1' })).toBeNull();
  });

  it('acumula varias comisiones de la misma materia', async () => {
    const vistos: string[][] = [];
    renderControlado((ids) => vistos.push(ids));
    await waitFor(() => expect(opciones()).toContain('C1 - Programación 1'));

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'c-1' } });
    await waitFor(() => expect(opciones()).toContain('C2 - Programación 1'));
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'c-2' } });

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Quitar C2' })).toBeTruthy(),
    );
    expect(screen.getByRole('button', { name: 'Quitar C1' })).toBeTruthy();
    expect(vistos.at(-1)).toEqual(['c-1', 'c-2']);
  });
});
