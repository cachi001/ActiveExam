/**
 * RED → GREEN → TRIANGULATE: navegación real materia → comisión → examen (C-69).
 *
 * Funciones puras que pegan al backend real (GET /exam-content/materias, etc.).
 * Inyectan apiBase + token para testear de forma aislada con fetch mockeado.
 * Sin @testing-library: tests de la capa de API, no de render.
 */

import { describe, expect, it, vi, afterEach, beforeEach } from 'vitest';
import type { Materia, Comision, ExamenContenidoResumen } from './types';

describe('examContentBrowse — listarMateriasFn', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;
  beforeEach(() => { fetchSpy = vi.spyOn(globalThis, 'fetch'); });
  afterEach(() => { fetchSpy.mockRestore(); });

  it('GET /exam-content/materias con token y devuelve la lista', async () => {
    const mock: Materia[] = [{ id: 'm1', codigo: 'AM-1', nombre: 'Análisis' }];
    fetchSpy.mockResolvedValueOnce({ ok: true, status: 200, json: async () => mock } as Response);

    const { listarMateriasFn } = await import('./examContentBrowse');
    const res = await listarMateriasFn('/api/v1', 'tok');

    expect(res).toHaveLength(1);
    expect(res[0].codigo).toBe('AM-1');
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/exam-content/materias',
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({ Authorization: 'Bearer tok' }),
      }),
    );
  });

  it('ante error de red devuelve [] sin propagar', async () => {
    fetchSpy.mockRejectedValueOnce(new Error('down'));
    const { listarMateriasFn } = await import('./examContentBrowse');
    expect(await listarMateriasFn('/api/v1', 'tok')).toEqual([]);
  });

  it('ante 500 devuelve []', async () => {
    fetchSpy.mockResolvedValueOnce({ ok: false, status: 500, json: async () => ({}) } as Response);
    const { listarMateriasFn } = await import('./examContentBrowse');
    expect(await listarMateriasFn('/api/v1', 'tok')).toEqual([]);
  });
});

describe('examContentBrowse — inscribirmePorCodigoFn (C-70)', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;
  beforeEach(() => { fetchSpy = vi.spyOn(globalThis, 'fetch'); });
  afterEach(() => { fetchSpy.mockRestore(); });

  it('POST /exam-content/inscribirme con el código en el body y token', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        comision_id: 'c1', comision_nombre: 'Comisión 1', materia_nombre: 'Prog 1', ya_inscripto: false,
      }),
    } as Response);

    const { inscribirmePorCodigoFn } = await import('./examContentBrowse');
    const res = await inscribirmePorCodigoFn('/api/v1', 'tok', 'PROG1-7K2Q');

    expect(res.ya_inscripto).toBe(false);
    expect(res.comision_nombre).toBe('Comisión 1');
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/exam-content/inscribirme',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ codigo_matriculacion: 'PROG1-7K2Q' }),
        headers: expect.objectContaining({ Authorization: 'Bearer tok' }),
      }),
    );
  });

  it('idempotente: ya_inscripto=true cuando ya estaba matriculado', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        comision_id: 'c1', comision_nombre: 'Comisión 1', materia_nombre: 'Prog 1', ya_inscripto: true,
      }),
    } as Response);
    const { inscribirmePorCodigoFn } = await import('./examContentBrowse');
    const res = await inscribirmePorCodigoFn('/api/v1', 'tok', 'PROG1-7K2Q');
    expect(res.ya_inscripto).toBe(true);
  });

  it('código inválido (404) lanza Error con .status = 404', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: false, status: 404, json: async () => ({ detail: { error: 'codigo_invalido' } }),
    } as Response);
    const { inscribirmePorCodigoFn } = await import('./examContentBrowse');
    await expect(inscribirmePorCodigoFn('/api/v1', 'tok', 'NO-EXISTE')).rejects.toMatchObject({
      status: 404,
    });
  });
});

describe('examContentBrowse — listarComisionesFn', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;
  beforeEach(() => { fetchSpy = vi.spyOn(globalThis, 'fetch'); });
  afterEach(() => { fetchSpy.mockRestore(); });

  it('GET /exam-content/materias/{id}/comisiones', async () => {
    const mock: Comision[] = [
      { id: 'c1', materia_id: 'm1', codigo: '1A', nombre: 'Comisión 1A', periodo: '1C', anio: 2026 },
    ];
    fetchSpy.mockResolvedValueOnce({ ok: true, status: 200, json: async () => mock } as Response);

    const { listarComisionesFn } = await import('./examContentBrowse');
    const res = await listarComisionesFn('/api/v1', 'tok', 'm1');

    expect(res[0].materia_id).toBe('m1');
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/exam-content/materias/m1/comisiones',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('error → []', async () => {
    fetchSpy.mockRejectedValueOnce(new Error('x'));
    const { listarComisionesFn } = await import('./examContentBrowse');
    expect(await listarComisionesFn('/api/v1', 'tok', 'm1')).toEqual([]);
  });
});

describe('examContentBrowse — listarExamenesDeComisionFn', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;
  beforeEach(() => { fetchSpy = vi.spyOn(globalThis, 'fetch'); });
  afterEach(() => { fetchSpy.mockRestore(); });

  it('GET /exam-content/comisiones/{id}/examenes y devuelve resúmenes sin es_correcta', async () => {
    const mock: ExamenContenidoResumen[] = [
      { id: 'e1', titulo: 'Parcial', cantidad_preguntas: 3, comision_id: 'c1', comision_nombre: 'Comisión 1A', materia_nombre: 'Análisis' },
    ];
    fetchSpy.mockResolvedValueOnce({ ok: true, status: 200, json: async () => mock } as Response);

    const { listarExamenesDeComisionFn } = await import('./examContentBrowse');
    const res = await listarExamenesDeComisionFn('/api/v1', 'tok', 'c1');

    expect(res[0].id).toBe('e1');
    expect(res[0].cantidad_preguntas).toBe(3);
    expect(Object.keys(res[0])).not.toContain('es_correcta');
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/exam-content/comisiones/c1/examenes',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('error → []', async () => {
    fetchSpy.mockResolvedValueOnce({ ok: false, status: 404, json: async () => ({}) } as Response);
    const { listarExamenesDeComisionFn } = await import('./examContentBrowse');
    expect(await listarExamenesDeComisionFn('/api/v1', 'tok', 'c1')).toEqual([]);
  });
});

describe('examContentBrowse — sin token no agrega Authorization', () => {
  it('omite el header Authorization cuando token es undefined', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    fetchSpy.mockResolvedValueOnce({ ok: true, status: 200, json: async () => [] } as Response);

    const { listarMateriasFn } = await import('./examContentBrowse');
    await listarMateriasFn('/api/v1', undefined);

    const init = fetchSpy.mock.calls[0][1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers['Authorization']).toBeUndefined();
    fetchSpy.mockRestore();
  });
});
