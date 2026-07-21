import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, fireEvent, waitFor } from '@testing-library/react';
import MoodleImportPage from './MoodleImportPage';
import { invalidateCache } from '../../lib/useCachedData';

// Espiamos la invalidación del cache: importar un examen deja obsoleta la lista
// compartida `examenes-contenido` (la leen AdminDashboard y otras pantallas vía
// useCachedData), así que la mutación debe invalidarla (C-73, sección 5.4).
vi.mock('../../lib/useCachedData', async (orig) => {
  const actual = await orig<typeof import('../../lib/useCachedData')>();
  return { ...actual, invalidateCache: vi.fn(actual.invalidateCache) };
});

// Sin cleanup entre tests los render() se acumulan en el DOM y las queries
// (getByRole/getByLabelText) encuentran múltiples coincidencias. Limpiamos
// después de cada test para aislarlos.
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.mocked(invalidateCache).mockClear();
});

describe('MoodleImportPage', () => {
  it('renders without crashing', () => {
    render(<MoodleImportPage />);
    expect(screen.getByText('Importar examen desde Moodle XML')).toBeTruthy();
  });

  it('shows file input and submit button', () => {
    render(<MoodleImportPage />);
    expect(screen.getByLabelText(/Archivo XML de Moodle/i)).toBeTruthy();
    expect(screen.getByRole('button', { name: /Importar/i })).toBeTruthy();
  });

  it('button is disabled without a file selected', () => {
    render(<MoodleImportPage />);
    const btn = screen.getByRole('button', { name: /Importar/i }) as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });

  it('shows optional titulo input', () => {
    render(<MoodleImportPage />);
    expect(screen.getByLabelText(/Título del examen/i)).toBeTruthy();
  });

  it('tras un import exitoso invalida la lista compartida de exámenes (examenes-contenido)', async () => {
    // fetch OK: el POST del import devuelve el reporte; cualquier otra llamada
    // (getMoodleTarget) también resuelve OK y no interfiere con lo que medimos.
    const fetchMock = vi.fn((url: string) => {
      if (typeof url === 'string' && url.includes('/exam-content/moodle-import')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ examen_id: 'ex-1', importadas: 10, omitidas: [] }),
        } as Response);
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) } as Response);
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<MoodleImportPage />);
    const input = screen.getByLabelText(/Archivo XML de Moodle/i) as HTMLInputElement;
    const archivo = new File(['<quiz></quiz>'], 'examen.xml', { type: 'text/xml' });
    fireEvent.change(input, { target: { files: [archivo] } });

    fireEvent.click(screen.getByRole('button', { name: /Importar/i }));

    await waitFor(() => expect(vi.mocked(invalidateCache)).toHaveBeenCalledWith('examenes-contenido'));
    vi.unstubAllGlobals();
  });
});
