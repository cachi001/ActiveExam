import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { EventoCard } from './EventoCard';
import type { EventoProctoringDetalle } from '../../lib/types';

// C-72 sección 9: el bloque de conteo de rostros cliente/servidor se muestra SOLO
// con discrepancia (cliente ≠ servidor) Y captura (screenshot). Coinciden o sin
// imagen → no aporta señal revisable, se oculta. Ningún evento se oculta.
afterEach(cleanup);

function ev(over: Partial<EventoProctoringDetalle> = {}): EventoProctoringDetalle {
  return {
    evento_id: 'e1',
    tipo: 'copiar_pegar',
    severidad: 'media',
    ts_cliente: '2026-07-17T10:00:00.000Z',
    ...over,
  };
}

describe('EventoCard — bloque de conteo de rostros (C-72 sección 9)', () => {
  it('9.3 muestra el conteo con discrepancia Y captura', () => {
    render(
      <EventoCard
        evento={ev({ face_count_cliente: 2, face_count_servidor: 1, screenshot_base64: 'imgdata' })}
      />,
    );
    expect(screen.queryByText(/Rostros detectados/i)).toBeTruthy();
  });

  it('9.1 NO muestra el conteo cuando cliente y servidor coinciden', () => {
    render(
      <EventoCard
        evento={ev({ face_count_cliente: 1, face_count_servidor: 1, screenshot_base64: 'imgdata' })}
      />,
    );
    expect(screen.queryByText(/Rostros detectados/i)).toBeNull();
  });

  it('9.2 NO muestra el conteo con discrepancia pero SIN captura', () => {
    render(
      <EventoCard
        evento={ev({ face_count_cliente: 2, face_count_servidor: 1, screenshot_base64: null })}
      />,
    );
    expect(screen.queryByText(/Rostros detectados/i)).toBeNull();
  });

  it('9.4 el evento se renderiza igual aunque no se muestre el conteo', () => {
    const { container } = render(
      <EventoCard evento={ev({ face_count_cliente: 1, face_count_servidor: 1 })} />,
    );
    // la tarjeta renderiza contenido (el evento nunca se oculta), sin el bloque de conteo
    expect(container.textContent && container.textContent.length > 0).toBe(true);
    expect(screen.queryByText(/Rostros detectados/i)).toBeNull();
  });
});
