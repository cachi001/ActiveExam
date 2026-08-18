/**
 * TDD: RED → GREEN → TRIANGULATE
 * Tests para proctoringRegistro.ts (C-76 tarea 17: Registro de sesiones).
 *
 * Cubre:
 *  - listarRegistroSesionesFn: URL, params (q/exam_id/fechas/nivel_riesgo/paginación), auth header, error HTTP
 *  - listarExamenesConSesionesFn: URL, auth header, shape de respuesta
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

describe('listarRegistroSesionesFn — llamada básica', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => { fetchSpy = vi.spyOn(globalThis, 'fetch'); });
  afterEach(() => { fetchSpy.mockRestore(); });

  it('llama al endpoint correcto con auth header', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [], total: 0, page: 1, page_size: 20 }),
    } as Response);

    const { listarRegistroSesionesFn } = await import('./proctoringRegistro');
    await listarRegistroSesionesFn('/api/v1', 'tok-abc');

    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/proctoring/sessions/registro',
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({ Authorization: 'Bearer tok-abc' }),
      }),
    );
  });

  it('arma la querystring con TODOS los filtros cuando se proveen (sin hardcodeo)', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [], total: 0, page: 2, page_size: 10 }),
    } as Response);

    const { listarRegistroSesionesFn } = await import('./proctoringRegistro');
    await listarRegistroSesionesFn('/api/v1', 'tok-abc', {
      q: 'ana gomez',
      exam_id: 'exam-1',
      fecha_desde: '2026-01-01T00:00:00',
      fecha_hasta: '2026-01-31T23:59:59',
      nivel_riesgo: 'alto',
      page: 2,
      page_size: 10,
    });

    const calledUrl = (fetchSpy.mock.calls[0] as [string, unknown])[0] as string;
    const url = new URL(calledUrl, 'http://x');
    expect(url.pathname).toBe('/api/v1/proctoring/sessions/registro');
    expect(url.searchParams.get('q')).toBe('ana gomez');
    expect(url.searchParams.get('exam_id')).toBe('exam-1');
    expect(url.searchParams.get('fecha_desde')).toBe('2026-01-01T00:00:00');
    expect(url.searchParams.get('fecha_hasta')).toBe('2026-01-31T23:59:59');
    expect(url.searchParams.get('nivel_riesgo')).toBe('alto');
    expect(url.searchParams.get('page')).toBe('2');
    expect(url.searchParams.get('page_size')).toBe('10');
  });

  it('sin filtros no agrega querystring (page/page_size por defecto de la llamada)', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [], total: 0, page: 1, page_size: 20 }),
    } as Response);

    const { listarRegistroSesionesFn } = await import('./proctoringRegistro');
    await listarRegistroSesionesFn('/api/v1', undefined);

    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/proctoring/sessions/registro',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('devuelve el envelope paginado tal cual lo manda el backend', async () => {
    const payload = {
      items: [{ id: 's1', modo: 'examen', creada_en: '2026-01-01T00:00:00Z', total_eventos: 1, total_discrepancias: 0, score: 10 }],
      total: 1,
      page: 1,
      page_size: 20,
    };
    fetchSpy.mockResolvedValueOnce({ ok: true, json: async () => payload } as Response);

    const { listarRegistroSesionesFn } = await import('./proctoringRegistro');
    const resp = await listarRegistroSesionesFn('/api/v1', 'tok');
    expect(resp).toEqual(payload);
  });

  it('lanza en error HTTP con el status adjunto', async () => {
    fetchSpy.mockResolvedValueOnce({ ok: false, status: 403 } as Response);

    const { listarRegistroSesionesFn } = await import('./proctoringRegistro');
    await expect(listarRegistroSesionesFn('/api/v1', 'tok')).rejects.toMatchObject({ status: 403 });
  });
});

describe('listarExamenesConSesionesFn — catálogo de filtro', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => { fetchSpy = vi.spyOn(globalThis, 'fetch'); });
  afterEach(() => { fetchSpy.mockRestore(); });

  it('llama al endpoint del catálogo con auth header', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => [{ id: 'exam-1', titulo: 'Parcial 1' }],
    } as Response);

    const { listarExamenesConSesionesFn } = await import('./proctoringRegistro');
    const resp = await listarExamenesConSesionesFn('/api/v1', 'tok-abc');

    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/proctoring/sessions/registro/examenes',
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({ Authorization: 'Bearer tok-abc' }),
      }),
    );
    expect(resp).toEqual([{ id: 'exam-1', titulo: 'Parcial 1' }]);
  });

  it('lanza en error HTTP', async () => {
    fetchSpy.mockResolvedValueOnce({ ok: false, status: 500 } as Response);

    const { listarExamenesConSesionesFn } = await import('./proctoringRegistro');
    await expect(listarExamenesConSesionesFn('/api/v1', 'tok')).rejects.toMatchObject({ status: 500 });
  });
});

describe('listarRegistroSesionesFn — filtros materia_id/comision_id (C-76 tarea 20.3)', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => { fetchSpy = vi.spyOn(globalThis, 'fetch'); });
  afterEach(() => { fetchSpy.mockRestore(); });

  it('agrega materia_id y comision_id a la querystring cuando se proveen', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [], total: 0, page: 1, page_size: 20 }),
    } as Response);

    const { listarRegistroSesionesFn } = await import('./proctoringRegistro');
    await listarRegistroSesionesFn('/api/v1', 'tok-abc', {
      materia_id: 'mat-1',
      comision_id: 'com-1',
    });

    const calledUrl = (fetchSpy.mock.calls[0] as [string, unknown])[0] as string;
    const url = new URL(calledUrl, 'http://x');
    expect(url.searchParams.get('materia_id')).toBe('mat-1');
    expect(url.searchParams.get('comision_id')).toBe('com-1');
  });
});

describe('eliminarSesionTestFn — DELETE acotado a modo=test (C-76 tarea 20.1)', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => { fetchSpy = vi.spyOn(globalThis, 'fetch'); });
  afterEach(() => { fetchSpy.mockRestore(); });

  it('llama DELETE al endpoint correcto con auth header', async () => {
    fetchSpy.mockResolvedValueOnce({ ok: true, status: 204 } as Response);

    const { eliminarSesionTestFn } = await import('./proctoringRegistro');
    await eliminarSesionTestFn('/api/v1', 'tok-abc', 'sess-1');

    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/proctoring/sessions/sess-1',
      expect.objectContaining({
        method: 'DELETE',
        headers: expect.objectContaining({ Authorization: 'Bearer tok-abc' }),
      }),
    );
  });

  it('lanza en error HTTP (ej. 409 sesion modo=examen) con el status adjunto', async () => {
    fetchSpy.mockResolvedValueOnce({ ok: false, status: 409 } as Response);

    const { eliminarSesionTestFn } = await import('./proctoringRegistro');
    await expect(eliminarSesionTestFn('/api/v1', 'tok', 'sess-1')).rejects.toMatchObject({ status: 409 });
  });
});
