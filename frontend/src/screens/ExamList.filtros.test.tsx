/**
 * c-78 F-05/F-06 (§7.5) — estados de filtro de la pantalla de Exámenes.
 *
 * Los tres estados que se confundían entre sí:
 *   1. Aplicar SOLO comisión habilita "Limpiar" (antes `hayFiltrosActivos` no
 *      miraba la comisión, así que el botón quedaba apagado con un filtro puesto).
 *   2. Un filtro sin resultados dice "ningún examen coincide", no "todavía no hay".
 *   3. Base vacía SIN filtros dice "todavía no hay exámenes cargados".
 *
 * El shell y el modal de creación se mockean a passthrough: lo que se testea es
 * el cableado de filtros → mensaje, no el chrome de la pantalla.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('../ui/shells', () => ({
  StaffShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('../lib/router', () => ({
  useNavigate: () => vi.fn(),
  Link: ({ children }: { children: React.ReactNode }) => <a>{children}</a>,
}));

vi.mock('../admin/ExamImport/CrearExamenModal', () => ({
  CrearExamenModal: () => null,
}));

// El toast necesita su provider; acá no se testea la notificación.
vi.mock('../ui/toast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

vi.mock('../lib/api', () => ({
  API_BASE: '/api/v1',
  api: {
    materiasDisponibles: vi.fn(),
    comisionesDeMateria: vi.fn(),
  },
}));

vi.mock('../lib/examContentCatalog', () => ({
  listarExamenesContenidoPaginadoFn: vi.fn(),
  darDeBajaExamenFn: vi.fn(),
  reactivarExamenFn: vi.fn(),
}));

import ExamList from './ExamList';
import { api } from '../lib/api';
import { listarExamenesContenidoPaginadoFn } from '../lib/examContentCatalog';

const VACIO = { items: [], total: 0, page: 1, page_size: 5 };

beforeEach(() => {
  vi.mocked(api.materiasDisponibles).mockResolvedValue([
    { id: 'm-1', nombre: 'Álgebra' } as never,
  ]);
  vi.mocked(api.comisionesDeMateria).mockResolvedValue([
    { id: 'c-1', nombre: 'Comisión A' } as never,
  ]);
  vi.mocked(listarExamenesContenidoPaginadoFn).mockResolvedValue(VACIO);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

async function aplicarComision() {
  fireEvent.change(screen.getByLabelText('Materia'), { target: { value: 'm-1' } });
  const opcionComision = await screen.findByRole('option', { name: 'Comisión A' });
  fireEvent.change(opcionComision.closest('select')!, { target: { value: 'c-1' } });
  fireEvent.click(await screen.findByRole('button', { name: /aplicar filtros/i }));
}

describe('ExamList — estados de filtro (F-05)', () => {
  it('aplicar solo comisión habilita "Limpiar"', async () => {
    render(<ExamList />);
    await waitFor(() => expect(listarExamenesContenidoPaginadoFn).toHaveBeenCalled());

    // Sin filtros: no hay nada que limpiar.
    expect(screen.queryByRole('button', { name: /limpiar/i })).toBeNull();

    await aplicarComision();

    expect(
      await screen.findByRole('button', { name: /limpiar/i }),
    ).toBeTruthy();
  });

  it('el filtro de comisión viaja al backend', async () => {
    render(<ExamList />);
    await waitFor(() => expect(listarExamenesContenidoPaginadoFn).toHaveBeenCalled());

    await aplicarComision();

    await waitFor(() =>
      expect(listarExamenesContenidoPaginadoFn).toHaveBeenLastCalledWith(
        '/api/v1',
        undefined,
        expect.objectContaining({ comision_id: 'c-1', estado: 'activo' }),
      ),
    );
  });

  it('el filtro de estado manda `inactivo` al backend y habilita "Limpiar"', async () => {
    render(<ExamList />);
    await waitFor(() => expect(listarExamenesContenidoPaginadoFn).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText('Estado'), { target: { value: 'inactivo' } });
    fireEvent.click(await screen.findByRole('button', { name: /aplicar filtros/i }));

    await waitFor(() =>
      expect(listarExamenesContenidoPaginadoFn).toHaveBeenLastCalledWith(
        '/api/v1',
        undefined,
        expect.objectContaining({ estado: 'inactivo' }),
      ),
    );
    expect(await screen.findByRole('button', { name: /limpiar/i })).toBeTruthy();
  });
});

describe('ExamList — mensaje de vacío (F-06)', () => {
  it('con filtro aplicado y sin resultados dice que nada coincide', async () => {
    render(<ExamList />);
    await waitFor(() => expect(listarExamenesContenidoPaginadoFn).toHaveBeenCalled());

    await aplicarComision();

    expect(
      await screen.findByText(/ningún examen coincide con los filtros/i),
    ).toBeTruthy();
  });

  it('sin filtros y base vacía dice que todavía no hay exámenes', async () => {
    render(<ExamList />);

    expect(
      await screen.findByText(/todavía no hay exámenes cargados/i),
    ).toBeTruthy();
    expect(screen.queryByText(/ningún examen coincide/i)).toBeNull();
  });
});
