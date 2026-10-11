import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { CalibracionCard } from './CalibracionCard';
import type { SesionProctoringDetalle } from '../../lib/types';

afterEach(() => cleanup());

function detalleCon(calibracion: SesionProctoringDetalle['calibracion']): SesionProctoringDetalle {
  return { calibracion } as SesionProctoringDetalle;
}

describe('CalibracionCard', () => {
  it('sin calibración no renderiza nada', () => {
    const { container } = render(<CalibracionCard detalle={detalleCon(null)} />);
    expect(container.firstChild).toBeNull();
  });

  it('calibración de 4 esquinas: muestra el rango medido', () => {
    render(
      <CalibracionCard
        detalle={detalleCon({
          centro: { x: 0.02, y: -0.01 },
          rango_x: [-0.22, 0.24],
          rango_y: [-0.55, 0.53],
          origen: 'paso_previo',
          muestras_por_punto: 13,
        })}
      />,
    );
    expect(screen.getByText(/las 4 esquinas/i)).toBeTruthy();
    expect(screen.getByText(/Rango medido/i)).toBeTruthy();
    expect(screen.getByText('13')).toBeTruthy();
  });

  it('calibración de respaldo (un solo punto): NO muestra rango y avisa que no calibró antes', () => {
    render(
      <CalibracionCard
        detalle={detalleCon({
          centro: { x: 0.1, y: 0 },
          rango_x: null,
          rango_y: null,
          origen: 'respaldo',
          muestras_por_punto: 13,
        })}
      />,
    );
    expect(screen.getByText(/No calibró antes de empezar/i)).toBeTruthy();
    expect(screen.queryByText(/Rango medido/i)).toBeNull();
  });
});
