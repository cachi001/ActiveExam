import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { EventoCard } from './EventoCard';
import type { EventoProctoringDetalle } from '../../lib/types';

// C-72 sección 7.6: la DURACIÓN de ausencia de una reanudación (medida server-side,
// regla #6) debe ser VISIBLE y legible en el contexto de revisión de la sesión. El
// backend la deja en el payload como `ausencia_seg` (segundos). El revisor tiene que
// leerla clara, no como un número crudo sin unidad.
afterEach(cleanup);

function ev(over: Partial<EventoProctoringDetalle> = {}): EventoProctoringDetalle {
  return {
    evento_id: 'e1',
    tipo: 'reanudacion_tardia',
    severidad: 'media',
    ts_cliente: '2026-07-17T10:00:00.000Z',
    ...over,
  };
}

describe('EventoCard — duración de ausencia en revisión (C-72 sección 7.6)', () => {
  it('muestra la ausencia con etiqueta legible y minutos+segundos', () => {
    render(<EventoCard evento={ev({ payload: { ausencia_seg: 75, origen: 'server' } })} />);
    expect(screen.getByText(/Duración de ausencia/)).toBeTruthy();
    expect(screen.getByText('1 min 15 s')).toBeTruthy();
  });

  it('ausencia sub-minuto se muestra en segundos', () => {
    render(<EventoCard evento={ev({ payload: { ausencia_seg: 45, origen: 'server' } })} />);
    expect(screen.getByText('45 s')).toBeTruthy();
  });

  it('no ensucia la revisión con la clave interna `origen`', () => {
    render(<EventoCard evento={ev({ payload: { ausencia_seg: 45, origen: 'server' } })} />);
    expect(screen.queryByText('server')).toBeNull();
  });
});
