/**
 * Tests — SeccionProctoring (c-76 bloque 4.3)
 *
 * Cubre el campo "Pausas máximas por sesión" (pausas_max_por_sesion):
 *  a) default 2 cuando el backend no lo manda
 *  b) valor cargado desde la config efectiva se refleja en el input
 *  c) guardar envía pausas_max_por_sesion en el PATCH
 *
 * TDD Cycle: RED → GREEN → TRIANGULATE → REFACTOR
 * Framework: vitest + @testing-library/react. Front puro (regla dura #4 no aplica).
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('../../ui/toast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}));

vi.mock('../../config/effectiveConfigCache', () => ({
  resetEffectiveConfigCache: vi.fn(),
}));

vi.mock('../admin/components/DetectoresSelector', () => ({
  default: () => <div data-testid="detectores-selector" />,
}));

const mockObtenerConfigEfectiva = vi.fn();
const mockEditarConfigSistema = vi.fn();
vi.mock('../../lib/api', () => ({
  api: {
    obtenerConfigEfectiva: (...args: unknown[]) => mockObtenerConfigEfectiva(...args),
    editarConfigSistema: (...args: unknown[]) => mockEditarConfigSistema(...args),
  },
}));

import SeccionProctoring from './SeccionProctoring';

const CONFIG_BASE = {
  version: 1,
  umbral_cola_revision: 70,
  detectores_activos: ['rostro_ausente'],
  chat_habilitado: true,
  pausas_habilitadas: true,
  pausa_max_min: 10,
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('SeccionProctoring — pausas_max_por_sesion (c-76 bloque 4)', () => {
  it('usa el default 2 cuando el backend no manda pausas_max_por_sesion', async () => {
    mockObtenerConfigEfectiva.mockResolvedValue({ ...CONFIG_BASE });
    render(<SeccionProctoring />);
    const input = await screen.findByLabelText('Cantidad máxima de pausas por sesión');
    expect((input as HTMLInputElement).value).toBe('2');
  });

  it('refleja el valor cargado desde la config efectiva', async () => {
    mockObtenerConfigEfectiva.mockResolvedValue({ ...CONFIG_BASE, pausas_max_por_sesion: 5 });
    render(<SeccionProctoring />);
    const input = await screen.findByLabelText('Cantidad máxima de pausas por sesión');
    expect((input as HTMLInputElement).value).toBe('5');
  });

  it('guardar envía pausas_max_por_sesion en el PATCH', async () => {
    mockObtenerConfigEfectiva.mockResolvedValue({ ...CONFIG_BASE, pausas_max_por_sesion: 2 });
    mockEditarConfigSistema.mockResolvedValue({});
    render(<SeccionProctoring />);
    const input = await screen.findByLabelText('Cantidad máxima de pausas por sesión');
    fireEvent.change(input, { target: { value: '3' } });

    const guardar = await screen.findByRole('button', { name: /guardar parámetros/i });
    fireEvent.click(guardar);

    await waitFor(() => {
      expect(mockEditarConfigSistema).toHaveBeenCalledWith(
        expect.objectContaining({ pausas_max_por_sesion: 3 }),
      );
    });
  });
});
