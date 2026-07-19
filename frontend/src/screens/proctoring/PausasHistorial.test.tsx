import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import type { Pausa } from '../../lib/types';

// C-72 sección 12.10: el sistema puede cerrar una pausa 'solicitada' como
// 'expirada' (timeout o fin de sesión). El historial de la sesión (evidencia
// revisable) DEBE renderizar ese estado sin crashear y sin confundirlo con una
// aprobación/rechazo (L2.5). El bug: ESTADO['expirada'] era undefined → todo el
// historial explotaba en cuanto una sesión tenía una pausa expirada.

const listarPausas = vi.fn();
vi.mock('../../lib/api', () => ({
  api: {
    listarPausas: (id: string) => listarPausas(id),
  },
}));

// Import DESPUÉS del mock para que el módulo tome la versión mockeada de `api`.
const { PausasHistorial } = await import('./PausasHistorial');

afterEach(() => {
  cleanup();
  listarPausas.mockReset();
});

function pausa(over: Partial<Pausa> = {}): Pausa {
  return {
    id: 'p1',
    motivo: 'Fui al baño',
    estado: 'solicitada',
    solicitada_en: '2026-07-17T10:00:00.000Z',
    ...over,
  };
}

describe('PausasHistorial — estado expirada (C-72 sección 12.10)', () => {
  it('renderiza una pausa expirada sin crashear y con etiqueta propia', async () => {
    listarPausas.mockResolvedValue([pausa({ estado: 'expirada' })]);
    render(<PausasHistorial sessionId="s1" />);
    // Etiqueta clara de que la cerró el sistema, NO un veredicto del proctor.
    expect(await screen.findByText('No respondida a tiempo')).toBeTruthy();
  });

  it('una expirada no se rotula como aprobada ni rechazada', async () => {
    listarPausas.mockResolvedValue([pausa({ estado: 'expirada' })]);
    render(<PausasHistorial sessionId="s1" />);
    await screen.findByText('No respondida a tiempo');
    expect(screen.queryByText('Aprobada')).toBeNull();
    expect(screen.queryByText('Rechazada')).toBeNull();
  });

  it('sigue renderizando los estados ya soportados (aprobada)', async () => {
    listarPausas.mockResolvedValue([pausa({ estado: 'aprobada' })]);
    render(<PausasHistorial sessionId="s1" />);
    expect(await screen.findByText('Aprobada')).toBeTruthy();
  });
});
