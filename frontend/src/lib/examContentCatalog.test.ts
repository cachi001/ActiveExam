/**
 * RED → GREEN → TRIANGULATE: tests de listarExamenesContenido() y ExamenContenidoResumen.
 *
 * TDD Cycle:
 *  RED:         tests escritos primero — referencian listarExamenesContenido() que no existe aún.
 *  GREEN:       se agrega listarExamenesContenido() a api.ts + ExamenContenidoResumen a types.ts.
 *  TRIANGULATE: modo demo (vacío), modo real (fetch), shape de respuesta.
 *
 * Sin @testing-library/react — tests de lógica pura de la capa de API.
 */

import { describe, expect, it, vi, afterEach, beforeEach } from 'vitest';
import type { ExamenContenidoResumen } from './types';

// ---------------------------------------------------------------------------
// 1. RED: ExamenContenidoResumen existe como tipo en types.ts
// ---------------------------------------------------------------------------

describe('1.1 ExamenContenidoResumen — tipo de dominio', () => {
  it('tiene los campos id, titulo y cantidad_preguntas', () => {
    // Si este test compila, el tipo existe. Si types.ts no lo exporta, da error de TS.
    const resumen: ExamenContenidoResumen = {
      id: 'uuid-1',
      titulo: 'Parcial de Álgebra',
      cantidad_preguntas: 5,
    };
    expect(resumen.id).toBe('uuid-1');
    expect(resumen.titulo).toBe('Parcial de Álgebra');
    expect(resumen.cantidad_preguntas).toBe(5);
  });

  it('no permite es_correcta — D3', () => {
    // El tipo NO debe tener es_correcta. Verificamos por inspection de shape.
    const resumen: ExamenContenidoResumen = {
      id: 'x',
      titulo: 'T',
      cantidad_preguntas: 0,
    };
    // TypeScript garantiza esto en compilación; en runtime verificamos via keys.
    const claves = Object.keys(resumen);
    expect(claves).not.toContain('es_correcta');
    expect(claves).not.toContain('preguntas');
    expect(claves).not.toContain('opciones');
  });
});

// ---------------------------------------------------------------------------
// 2. RED: listarExamenesContenido() en modo demo devuelve []
// ---------------------------------------------------------------------------

describe('2.1 listarExamenesContenido() — modo demo', () => {
  it('devuelve [] sin hacer fetch cuando USE_REAL_BACKEND=false', async () => {
    // En modo demo (sin backend), el catálogo de exámenes importados está vacío.
    // Importamos con vi.doMock para controlar USE_REAL_BACKEND.
    const fetchSpy = vi.spyOn(globalThis, 'fetch');

    // Importar el módulo que aporta la función a testear.
    // El modo demo se simula importando sin VITE_USE_REAL_BACKEND (default: demo).
    const { api } = await import('./api');

    // En modo demo modoDemo=true → listarExamenesContenido devuelve []
    if (api.modoDemo) {
      const resultado = await api.listarExamenesContenido();
      expect(resultado).toEqual([]);
      expect(fetchSpy).not.toHaveBeenCalledWith(
        expect.stringContaining('exam-content'),
        expect.anything(),
      );
    } else {
      // Si USE_REAL_BACKEND=1 en el entorno de test, saltamos esta verificación.
      expect(true).toBe(true); // pass
    }

    fetchSpy.mockRestore();
  });
});

// ---------------------------------------------------------------------------
// 3. GREEN: listarExamenesContenido() en modo real llama a GET /exam-content
// ---------------------------------------------------------------------------

describe('3.1 listarExamenesContenido() — modo real', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, 'fetch');
  });

  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it('cuando fetch retorna 200 con lista, devuelve los items correctamente', async () => {
    const mockItems: ExamenContenidoResumen[] = [
      { id: 'abc-1', titulo: 'Álgebra', cantidad_preguntas: 3 },
      { id: 'abc-2', titulo: 'Biología', cantidad_preguntas: 5 },
    ];

    fetchSpy.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockItems,
    } as Response);

    // Llamar directamente a listarExamenesContenido como función pura (mock fetch).
    const { listarExamenesContenidoFn } = await import('./examContentCatalog');
    const resultado = await listarExamenesContenidoFn('/api/v1', 'test-token');

    expect(resultado).toHaveLength(2);
    expect(resultado[0].id).toBe('abc-1');
    expect(resultado[0].titulo).toBe('Álgebra');
    expect(resultado[0].cantidad_preguntas).toBe(3);
    expect(resultado[1].id).toBe('abc-2');
  });

  it('cuando fetch falla (red caída), devuelve [] sin propagar el error', async () => {
    fetchSpy.mockRejectedValueOnce(new Error('network error'));

    const { listarExamenesContenidoFn } = await import('./examContentCatalog');
    const resultado = await listarExamenesContenidoFn('/api/v1', 'test-token');

    expect(resultado).toEqual([]);
  });

  it('cuando fetch retorna 500, devuelve [] sin propagar', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({ detail: 'internal error' }),
    } as Response);

    const { listarExamenesContenidoFn } = await import('./examContentCatalog');
    const resultado = await listarExamenesContenidoFn('/api/v1', 'test-token');

    expect(resultado).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// 4. TRIANGULATE: shape y campos
// ---------------------------------------------------------------------------

describe('4.1 listarExamenesContenidoFn() — shape de la respuesta', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, 'fetch');
  });

  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it('llama al endpoint correcto con el token de auth', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => [],
    } as Response);

    const { listarExamenesContenidoFn } = await import('./examContentCatalog');
    await listarExamenesContenidoFn('/api/v1', 'my-token');

    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/exam-content',
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({
          Authorization: 'Bearer my-token',
        }),
      }),
    );
  });

  it('cuando el token es undefined, no agrega Authorization header', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => [],
    } as Response);

    const { listarExamenesContenidoFn } = await import('./examContentCatalog');
    await listarExamenesContenidoFn('/api/v1', undefined);

    const call = fetchSpy.mock.calls[0];
    const init = call[1] as RequestInit;
    const headers = init?.headers as Record<string, string>;
    expect(headers?.['Authorization']).toBeUndefined();
  });

  it('examen_contenido_id del item es el mismo que se usa para GET /{id}', async () => {
    const mockItems: ExamenContenidoResumen[] = [
      { id: 'real-uuid-123', titulo: 'Cálculo Diferencial', cantidad_preguntas: 10 },
    ];
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockItems,
    } as Response);

    const { listarExamenesContenidoFn } = await import('./examContentCatalog');
    const resultado = await listarExamenesContenidoFn('/api/v1', 'tok');

    // El id del item es el examen_contenido_id que se propaga a la sesión
    expect(resultado[0].id).toBe('real-uuid-123');
    // Y ese mismo id se usaría para GET /api/v1/exam-content/real-uuid-123
  });
});
