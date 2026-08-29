/**
 * El encabezado del modal de ayuda nombra la ayuda Y la sección.
 *
 * Mostraba solo el nombre de la sección ("Mis exámenes"), igual que el título de
 * la página que estaba detrás: abierto el diálogo, no quedaba claro que eso era
 * la ayuda y no otra pantalla. Pedido del dueño (28/8/2026): que diga
 * `Ayuda «Sección»`.
 *
 * Se arregla en el componente y no en cada pantalla: hay 26 `<HelpButton>` en la
 * app y prefijar el texto en cada uno los deja desincronizados al primer olvido.
 */

import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { HelpButton } from './HelpButton';

afterEach(() => cleanup());

const abrir = (title = 'Mis exámenes') => {
  render(<HelpButton title={title}>Contenido de la ayuda</HelpButton>);
  fireEvent.click(screen.getByRole('button', { name: /ayuda/i }));
};

describe('HelpButton', () => {
  it('el encabezado dice que es la ayuda de esa sección', () => {
    abrir();
    expect(screen.getByRole('heading').textContent).toBe('Ayuda «Mis exámenes»');
  });

  it('el nombre de la sección lo sigue poniendo quien lo usa', () => {
    abrir('Banco de preguntas');
    expect(screen.getByRole('heading').textContent).toContain('Banco de preguntas');
  });

  it('sigue mostrando el contenido de la ayuda', () => {
    abrir();
    expect(screen.getByText('Contenido de la ayuda')).toBeTruthy();
  });

  it('cerrado no deja el diálogo montado', () => {
    render(<HelpButton title="Mis exámenes">Contenido</HelpButton>);
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});
