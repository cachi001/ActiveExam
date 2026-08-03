/**
 * TDD: RED → GREEN → TRIANGULATE
 * Tests para examContentResultados.ts (C-69 admin sync).
 *
 * Cubre:
 *  - listarResultadosFn: URL, params, auth header, paginación, error HTTP
 *  - sincronizarMoodleFn: método POST, URL, auth header, shape de respuesta
 *  - getExamenHeaderFn: URL, normalización de campos
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import type { ResultadoExamen, SincronizarMoodleResponse } from './examContentResultados';
import { contarRetencionesPorRevision } from './examContentResultados';

// ---------------------------------------------------------------------------
// 1. RED — tipos de dominio
// ---------------------------------------------------------------------------

describe('1.1 ResultadoExamen — tipo de dominio', () => {
  it('tiene los campos mínimos requeridos', () => {
    const r: ResultadoExamen = {
      session_id: 'sess-1',
      alumno_idnumber: 'FRM-23-0001',
      alumno_email: 'test@example.com',
      alumno_nombre: null,
      nota: 8.5,
      estado_moodle: 'pendiente',
      actualizado_en: '2026-06-01T10:00:00',
    };
    expect(r.estado_moodle).toBe('pendiente');
    expect(r.alumno_nombre).toBeNull();
  });

  it('estado_moodle acepta los cuatro valores válidos', () => {
    const estados: ResultadoExamen['estado_moodle'][] = ['pendiente', 'enviado', 'fallido', 'sin_token'];
    expect(estados).toHaveLength(4);
  });

  it('SincronizarMoodleResponse tiene los campos esperados', () => {
    const r: SincronizarMoodleResponse = { enviadas: 5, fallidas: 0, sin_token: 1, total: 6 };
    expect(r.enviadas).toBe(5);
    expect(r.mensaje).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// 2. RED → GREEN: listarResultadosFn
// ---------------------------------------------------------------------------

describe('2.1 listarResultadosFn — llamada básica', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => { fetchSpy = vi.spyOn(globalThis, 'fetch'); });
  afterEach(() => { fetchSpy.mockRestore(); });

  it('llama al endpoint correcto con auth header', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [], total: 0, page: 1, page_size: 25 }),
    } as Response);

    const { listarResultadosFn } = await import('./examContentResultados');
    await listarResultadosFn('/api/v1', 'tok-abc', 'exam-uuid-1');

    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/exam-content/exam-uuid-1/resultados',
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({ Authorization: 'Bearer tok-abc' }),
      }),
    );
  });

  it('incluye q y estado en la querystring cuando se proveen', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [], total: 0, page: 1, page_size: 25 }),
    } as Response);

    const { listarResultadosFn } = await import('./examContentResultados');
    await listarResultadosFn('/api/v1', 'tok', 'ex-1', { q: 'garcia', estado: 'pendiente' });

    const url = fetchSpy.mock.calls[0][0] as string;
    expect(url).toContain('q=garcia');
    expect(url).toContain('estado=pendiente');
  });

  it('incluye page y page_size en la querystring', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [], total: 10, page: 2, page_size: 5 }),
    } as Response);

    const { listarResultadosFn } = await import('./examContentResultados');
    await listarResultadosFn('/api/v1', 'tok', 'ex-2', { page: 2, page_size: 5 });

    const url = fetchSpy.mock.calls[0][0] as string;
    expect(url).toContain('page=2');
    expect(url).toContain('page_size=5');
  });

  it('retorna la respuesta paginada correctamente', async () => {
    const mockItems: ResultadoExamen[] = [
      { session_id: 's1', alumno_idnumber: 'FRM-1', alumno_email: 'a@b.com', alumno_nombre: 'Ana García', nota: 7, estado_moodle: 'enviado', actualizado_en: '2026-01-01T00:00:00' },
    ];
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: mockItems, total: 1, page: 1, page_size: 25 }),
    } as Response);

    const { listarResultadosFn } = await import('./examContentResultados');
    const result = await listarResultadosFn('/api/v1', 'tok', 'ex-1');

    expect(result.items).toHaveLength(1);
    expect(result.items[0].alumno_nombre).toBe('Ana García');
    expect(result.total).toBe(1);
  });

  it('lanza en HTTP 403', async () => {
    fetchSpy.mockResolvedValueOnce({ ok: false, status: 403, json: async () => ({}) } as Response);

    const { listarResultadosFn } = await import('./examContentResultados');
    await expect(listarResultadosFn('/api/v1', 'tok', 'ex-1')).rejects.toThrow('HTTP 403');
  });

  it('no agrega Authorization cuando no hay token', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [], total: 0, page: 1, page_size: 25 }),
    } as Response);

    const { listarResultadosFn } = await import('./examContentResultados');
    await listarResultadosFn('/api/v1', undefined, 'ex-1');

    const init = fetchSpy.mock.calls[0][1] as RequestInit;
    const headers = init?.headers as Record<string, string>;
    expect(headers?.['Authorization']).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// 3. RED → GREEN: sincronizarMoodleFn
// ---------------------------------------------------------------------------

describe('3.1 sincronizarMoodleFn — POST correcto', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => { fetchSpy = vi.spyOn(globalThis, 'fetch'); });
  afterEach(() => { fetchSpy.mockRestore(); });

  it('llama con método POST a la URL correcta', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ enviadas: 3, fallidas: 0, sin_token: 0, total: 3 }),
    } as Response);

    const { sincronizarMoodleFn } = await import('./examContentResultados');
    await sincronizarMoodleFn('/api/v1', 'tok', 'exam-xyz');

    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/exam-content/exam-xyz/sincronizar-moodle',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('retorna el shape de respuesta correctamente', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ enviadas: 2, fallidas: 1, sin_token: 0, total: 3, mensaje: 'Parcial OK' }),
    } as Response);

    const { sincronizarMoodleFn } = await import('./examContentResultados');
    const result = await sincronizarMoodleFn('/api/v1', 'tok', 'exam-1');

    expect(result.enviadas).toBe(2);
    expect(result.fallidas).toBe(1);
    expect(result.mensaje).toBe('Parcial OK');
  });

  it('cuando sin_token, retorna el campo y el mensaje de configuración', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ enviadas: 0, fallidas: 0, sin_token: 5, total: 5, mensaje: 'Token Moodle no configurado' }),
    } as Response);

    const { sincronizarMoodleFn } = await import('./examContentResultados');
    const result = await sincronizarMoodleFn('/api/v1', 'tok', 'exam-2');

    expect(result.sin_token).toBe(5);
    expect(result.enviadas).toBe(0);
    expect(result.mensaje).toContain('Token');
  });

  it('lanza en HTTP 500', async () => {
    fetchSpy.mockResolvedValueOnce({ ok: false, status: 500, json: async () => ({}) } as Response);

    const { sincronizarMoodleFn } = await import('./examContentResultados');
    await expect(sincronizarMoodleFn('/api/v1', 'tok', 'ex-1')).rejects.toThrow('HTTP 500');
  });
});

// ---------------------------------------------------------------------------
// 4. TRIANGULATE: getExamenHeaderFn
// ---------------------------------------------------------------------------

describe('4.1 getExamenHeaderFn — normalización de campos', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => { fetchSpy = vi.spyOn(globalThis, 'fetch'); });
  afterEach(() => { fetchSpy.mockRestore(); });

  it('llama a GET /exam-content/{id}/resumen', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 'abc', titulo: 'Álgebra', cantidad_preguntas: 10 }),
    } as Response);

    const { getExamenHeaderFn } = await import('./examContentResultados');
    await getExamenHeaderFn('/api/v1', 'tok', 'abc');

    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/exam-content/abc/resumen',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('normaliza el campo titulo y cantidad_preguntas', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 'e1', titulo: 'Cálculo', cantidad_preguntas: 20, comision_nombre: 'C1A', materia_nombre: 'Matemática' }),
    } as Response);

    const { getExamenHeaderFn } = await import('./examContentResultados');
    const result = await getExamenHeaderFn('/api/v1', 'tok', 'e1');

    expect(result.titulo).toBe('Cálculo');
    expect(result.cantidad_preguntas).toBe(20);
    expect(result.comision_nombre).toBe('C1A');
    expect(result.materia_nombre).toBe('Matemática');
  });

  it('lanza en HTTP 404', async () => {
    fetchSpy.mockResolvedValueOnce({ ok: false, status: 404, json: async () => ({}) } as Response);

    const { getExamenHeaderFn } = await import('./examContentResultados');
    await expect(getExamenHeaderFn('/api/v1', 'tok', 'no-existe')).rejects.toThrow('HTTP 404');
  });
});

// ---------------------------------------------------------------------------
// 5. RED → GREEN → TRIANGULATE: contarRetencionesPorRevision
//
// Bug real: el banner "N notas retenidas por revisión" de ExamResultados.tsx
// contaba TODAS las filas con retenido_por (cualquier motivo) bajo el mismo
// mensaje "superaron el umbral de riesgo o están en revisión". Pero
// 'sin_destino' y 'sin_credencial_docente' son retenciones de CONFIGURACIÓN,
// nada que ver con el score de proctoring ni con una revisión pendiente — un
// alumno bajo el umbral (aprobado o desaprobado) terminaba mostrado como si
// su nota estuviera pendiente de revisión humana por riesgo, sin haberlo
// superado nunca.
// ---------------------------------------------------------------------------

function _r(retenido_por: string | null): ResultadoExamen {
  return {
    session_id: 's-' + Math.random(),
    alumno_idnumber: 'FRM-1',
    alumno_email: 'a@b.com',
    alumno_nombre: null,
    nota: 7,
    estado_moodle: 'pendiente',
    actualizado_en: '2026-01-01T00:00:00',
    retenido_por,
  };
}

describe('5.1 contarRetencionesPorRevision — separa revisión de configuración', () => {
  it('cuenta en_riesgo y anulada como retención por revisión', () => {
    const resultados = [_r('en_riesgo'), _r('anulada'), _r(null)];
    const c = contarRetencionesPorRevision(resultados);
    expect(c.revision).toBe(2);
    expect(c.configuracion).toBe(0);
  });

  it('cuenta sin_destino y sin_credencial_docente como retención de configuración, NO de revisión', () => {
    const resultados = [_r('sin_destino'), _r('sin_credencial_docente')];
    const c = contarRetencionesPorRevision(resultados);
    expect(c.revision).toBe(0);
    expect(c.configuracion).toBe(2);
  });

  it('caso mixto: un alumno bajo el umbral retenido solo por sin_destino no cuenta como revisión', () => {
    // Escenario real del bug: EST-001 aprobó sin superar el umbral pero el
    // examen no tenía destino Moodle configurado -> quedaba en el contador de
    // "retenidas por revisión" del banner, mensaje falso para ese alumno.
    const resultados = [_r('en_riesgo'), _r('sin_destino'), _r('sin_destino'), _r(null)];
    const c = contarRetencionesPorRevision(resultados);
    expect(c.revision).toBe(1);
    expect(c.configuracion).toBe(2);
  });

  it('anulada cuenta como revisión (es un veredicto humano, no config faltante)', () => {
    const resultados = [_r('anulada')];
    const c = contarRetencionesPorRevision(resultados);
    expect(c.revision).toBe(1);
    expect(c.configuracion).toBe(0);
  });

  it('sin resultados retenidos, ambos contadores en 0', () => {
    const c = contarRetencionesPorRevision([_r(null), _r(null)]);
    expect(c.revision).toBe(0);
    expect(c.configuracion).toBe(0);
  });
});
