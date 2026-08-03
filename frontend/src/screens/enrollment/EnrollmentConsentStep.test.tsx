/**
 * Carga resiliente del paso de consentimiento (C-73, sección 2.4). Lo crítico:
 * si `getConsentText()` FALLA, la pantalla NO puede quedar en un spinner eterno
 * (el patrón viejo `.then(setTexto)` sin `.catch` dejaba `texto` en null para
 * siempre → "Cargando consentimiento…" infinito). Debe mostrar un estado de
 * error con reintento, sin degradar el flujo legal.
 *
 * @vitest-environment jsdom
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor, fireEvent } from '@testing-library/react';
import { EnrollmentConsentStep } from './EnrollmentConsentStep';
import { api } from '../../lib/api';
import type { ConsentTextResponse } from '../../lib/types';

const TEXTO: ConsentTextResponse = {
  version: 'v3',
  hash_texto: 'abc123',
  bloques: [{ titulo: 'Finalidad', cuerpo: 'Supervisar evaluaciones.' }],
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('EnrollmentConsentStep — carga resiliente', () => {
  it('éxito: renderiza la versión y los bloques del texto', async () => {
    vi.spyOn(api, 'getConsentText').mockResolvedValue(TEXTO);
    render(<EnrollmentConsentStep acuseActual={null} onConsentido={vi.fn()} />);
    // 'Finalidad' (título de bloque) es único → prueba el render "ready".
    await waitFor(() => expect(screen.getByText('Finalidad')).toBeTruthy());
    // La versión aparece en el badge y en el texto del checkbox.
    expect(screen.getAllByText(/versión v3/i).length).toBeGreaterThanOrEqual(1);
  });

  it('error: si getConsentText rechaza, muestra error + reintento (NO spinner eterno)', async () => {
    vi.spyOn(api, 'getConsentText').mockRejectedValue(new Error('red caída'));
    render(<EnrollmentConsentStep acuseActual={null} onConsentido={vi.fn()} />);

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /reintentar/i })).toBeTruthy(),
    );
    // No debe quedar el spinner de carga.
    expect(screen.queryByText(/Cargando consentimiento/i)).toBeNull();
  });

  it('reintentar: tras un fallo, el botón re-dispara y carga el texto', async () => {
    const spy = vi
      .spyOn(api, 'getConsentText')
      .mockRejectedValueOnce(new Error('red caída'))
      .mockResolvedValueOnce(TEXTO);
    render(<EnrollmentConsentStep acuseActual={null} onConsentido={vi.fn()} />);

    const btn = await screen.findByRole('button', { name: /reintentar/i });
    fireEvent.click(btn);

    // 'Finalidad' (título de bloque) es único; 'Versión v3' aparece en el badge
    // y en el texto del checkbox → ambiguo.
    await waitFor(() => expect(screen.getByText('Finalidad')).toBeTruthy());
    expect(spy).toHaveBeenCalledTimes(2);
  });
});
