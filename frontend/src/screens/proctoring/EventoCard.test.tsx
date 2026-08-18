import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { EventoCard } from './EventoCard';
import type { EventoProctoringDetalle } from '../../lib/types';

// Fix UX (ronda 5): el bloque de conteo de rostros cliente/servidor es el "por
// qué" del veredicto "no coincide" — se muestra SIEMPRE que haya discrepancia
// (cliente ≠ servidor), CON o SIN captura (antes se ocultaba sin captura, y el
// revisor veía "no coincide" sin ninguna pista de qué había diferido). El texto
// "No coinciden" (ronda 6) se sacó del bloque de conteo por estar duplicado con
// el badge "No coincide con el navegador" — el conteo se detecta ahora por el
// chip "Navegador" / "Servidor".
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

describe('EventoCard — bloque de conteo de rostros', () => {
  it('muestra el conteo con discrepancia Y captura', () => {
    render(
      <EventoCard
        evento={ev({ face_count_cliente: 2, face_count_servidor: 1, screenshot_base64: 'imgdata' })}
      />,
    );
    expect(screen.queryByText(/Navegador/i)).toBeTruthy();
  });

  it('NO muestra el conteo cuando cliente y servidor coinciden', () => {
    render(
      <EventoCard
        evento={ev({ face_count_cliente: 1, face_count_servidor: 1, screenshot_base64: 'imgdata' })}
      />,
    );
    expect(screen.queryByText(/Navegador/i)).toBeNull();
  });

  it('muestra el conteo con discrepancia aunque NO haya captura (es el "por qué")', () => {
    render(
      <EventoCard
        evento={ev({ face_count_cliente: 2, face_count_servidor: 1, screenshot_base64: null })}
      />,
    );
    expect(screen.queryByText(/Navegador/i)).toBeTruthy();
  });

  it('el evento se renderiza igual aunque no se muestre el conteo', () => {
    const { container } = render(
      <EventoCard evento={ev({ face_count_cliente: 1, face_count_servidor: 1 })} />,
    );
    // la tarjeta renderiza contenido (el evento nunca se oculta), sin el bloque de conteo
    expect(container.textContent && container.textContent.length > 0).toBe(true);
    expect(screen.queryByText(/Navegador/i)).toBeNull();
  });
});

// C-76 (15.5): leyenda "contexto, no prueba automática" en cambio_pestana/copiar_pegar
// cuando hay captura — para que un revisor no lo lea como confirmación del evento.
describe('EventoCard — leyenda de captura contextual (C-76 15.5)', () => {
  it('muestra la leyenda en copiar_pegar CON captura', () => {
    render(<EventoCard evento={ev({ tipo: 'copiar_pegar', screenshot_base64: 'imgdata' })} />);
    expect(screen.queryByText(/contexto para revisión/i)).toBeTruthy();
  });

  it('muestra la leyenda en cambio_pestana CON captura', () => {
    render(<EventoCard evento={ev({ tipo: 'cambio_pestana', screenshot_base64: 'imgdata' })} />);
    expect(screen.queryByText(/contexto para revisión/i)).toBeTruthy();
  });

  it('NO muestra la leyenda en copiar_pegar SIN captura', () => {
    render(<EventoCard evento={ev({ tipo: 'copiar_pegar', screenshot_base64: null })} />);
    expect(screen.queryByText(/contexto para revisión/i)).toBeNull();
  });

  it('NO muestra la leyenda en eventos de visión (multiples_rostros) aunque haya captura', () => {
    // multiples_rostros SÍ se re-infiere server-side sobre la MISMA imagen — no es
    // "solo contexto", es prueba directa. La leyenda no debe aparecer acá.
    render(<EventoCard evento={ev({ tipo: 'multiples_rostros', screenshot_base64: 'imgdata' })} />);
    expect(screen.queryByText(/contexto para revisión/i)).toBeNull();
  });

  it('muestra el hash de clipboard truncado cuando está presente en el payload', () => {
    const hash = 'a'.repeat(64);
    render(
      <EventoCard
        evento={ev({
          tipo: 'copiar_pegar',
          screenshot_base64: 'imgdata',
          payload: { accion: 'paste', clipboard_sha256: hash },
        })}
      />,
    );
    expect(screen.queryByText(/Hash de lo pegado/i)).toBeTruthy();
    expect(screen.queryByText(hash)).toBeNull(); // truncado, no el hash completo
  });
});
