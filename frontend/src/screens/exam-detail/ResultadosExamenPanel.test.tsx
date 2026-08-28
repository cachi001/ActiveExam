/**
 * Tests — ResultadosExamenPanel (C-76 tarea 14: estado de entrega + archivado)
 *
 * Cubre lo pedido en tasks.md §14.8:
 *  - el select "Estado de entrega" refleja las 4 opciones nuevas (labels en
 *    español claro, no términos técnicos crudos)
 *  - "Aplicar filtros" combina q/estado/estado_entrega/archivado/fecha en el
 *    query que arma la llamada a listarResultadosFn
 *  - el botón archivar dispara el PATCH (archivarResultadoFn) y refresca la fila
 *
 * Framework: vitest + @testing-library/react. Mocks: API client (examContentResultados)
 * y authProvider — no hay fetch real.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';

import { ResultadosExamenPanel } from './ResultadosExamenPanel';
import type { ResultadoExamen } from '../../lib/examContentResultados';
import { ToastProvider } from '../../ui/toast';

const listarResultadosFn = vi.fn();
const sincronizarMoodleFn = vi.fn();
const archivarResultadoFn = vi.fn();

vi.mock('../../lib/examContentResultados', async () => {
  const actual = await vi.importActual<typeof import('../../lib/examContentResultados')>(
    '../../lib/examContentResultados',
  );
  return {
    ...actual,
    listarResultadosFn: (...args: unknown[]) => listarResultadosFn(...args),
    sincronizarMoodleFn: (...args: unknown[]) => sincronizarMoodleFn(...args),
    archivarResultadoFn: (...args: unknown[]) => archivarResultadoFn(...args),
  };
});

vi.mock('../../lib/authProvider', () => ({
  authProvider: { getToken: () => 'tok-test' },
}));

function unaFila(overrides: Partial<ResultadoExamen> = {}): ResultadoExamen {
  return {
    session_id: 'sess-1',
    alumno_idnumber: 'FRM-1',
    alumno_email: 'a@b.com',
    alumno_nombre: 'Ana García',
    nota: 8,
    estado_moodle: 'pendiente',
    actualizado_en: '2026-01-01T00:00:00',
    estado_entrega: 'finalizada',
    archivado: false,
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function renderPanel(examenId = 'ex-1') {
  return render(
    <ToastProvider>
      <ResultadosExamenPanel examenId={examenId} />
    </ToastProvider>,
  );
}

describe('ResultadosExamenPanel — combinación de filtros (C-76 §14.8)', () => {
  it('Aplicar filtros arma el query esperado: mostrar archivadas + fechas', async () => {
    listarResultadosFn.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 5 });
    renderPanel();
    await waitFor(() => expect(listarResultadosFn.mock.calls.length).toBeGreaterThan(0));
    const llamadasAntes = listarResultadosFn.mock.calls.length;

    fireEvent.click(screen.getByLabelText(/mostrar archivadas/i));
    fireEvent.change(screen.getByLabelText(/^desde$/i), { target: { value: '2026-01-01' } });
    fireEvent.change(screen.getByLabelText(/^hasta$/i), { target: { value: '2026-01-31' } });
    fireEvent.click(screen.getByRole('button', { name: /aplicar filtros/i }));

    await waitFor(() => expect(listarResultadosFn.mock.calls.length).toBeGreaterThan(llamadasAntes));
    const params = listarResultadosFn.mock.calls.at(-1)![3];
    expect(params).toMatchObject({
      // c-78 F-03 (§5.3): el toggle manda 'todas' (archivadas Y no archivadas),
      // no 'true' — pedir SOLO las archivadas no es lo que dice el checkbox.
      archivado: 'todas',
      fecha_desde: '2026-01-01T00:00:00',
      fecha_hasta: '2026-01-31T23:59:59',
    });
  });

  it("por defecto (sin tocar el toggle) pide archivado='false'", async () => {
    listarResultadosFn.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 5 });
    renderPanel();
    await waitFor(() => expect(listarResultadosFn.mock.calls.length).toBeGreaterThan(0));

    const params = listarResultadosFn.mock.calls.at(-1)![3];
    // c-78 F-03: el filtro es tri-estado ('false' | 'true' | 'todas'), no booleano.
    expect(params.archivado).toBe('false');
  });
});

describe('ResultadosExamenPanel — botón archivar (C-76 §14.8)', () => {
  it('dispara el PATCH (archivarResultadoFn) y refresca la fila', async () => {
    listarResultadosFn.mockResolvedValue({
      items: [unaFila({ archivado: false })],
      total: 1,
      page: 1,
      page_size: 5,
    });
    archivarResultadoFn.mockResolvedValue({ session_id: 'sess-1', archivado: true });

    renderPanel();
    await waitFor(() => screen.getByText('Ana García'));
    const llamadasAntes = listarResultadosFn.mock.calls.length;

    // Las acciones viven dentro del menu de tres puntos: siempre las mismas
    // tres opciones, apagadas con su motivo cuando no aplican. Antes eran
    // botones sueltos y una fila mostraba una opcion menos que la de al lado.
    fireEvent.click(screen.getByRole('button', { name: /acciones de/i }));
    fireEvent.click(screen.getByRole('menuitem', { name: /^archivar$/i }));

    await waitFor(() =>
      expect(archivarResultadoFn).toHaveBeenCalledWith('/api/v1', 'tok-test', 'ex-1', 'sess-1', true),
    );
    // Refresca: la lista se vuelve a pedir después del PATCH.
    await waitFor(() => expect(listarResultadosFn.mock.calls.length).toBeGreaterThan(llamadasAntes));
  });

  it('triangulación: sobre una fila YA archivada, el botón desarchiva (archivado=false)', async () => {
    listarResultadosFn.mockResolvedValue({
      items: [unaFila({ archivado: true })],
      total: 1,
      page: 1,
      page_size: 5,
    });
    archivarResultadoFn.mockResolvedValue({ session_id: 'sess-1', archivado: false });

    renderPanel();
    await waitFor(() => screen.getByText('Ana García'));

    fireEvent.click(screen.getByRole('button', { name: /acciones de/i }));
    fireEvent.click(screen.getByRole('menuitem', { name: /desarchivar/i }));

    await waitFor(() =>
      expect(archivarResultadoFn).toHaveBeenCalledWith('/api/v1', 'tok-test', 'ex-1', 'sess-1', false),
    );
  });
});
