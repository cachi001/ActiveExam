/**
 * ChipMultiSelect — componente genérico de selección múltiple con chips.
 *
 * Se testea el contrato de presentación puro: elegir del desplegable dispara
 * onAgregar con el id, quitar un chip dispara onQuitar con el id, los chips
 * muestran su texto propio (no necesariamente el mismo que el de la opción)
 * y cada botón de quitar tiene su aria-label. El componente no llama a ningún
 * endpoint — eso es responsabilidad de quien lo usa (ver ComisionMultiSelect,
 * AsignarDocenteDialog y AsignarResponsableDialog).
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, fireEvent } from '@testing-library/react';

import { ChipMultiSelect, type ChipMultiSelectOption } from './ChipMultiSelect';

const DISPONIBLES: ChipMultiSelectOption[] = [
  { id: 'u-1', textoOpcion: 'Ana Pérez · legajo-1', textoChip: 'Ana Pérez' },
  { id: 'u-2', textoOpcion: 'Beto Gómez · legajo-2', textoChip: 'Beto Gómez' },
];

afterEach(() => {
  cleanup();
});

describe('ChipMultiSelect', () => {
  it('elegir del desplegable dispara onAgregar con el id de la opción', () => {
    const onAgregar = vi.fn();
    render(
      <ChipMultiSelect
        seleccionados={[]}
        disponibles={DISPONIBLES}
        onAgregar={onAgregar}
        onQuitar={vi.fn()}
        textoOpcionVacia="Elegir…"
      />,
    );

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'u-1' } });

    expect(onAgregar).toHaveBeenCalledWith('u-1');
  });

  it('cada elegido se muestra como chip con su propio texto y su botón de quitar', () => {
    render(
      <ChipMultiSelect
        seleccionados={[{ id: 'u-1', textoOpcion: 'Ana Pérez · legajo-1', textoChip: 'Ana Pérez' }]}
        disponibles={DISPONIBLES.filter((o) => o.id !== 'u-1')}
        onAgregar={vi.fn()}
        onQuitar={vi.fn()}
        textoOpcionVacia="Elegir…"
      />,
    );

    expect(screen.getByText('Ana Pérez')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Quitar Ana Pérez' })).toBeTruthy();
    // El texto largo de la opción (con legajo) no aparece en pantalla como chip.
    expect(screen.queryByText('Ana Pérez · legajo-1')).toBeNull();
  });

  it('clickear el botón de quitar dispara onQuitar con el id del chip', () => {
    const onQuitar = vi.fn();
    render(
      <ChipMultiSelect
        seleccionados={[{ id: 'u-1', textoOpcion: 'Ana Pérez', textoChip: 'Ana Pérez' }]}
        disponibles={[]}
        onAgregar={vi.fn()}
        onQuitar={onQuitar}
        textoOpcionVacia="Sin candidatos"
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Quitar Ana Pérez' }));

    expect(onQuitar).toHaveBeenCalledWith('u-1');
  });

  it('sin chips elegidos no se renderiza la fila de chips ni sus botones', () => {
    render(
      <ChipMultiSelect
        seleccionados={[]}
        disponibles={DISPONIBLES}
        onAgregar={vi.fn()}
        onQuitar={vi.fn()}
        textoOpcionVacia="Elegir…"
      />,
    );

    expect(screen.queryByRole('button')).toBeNull();
  });

  it('disabled deshabilita el desplegable y los botones de quitar', () => {
    render(
      <ChipMultiSelect
        seleccionados={[{ id: 'u-1', textoOpcion: 'Ana Pérez', textoChip: 'Ana Pérez' }]}
        disponibles={DISPONIBLES.filter((o) => o.id !== 'u-1')}
        onAgregar={vi.fn()}
        onQuitar={vi.fn()}
        textoOpcionVacia="Elegir…"
        disabled
      />,
    );

    expect((screen.getByRole('combobox') as HTMLSelectElement).disabled).toBe(true);
    expect(
      (screen.getByRole('button', { name: 'Quitar Ana Pérez' }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });
});
