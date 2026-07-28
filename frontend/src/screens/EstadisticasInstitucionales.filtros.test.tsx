/**
 * C-20 task 4.4 — los filtros de la UI están CABLEADOS al endpoint.
 *
 * Verifica el flujo real: al elegir una materia y presionar "Aplicar filtros",
 * la página vuelve a pedir el resumen con ese filtro (borrador → aplicado). El
 * StaffShell se mockea a un passthrough para no arrastrar router/auth: lo que se
 * testea es el cableado filtro → fetch, no el chrome de la pantalla.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, fireEvent, waitFor } from '@testing-library/react';
import type { ResumenStats } from '../lib/types';

// Shell = passthrough (evita el router/auth del chrome; ignora el prop `help`).
vi.mock('../ui/shells', () => ({
  StaffShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

// api mockeado: no hay red. obtenerResumenStats es el espía del cableado.
// El selector de materias se puebla desde `materiasDisponibles` (catálogo real),
// NO desde el desglose `por_materia` del resumen: una materia sin sesiones
// rendidas también tiene que poder filtrarse.
vi.mock('../lib/api', () => ({
  api: {
    obtenerResumenStats: vi.fn(),
    listarExamenesContenido: vi.fn(),
    materiasDisponibles: vi.fn(),
    comisionesDeMateria: vi.fn(),
  },
}));

import EstadisticasInstitucionales from './EstadisticasInstitucionales';
import { api } from '../lib/api';

const RESUMEN: ResumenStats = {
  total_examenes: 2,
  total_materias: 1,
  total_comisiones: 1,
  total_sesiones: 3,
  sesiones_finalizadas: 2,
  sesiones_en_riesgo: 1,
  umbral_riesgo: 40,
  // Bandas: la última arranca en el umbral vivo (acá 40), no en un 70 fijo.
  distribucion_scores: { '0-24': 2, '25-39': 0, '40-100': 1 },
  por_materia: [{ materia_id: 'm-1', nombre: 'Álgebra', sesiones: 2, en_riesgo: 1 }],
  top_eventos: [],
  por_dia: [],
  decisiones: {},
};

beforeEach(() => {
  vi.mocked(api.obtenerResumenStats).mockResolvedValue(RESUMEN);
  vi.mocked(api.listarExamenesContenido).mockResolvedValue([]);
  vi.mocked(api.materiasDisponibles).mockResolvedValue([
    { id: 'm-1', nombre: 'Álgebra' } as never,
  ]);
  vi.mocked(api.comisionesDeMateria).mockResolvedValue([]);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('EstadisticasInstitucionales — filtros cableados al endpoint (4.4)', () => {
  it('al aplicar una materia, re-pide el resumen con ese filtro', async () => {
    render(<EstadisticasInstitucionales />);

    // Carga inicial: pide SIN filtro y puebla el selector de materias.
    await waitFor(() =>
      expect(api.obtenerResumenStats).toHaveBeenCalledWith({}),
    );
    await screen.findByRole('option', { name: 'Álgebra' });

    // Elijo la materia → aparece "Aplicar filtros" (hay cambios pendientes).
    fireEvent.change(screen.getByLabelText('Materia'), { target: { value: 'm-1' } });
    const aplicar = await screen.findByRole('button', { name: /aplicar filtros/i });
    fireEvent.click(aplicar);

    // El fetch se re-dispara CON el filtro aplicado.
    await waitFor(() =>
      expect(api.obtenerResumenStats).toHaveBeenLastCalledWith({ materia_id: 'm-1' }),
    );
  });

  it('sin cambios en el borrador, no aparece "Aplicar filtros"', async () => {
    render(<EstadisticasInstitucionales />);
    await screen.findByRole('option', { name: 'Álgebra' });

    // Recién cargado, borrador == aplicado (ambos vacíos) → nada que aplicar.
    expect(screen.queryByRole('button', { name: /aplicar filtros/i })).toBeNull();
  });
});
