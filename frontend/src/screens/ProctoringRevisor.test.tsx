/**
 * Tests — ProctoringRevisor (C-76 tarea 17: Registro de sesiones — tabla +
 * paginación real + filtros server-side, reemplaza el agrupado-por-examen-con-cards).
 *
 * Cubre lo pedido en tasks.md §17.6:
 *  - la tabla renderiza filas reales (alumno/examen/fecha/eventos/discrepancias/score)
 *  - los filtros arman el query esperado (query real hacia listarRegistroSesionesFn)
 *  - la paginación navega correctamente (Pagination -> page siguiente)
 *  - CERO strings de examen/estado hardcodeados: el <select> de "Examen" sale
 *    ÚNICAMENTE del catálogo devuelto por listarExamenesConSesionesFn (nunca de
 *    un array escrito a mano en el componente).
 *
 * Framework: vitest + @testing-library/react. Mocks: lib/proctoringRegistro,
 * lib/authProvider, lib/api (solo API_BASE), lib/router, lib/store, ui/shells.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { SesionProctoringResumen } from '../lib/types';

const here = dirname(fileURLToPath(import.meta.url));

const listarRegistroSesionesFn = vi.fn();
const listarExamenesConSesionesFn = vi.fn();
const eliminarSesionTestFn = vi.fn();

vi.mock('../lib/proctoringRegistro', () => ({
  listarRegistroSesionesFn: (...args: unknown[]) => listarRegistroSesionesFn(...args),
  listarExamenesConSesionesFn: (...args: unknown[]) => listarExamenesConSesionesFn(...args),
  eliminarSesionTestFn: (...args: unknown[]) => eliminarSesionTestFn(...args),
}));

const listarMateriasFn = vi.fn();
const listarComisionesFn = vi.fn();

vi.mock('../lib/examContentBrowse', () => ({
  listarMateriasFn: (...args: unknown[]) => listarMateriasFn(...args),
  listarComisionesFn: (...args: unknown[]) => listarComisionesFn(...args),
}));

vi.mock('../lib/authProvider', () => ({
  authProvider: { getToken: () => 'tok-test' },
}));

vi.mock('../lib/api', () => ({ API_BASE: '/api/v1' }));

const toastSuccess = vi.fn();
const toastWarning = vi.fn();
vi.mock('../ui/toast', () => ({
  useToast: () => ({ success: toastSuccess, warning: toastWarning, error: vi.fn(), info: vi.fn(), show: vi.fn(), dismiss: vi.fn() }),
}));

vi.mock('../lib/store', () => ({
  useApp: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({ setProctoringSessionId: vi.fn(), setProctoringDetailBackRoute: vi.fn() }),
}));

const navigate = vi.fn();
vi.mock('../lib/router', () => ({ useNavigate: () => navigate }));

// StaffShell = passthrough (evita el chrome/nav real): lo que se testea es la
// tabla y los filtros, no el shell.
vi.mock('../ui/shells', () => ({
  StaffShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import ProctoringRevisor from './ProctoringRevisor';

function unaSesion(overrides: Partial<SesionProctoringResumen> = {}): SesionProctoringResumen {
  return {
    id: 'sess-1',
    modo: 'examen',
    creada_en: '2026-01-10T10:00:00Z',
    finalizada_en: '2026-01-10T11:00:00Z',
    total_eventos: 4,
    total_discrepancias: 1,
    score: 20,
    examen_titulo: 'Parcial 1',
    materia_nombre: 'Álgebra',
    comision_nombre: 'C1',
    alumno_nombre: 'Ana Gómez',
    alumno_idnumber: 'LU-1',
    alumno_email: 'ana@uni.edu',
    ...overrides,
  };
}

beforeEach(() => {
  listarMateriasFn.mockResolvedValue([]);
  listarComisionesFn.mockResolvedValue([]);
  eliminarSesionTestFn.mockResolvedValue(undefined);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('ProctoringRevisor — tabla renderiza filas reales', () => {
  it('muestra alumno, examen, eventos, discrepancias y score de la respuesta real', async () => {
    listarRegistroSesionesFn.mockResolvedValue({
      items: [unaSesion(), unaSesion({ id: 'sess-2', alumno_nombre: 'Beto Ruiz', score: 80 })],
      total: 2,
      page: 1,
      page_size: 20,
    });
    listarExamenesConSesionesFn.mockResolvedValue([{ id: 'exam-1', titulo: 'Parcial 1' }]);

    render(<ProctoringRevisor />);

    await waitFor(() => expect(screen.getByText('Ana Gómez')).toBeTruthy());
    expect(screen.getByText('Beto Ruiz')).toBeTruthy();
    expect(screen.getAllByText('Parcial 1').length).toBeGreaterThan(0);
    expect(screen.getAllByText('4').length).toBeGreaterThan(0); // eventos
  });

  it('sin resultados muestra el estado vacío, no filas fantasma', async () => {
    listarRegistroSesionesFn.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
    listarExamenesConSesionesFn.mockResolvedValue([]);

    render(<ProctoringRevisor />);

    await waitFor(() => expect(listarRegistroSesionesFn).toHaveBeenCalled());
    expect(screen.getByText(/todavía no hay sesiones finalizadas/i)).toBeTruthy();
  });
});

describe('ProctoringRevisor — columnas Materia/Comisión (C-76 tarea 19.2)', () => {
  it('muestra materia y comisión cuando el backend las manda', async () => {
    listarRegistroSesionesFn.mockResolvedValue({
      items: [unaSesion({ materia_nombre: 'Álgebra', comision_nombre: 'C1' })],
      total: 1,
      page: 1,
      page_size: 20,
    });
    listarExamenesConSesionesFn.mockResolvedValue([]);

    render(<ProctoringRevisor />);

    await waitFor(() => expect(screen.getByText('Álgebra')).toBeTruthy());
    expect(screen.getByText('C1')).toBeTruthy();
  });

  it('muestra un placeholder claro cuando materia/comisión vienen null', async () => {
    listarRegistroSesionesFn.mockResolvedValue({
      items: [unaSesion({ id: 'sess-null', materia_nombre: null, comision_nombre: null })],
      total: 1,
      page: 1,
      page_size: 20,
    });
    listarExamenesConSesionesFn.mockResolvedValue([]);

    render(<ProctoringRevisor />);

    await waitFor(() => expect(screen.getAllByText('—').length).toBeGreaterThan(0));
  });
});

describe('ProctoringRevisor — stat cards de resumen (C-76 tarea 20.6)', () => {
  it('renderiza los agregados devueltos por el backend, no un cálculo propio sobre items', async () => {
    // `items` trae solo 1 sesión (la página), pero los agregados del backend
    // reflejan el TOTAL filtrado (12 sesiones, 5 sobre el umbral de riesgo).
    // Si el componente recalculara sumando `items`, estos números no matchearían.
    listarRegistroSesionesFn.mockResolvedValue({
      items: [unaSesion({ total_eventos: 4, total_discrepancias: 1 })],
      total: 12,
      page: 1,
      page_size: 1,
      riesgo_bajo: 8,
      riesgo_medio: 3,
      riesgo_alto: 1,
      en_cola_revision: 1,
    });
    listarExamenesConSesionesFn.mockResolvedValue([]);

    render(<ProctoringRevisor />);

    await waitFor(() => expect(screen.getAllByText('12').length).toBeGreaterThan(0)); // sesiones finalizadas = total
    expect(screen.getAllByText('1').length).toBeGreaterThan(0); // sobre el umbral de riesgo
  });

  it('el componente fuente ya no arma stat cards con la métrica "discrepancias" ni chips de riesgo bajo/medio/alto (feedback 2026-08-18)', () => {
    // Verificación estructural (no de render): el catálogo de métricas de la
    // card de resumen ya NO invoca la clave 'discrepancias' — reemplazada por
    // 'enColaRevision', vía la API pública `statProps` (no acceso directo a
    // STAT_META). Tampoco debe quedar ningún chip agregado de riesgo bajo/medio/
    // alto (el dueño pidió sacarlos — el desglose por fila en la tabla alcanza).
    const fuente = readFileSync(join(here, 'ProctoringRevisor.tsx'), 'utf-8');
    expect(fuente).not.toMatch(/STAT_META\.discrepancias|statProps\('discrepancias'/);
    expect(fuente).toMatch(/statProps\('enColaRevision'/);
    expect(fuente).not.toMatch(/Bajo \{agregados\.riesgo_bajo\}|Medio \{agregados\.riesgo_medio\}|Alto \{agregados\.riesgo_alto\}/);
  });
});

describe('ProctoringRevisor — filtros Materia/Comisión en cascada (C-76 tarea 20.7)', () => {
  it('la Comisión arranca deshabilitada y se habilita al elegir Materia', async () => {
    listarRegistroSesionesFn.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
    listarExamenesConSesionesFn.mockResolvedValue([]);
    listarMateriasFn.mockResolvedValue([{ id: 'mat-1', codigo: 'MAT-1', nombre: 'Álgebra' }]);
    listarComisionesFn.mockResolvedValue([{ id: 'com-1', codigo: 'C1', nombre: 'Comisión 1' }]);

    render(<ProctoringRevisor />);

    const selectComision = await screen.findByLabelText(/^comisión$/i) as HTMLSelectElement;
    expect(selectComision.disabled).toBe(true);

    fireEvent.change(await screen.findByLabelText(/^materia$/i), { target: { value: 'mat-1' } });

    await waitFor(() => expect(listarComisionesFn).toHaveBeenCalledWith('/api/v1', 'tok-test', 'mat-1'));
    await waitFor(() => expect(selectComision.disabled).toBe(false));
  });

  it('Aplicar filtros incluye materia_id y comision_id en la llamada', async () => {
    listarRegistroSesionesFn.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
    listarExamenesConSesionesFn.mockResolvedValue([]);
    listarMateriasFn.mockResolvedValue([{ id: 'mat-1', codigo: 'MAT-1', nombre: 'Álgebra' }]);
    listarComisionesFn.mockResolvedValue([{ id: 'com-1', codigo: 'C1', nombre: 'Comisión 1' }]);

    render(<ProctoringRevisor />);

    fireEvent.change(await screen.findByLabelText(/^materia$/i), { target: { value: 'mat-1' } });
    await waitFor(() => expect(listarComisionesFn).toHaveBeenCalled());
    fireEvent.change(await screen.findByLabelText(/^comisión$/i), { target: { value: 'com-1' } });
    fireEvent.click(screen.getByRole('button', { name: /aplicar filtros/i }));

    await waitFor(() => {
      const ultima = listarRegistroSesionesFn.mock.calls.at(-1)?.[2];
      expect(ultima).toMatchObject({ materia_id: 'mat-1', comision_id: 'com-1' });
    });
  });
});

describe('ProctoringRevisor — Eliminar sesión de test (C-76 tarea 20.8)', () => {
  it('el botón Eliminar NO aparece en filas modo=examen', async () => {
    listarRegistroSesionesFn.mockResolvedValue({
      items: [unaSesion({ modo: 'examen' })],
      total: 1, page: 1, page_size: 20,
    });
    listarExamenesConSesionesFn.mockResolvedValue([]);

    render(<ProctoringRevisor />);

    await waitFor(() => expect(screen.getByText('Ana Gómez')).toBeTruthy());
    expect(screen.queryByTitle('Eliminar sesión de diagnóstico')).toBeNull();
  });

  it('el botón Eliminar aparece en filas modo=test y dispara el DELETE tras confirmar', async () => {
    listarRegistroSesionesFn.mockResolvedValue({
      items: [unaSesion({ modo: 'test' })],
      total: 1, page: 1, page_size: 20,
    });
    listarExamenesConSesionesFn.mockResolvedValue([]);

    render(<ProctoringRevisor />);

    await waitFor(() => expect(screen.getByText('Ana Gómez')).toBeTruthy());
    const botonEliminar = screen.getByTitle('Eliminar sesión de diagnóstico');
    fireEvent.click(botonEliminar);

    fireEvent.click(await screen.findByRole('button', { name: /^eliminar$/i }));

    await waitFor(() => expect(eliminarSesionTestFn).toHaveBeenCalledWith('/api/v1', 'tok-test', 'sess-1'));
    await waitFor(() => expect(toastSuccess).toHaveBeenCalled());
  });
});

describe('ProctoringRevisor — filtros arman el query esperado', () => {
  it('Aplicar filtros combina alumno + examen + fechas + nivel de riesgo en la llamada', async () => {
    listarRegistroSesionesFn.mockResolvedValue({ items: [unaSesion()], total: 1, page: 1, page_size: 20 });
    listarExamenesConSesionesFn.mockResolvedValue([{ id: 'exam-1', titulo: 'Parcial 1' }]);

    render(<ProctoringRevisor />);
    await waitFor(() => expect(listarExamenesConSesionesFn).toHaveBeenCalled());
    await waitFor(() => expect(listarRegistroSesionesFn.mock.calls.length).toBeGreaterThan(0));

    fireEvent.change(screen.getByLabelText(/^alumno$/i), { target: { value: 'Gómez' } });
    fireEvent.change(screen.getByLabelText(/^examen$/i), { target: { value: 'exam-1' } });
    fireEvent.change(screen.getByLabelText(/^desde$/i), { target: { value: '2026-01-01' } });
    fireEvent.change(screen.getByLabelText(/^hasta$/i), { target: { value: '2026-01-31' } });
    fireEvent.change(screen.getByLabelText(/nivel de riesgo/i), { target: { value: 'alto' } });
    fireEvent.click(screen.getByRole('button', { name: /aplicar filtros/i }));

    await waitFor(() => {
      const ultima = listarRegistroSesionesFn.mock.calls.at(-1)?.[2];
      expect(ultima).toMatchObject({
        q: 'Gómez',
        exam_id: 'exam-1',
        fecha_desde: '2026-01-01T00:00:00',
        fecha_hasta: '2026-01-31T23:59:59',
        nivel_riesgo: 'alto',
        page: 1,
      });
    });
  });

  it('Limpiar vuelve a pedir sin filtros', async () => {
    listarRegistroSesionesFn.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
    listarExamenesConSesionesFn.mockResolvedValue([]);

    render(<ProctoringRevisor />);
    await waitFor(() => expect(listarRegistroSesionesFn).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText(/^alumno$/i), { target: { value: 'algo' } });
    fireEvent.click(screen.getByRole('button', { name: /aplicar filtros/i }));
    await waitFor(() =>
      expect(listarRegistroSesionesFn.mock.calls.at(-1)?.[2]).toMatchObject({ q: 'algo' }),
    );

    fireEvent.click(screen.getByRole('button', { name: /limpiar/i }));
    await waitFor(() => {
      const ultima = listarRegistroSesionesFn.mock.calls.at(-1)?.[2];
      expect(ultima?.q).toBeUndefined();
    });
  });
});

describe('ProctoringRevisor — paginación navega correctamente', () => {
  it('ir a la página siguiente re-pide con page=2', async () => {
    listarRegistroSesionesFn.mockResolvedValue({
      items: [unaSesion()],
      total: 45, // 3 páginas de a 20
      page: 1,
      page_size: 20,
    });
    listarExamenesConSesionesFn.mockResolvedValue([]);

    render(<ProctoringRevisor />);
    await waitFor(() => expect(listarRegistroSesionesFn).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: /página siguiente/i }));

    await waitFor(() => {
      const ultima = listarRegistroSesionesFn.mock.calls.at(-1)?.[2];
      expect(ultima).toMatchObject({ page: 2, page_size: 20 });
    });
  });
});

describe('ProctoringRevisor — catálogo de exámenes SIN hardcodeo (C-76 §17.6)', () => {
  it('el <select> de Examen sale SOLO del catálogo devuelto por el backend', async () => {
    listarRegistroSesionesFn.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
    listarExamenesConSesionesFn.mockResolvedValue([
      { id: 'exam-a', titulo: 'Parcial de Cálculo' },
      { id: 'exam-b', titulo: 'Final de Física' },
    ]);

    render(<ProctoringRevisor />);

    const select = await screen.findByLabelText(/^examen$/i) as HTMLSelectElement;
    await waitFor(() => {
      const opciones = within(select).getAllByRole('option').map((o) => o.textContent);
      expect(opciones).toEqual(['Todos los exámenes', 'Parcial de Cálculo', 'Final de Física']);
    });
  });

  it('el componente fuente NO contiene un array de exámenes/estados escrito a mano', () => {
    const fuente = readFileSync(join(here, 'ProctoringRevisor.tsx'), 'utf-8');
    // Únicas listas hardcodeadas permitidas: el vocabulario FIJO de nivel de
    // riesgo (bajo/medio/alto — 3 valores de dominio, no datos de negocio). Nada
    // de exámenes ni de estados de sesión debe aparecer como literal en el archivo.
    expect(fuente).not.toMatch(/examenesMock|EXAMENES_MOCK|examenesHardcodeados/i);
    expect(fuente).not.toMatch(/'Parcial 1'|"Parcial 1"/);
  });
});
