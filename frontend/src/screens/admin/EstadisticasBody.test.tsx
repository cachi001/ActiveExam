/**
 * TDD: RED → GREEN → TRIANGULATE
 * Cuerpo presentacional de la página de estadísticas (C-20, tasks 4.2 + 4.3).
 *
 * Contrato de carga resiliente (C-73): cargando / error / vacío-real / cargado.
 * Lo CRÍTICO: un fetch fallido se muestra como ERROR (con reintentar), NUNCA
 * como datos en cero. Prop-driven → se testea sin red ni router (los estados
 * llegan por props; el fetch vive en la página que envuelve este cuerpo).
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, fireEvent } from '@testing-library/react';
import { EstadisticasBody } from './EstadisticasBody';
import type { ResumenStats } from '../../lib/types';

afterEach(cleanup);

const RESUMEN: ResumenStats = {
  total_examenes: 12,
  total_materias: 4,
  total_comisiones: 7,
  total_sesiones: 30,
  sesiones_finalizadas: 25,
  sesiones_en_riesgo: 3,
  umbral_riesgo: 70,
  distribucion_scores: { '0-24': 18, '25-49': 6, '50-69': 3, '70-100': 3 },
};

describe('EstadisticasBody — contrato de carga resiliente', () => {
  it('estado CARGANDO: muestra un indicador de carga, no cards en cero', () => {
    render(<EstadisticasBody cargando error={null} data={null} onReintentar={() => {}} />);
    expect(screen.getByText(/cargando/i)).toBeTruthy();
    expect(screen.queryByText('Materias')).toBeNull();
  });

  it('estado CARGADO: renderiza las stat cards con los valores del endpoint', () => {
    render(<EstadisticasBody cargando={false} error={null} data={RESUMEN} onReintentar={() => {}} />);
    expect(screen.getByText('Exámenes')).toBeTruthy();
    expect(screen.getByText('12')).toBeTruthy(); // total_examenes
    expect(screen.getByText('4')).toBeTruthy(); // total_materias
    expect(screen.getByText('7')).toBeTruthy(); // total_comisiones
    // La banda de riesgo se muestra pero como conteo, no como veredicto (L2.5).
    expect(screen.getByText(/en riesgo/i)).toBeTruthy();
  });

  it('estado ERROR: muestra el mensaje + Reintentar y NO muestra stat cards (no "0" fantasma)', () => {
    render(
      <EstadisticasBody
        cargando={false}
        error="No se pudieron cargar las estadísticas."
        data={null}
        onReintentar={() => {}}
      />,
    );
    expect(screen.getByText(/no se pudieron cargar/i)).toBeTruthy();
    expect(screen.getByRole('button', { name: /reintentar/i })).toBeTruthy();
    // Un fetch fallido NUNCA se muestra como datos: sin cards ni ceros.
    expect(screen.queryByText('Materias')).toBeNull();
    expect(screen.queryByText('Exámenes')).toBeNull();
  });

  it('Reintentar dispara onReintentar', () => {
    const onReintentar = vi.fn();
    render(
      <EstadisticasBody cargando={false} error="falló" data={null} onReintentar={onReintentar} />,
    );
    fireEvent.click(screen.getByRole('button', { name: /reintentar/i }));
    expect(onReintentar).toHaveBeenCalledOnce();
  });

  it('estado VACÍO-REAL: fetch OK sin sesiones → cards en 0 + aviso de sin datos (no error)', () => {
    const vacio: ResumenStats = {
      total_examenes: 0,
      total_materias: 0,
      total_comisiones: 0,
      total_sesiones: 0,
      sesiones_finalizadas: 0,
      sesiones_en_riesgo: 0,
      umbral_riesgo: 70,
      distribucion_scores: { '0-24': 0, '25-49': 0, '50-69': 0, '70-100': 0 },
    };
    render(<EstadisticasBody cargando={false} error={null} data={vacio} onReintentar={() => {}} />);
    // Cero es honesto acá (el fetch fue OK). No hay banner de error.
    expect(screen.queryByText(/no se pudieron cargar/i)).toBeNull();
    // Avisa que todavía no hay sesiones rendidas (aviso de vacío-real, no error).
    expect(screen.getByText(/no hay sesiones rendidas/i)).toBeTruthy();
    // NUEVO contrato: el dashboard COMPLETO queda visible aunque no haya datos —
    // no se colapsa a una sola card. Cada panel resuelve su propio "sin datos".
    expect(screen.getByText('Detectores más frecuentes')).toBeTruthy();
    expect(screen.getByText('Estado de revisión')).toBeTruthy();
    expect(screen.getByText('Sesiones por materia')).toBeTruthy();
    expect(screen.getByText('Actividad por día')).toBeTruthy();
  });
});
