/**
 * TDD: RED → GREEN → TRIANGULATE
 * Tests de la capa de API para el destino de la nota en Moodle (D12).
 *
 * Cubre setMoodleTarget / getMoodleTarget: URL, método, auth header, body y
 * manejo de error HTTP. Sin @testing-library (no instalado): tests de fetch.
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

vi.mock('./authProvider', () => ({
  authProvider: { getToken: () => 'tok' },
}));

describe('examContentAdmin — setMoodleTarget', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, 'fetch');
  });
  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it('POST al endpoint con token y body, devuelve el destino', async () => {
    const mock = { examen_id: 'ex-1', moodle_courseid: 12, moodle_cmid: 34 };
    fetchSpy.mockResolvedValueOnce({ ok: true, status: 200, json: async () => mock } as Response);

    const { setMoodleTarget } = await import('./examContentAdmin');
    const res = await setMoodleTarget('ex-1', { moodle_courseid: 12, moodle_cmid: 34 });

    expect(res.moodle_courseid).toBe(12);
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/exam-content/ex-1/moodle-target',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer tok' }),
        body: JSON.stringify({ moodle_courseid: 12, moodle_cmid: 34 }),
      }),
    );
  });

  it('acepta nulls para limpiar el destino', async () => {
    const mock = { examen_id: 'ex-2', moodle_courseid: null, moodle_cmid: null };
    fetchSpy.mockResolvedValueOnce({ ok: true, status: 200, json: async () => mock } as Response);

    const { setMoodleTarget } = await import('./examContentAdmin');
    const res = await setMoodleTarget('ex-2', { moodle_courseid: null, moodle_cmid: null });

    expect(res.moodle_courseid).toBeNull();
    expect(res.moodle_cmid).toBeNull();
  });

  it('ante error HTTP propaga el detalle', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'No autorizado' }),
    } as Response);

    const { setMoodleTarget } = await import('./examContentAdmin');
    await expect(
      setMoodleTarget('ex-3', { moodle_courseid: 1, moodle_cmid: 2 }),
    ).rejects.toThrow('No autorizado');
  });
});

// ---------------------------------------------------------------------------
// Helpers de destino Moodle: parseMoodleId / buildMoodleTarget (puros)
// ---------------------------------------------------------------------------

describe('examContentAdmin — parseMoodleId', () => {
  it('convierte texto numérico a número', async () => {
    const { parseMoodleId } = await import('./examContentAdmin');
    expect(parseMoodleId('42')).toBe(42);
    expect(parseMoodleId('  128  ')).toBe(128);
  });

  it('vacío o solo espacios → null (limpia el destino)', async () => {
    const { parseMoodleId } = await import('./examContentAdmin');
    expect(parseMoodleId('')).toBeNull();
    expect(parseMoodleId('   ')).toBeNull();
  });

  it('texto no numérico → null', async () => {
    const { parseMoodleId } = await import('./examContentAdmin');
    expect(parseMoodleId('abc')).toBeNull();
  });
});

describe('examContentAdmin — buildMoodleTarget', () => {
  it('arma el target con ambos ids', async () => {
    const { buildMoodleTarget } = await import('./examContentAdmin');
    expect(buildMoodleTarget('42', '128')).toEqual({ moodle_courseid: 42, moodle_cmid: 128 });
  });

  it('ambos vacíos → null/null (fallback global)', async () => {
    const { buildMoodleTarget } = await import('./examContentAdmin');
    expect(buildMoodleTarget('', '')).toEqual({ moodle_courseid: null, moodle_cmid: null });
  });

  it('uno solo cargado deja el otro en null', async () => {
    const { buildMoodleTarget } = await import('./examContentAdmin');
    expect(buildMoodleTarget('7', '')).toEqual({ moodle_courseid: 7, moodle_cmid: null });
  });
});

// ---------------------------------------------------------------------------
// asociarExamenAComision — RED → GREEN → TRIANGULATE
// ---------------------------------------------------------------------------

describe('examContentAdmin — asociarExamenAComision', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, 'fetch');
  });
  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it('POST al endpoint con token y body; devuelve la asociación', async () => {
    const mock = { examen_id: 'ex-1', comision_id: 'com-9' };
    fetchSpy.mockResolvedValueOnce({ ok: true, status: 200, json: async () => mock } as Response);

    const { asociarExamenAComision } = await import('./examContentAdmin');
    const res = await asociarExamenAComision('ex-1', 'com-9');

    expect(res.examen_id).toBe('ex-1');
    expect(res.comision_id).toBe('com-9');
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/exam-content/ex-1/comision',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer tok' }),
        body: JSON.stringify({ comision_id: 'com-9' }),
      }),
    );
  });

  it('ante error HTTP propaga el detalle', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Comisión no encontrada' }),
    } as Response);

    const { asociarExamenAComision } = await import('./examContentAdmin');
    await expect(asociarExamenAComision('ex-2', 'no-existe')).rejects.toThrow('Comisión no encontrada');
  });
});

describe('examContentAdmin — getMoodleTarget', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, 'fetch');
  });
  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it('GET al endpoint con token y devuelve el destino', async () => {
    const mock = { examen_id: 'ex-9', moodle_courseid: 7, moodle_cmid: null };
    fetchSpy.mockResolvedValueOnce({ ok: true, status: 200, json: async () => mock } as Response);

    const { getMoodleTarget } = await import('./examContentAdmin');
    const res = await getMoodleTarget('ex-9');

    expect(res.moodle_courseid).toBe(7);
    expect(res.moodle_cmid).toBeNull();
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/exam-content/ex-9/moodle-target',
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({ Authorization: 'Bearer tok' }),
      }),
    );
  });
});

// ---------------------------------------------------------------------------
// crearMateria — RED → GREEN → TRIANGULATE
// ---------------------------------------------------------------------------

describe('examContentAdmin — crearMateria', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, 'fetch');
  });
  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it('POST al endpoint correcto con token y body; devuelve MateriaResponse en 201', async () => {
    const mock = { id: 'mat-1', codigo: 'CB101', nombre: 'Análisis Matemático I' };
    fetchSpy.mockResolvedValueOnce({ ok: true, status: 201, json: async () => mock } as Response);

    const { crearMateria } = await import('./examContentAdmin');
    const res = await crearMateria({ codigo: 'CB101', nombre: 'Análisis Matemático I' });

    expect(res.id).toBe('mat-1');
    expect(res.codigo).toBe('CB101');
    expect(res.nombre).toBe('Análisis Matemático I');
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/exam-content/materias',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer tok' }),
        body: JSON.stringify({ codigo: 'CB101', nombre: 'Análisis Matemático I' }),
      }),
    );
  });

  it('lanza error con status=409 ante código duplicado', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: async () => ({ error: 'duplicado' }),
    } as Response);

    const { crearMateria } = await import('./examContentAdmin');
    const promise = crearMateria({ codigo: 'CB101', nombre: 'Materia X' });

    await expect(promise).rejects.toThrow('duplicado');
    const err = await promise.catch((e: unknown) => e as Error & { status?: number });
    expect(err.status).toBe(409);
  });

  it('lanza error con status=422 ante validación de dominio', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: false,
      status: 422,
      json: async () => ({ error: 'validacion_dominio' }),
    } as Response);

    const { crearMateria } = await import('./examContentAdmin');
    const promise = crearMateria({ codigo: '', nombre: '' });

    await expect(promise).rejects.toThrow('validacion_dominio');
    const err = await promise.catch((e: unknown) => e as Error & { status?: number });
    expect(err.status).toBe(422);
  });
});

// ---------------------------------------------------------------------------
// actualizarMateria — RED → GREEN → TRIANGULATE
// ---------------------------------------------------------------------------

describe('examContentAdmin — actualizarMateria', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, 'fetch');
  });
  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it('PATCH al endpoint con materiaId en URL, token y body; devuelve MateriaResponse', async () => {
    const mock = { id: 'mat-2', codigo: 'CB102', nombre: 'Física I — nuevo nombre' };
    fetchSpy.mockResolvedValueOnce({ ok: true, status: 200, json: async () => mock } as Response);

    const { actualizarMateria } = await import('./examContentAdmin');
    const res = await actualizarMateria('mat-2', { nombre: 'Física I — nuevo nombre' });

    expect(res.nombre).toBe('Física I — nuevo nombre');
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/exam-content/materias/mat-2',
      expect.objectContaining({
        method: 'PATCH',
        headers: expect.objectContaining({ Authorization: 'Bearer tok' }),
        body: JSON.stringify({ nombre: 'Física I — nuevo nombre' }),
      }),
    );
  });

  it('lanza error con status=404 si la materia no existe', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({}),
    } as Response);

    const { actualizarMateria } = await import('./examContentAdmin');
    const promise = actualizarMateria('no-existe', { nombre: 'X' });

    await expect(promise).rejects.toThrow();
    const err = await promise.catch((e: unknown) => e as Error & { status?: number });
    expect(err.status).toBe(404);
  });
});

// ---------------------------------------------------------------------------
// crearComision — RED → GREEN → TRIANGULATE
// ---------------------------------------------------------------------------

describe('examContentAdmin — crearComision', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, 'fetch');
  });
  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it('POST al endpoint con materiaId en URL, token y body; devuelve ComisionResponse', async () => {
    const mock = {
      id: 'com-1',
      materia_id: 'mat-1',
      codigo: '1A',
      nombre: 'Comisión 1A',
      periodo: '2026-1',
      anio: 2026,
    };
    fetchSpy.mockResolvedValueOnce({ ok: true, status: 201, json: async () => mock } as Response);

    const { crearComision } = await import('./examContentAdmin');
    const res = await crearComision('mat-1', {
      codigo: '1A',
      nombre: 'Comisión 1A',
      periodo: '2026-1',
      anio: 2026,
    });

    expect(res.id).toBe('com-1');
    expect(res.materia_id).toBe('mat-1');
    expect(res.periodo).toBe('2026-1');
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/exam-content/materias/mat-1/comisiones',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer tok' }),
        body: JSON.stringify({ codigo: '1A', nombre: 'Comisión 1A', periodo: '2026-1', anio: 2026 }),
      }),
    );
  });

  it('lanza error con status=409 ante comision duplicada', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: async () => ({ error: 'duplicado' }),
    } as Response);

    const { crearComision } = await import('./examContentAdmin');
    const promise = crearComision('mat-1', { codigo: '1A', nombre: 'Comisión 1A' });

    await expect(promise).rejects.toThrow('duplicado');
    const err = await promise.catch((e: unknown) => e as Error & { status?: number });
    expect(err.status).toBe(409);
  });

  it('incluye campos opcionales null si no se pasan', async () => {
    const mock = { id: 'com-2', materia_id: 'mat-1', codigo: '1B', nombre: 'Comisión 1B', periodo: null, anio: null };
    fetchSpy.mockResolvedValueOnce({ ok: true, status: 201, json: async () => mock } as Response);

    const { crearComision } = await import('./examContentAdmin');
    const res = await crearComision('mat-1', { codigo: '1B', nombre: 'Comisión 1B' });

    expect(res.periodo).toBeNull();
    expect(res.anio).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// actualizarComision — RED → GREEN → TRIANGULATE
// ---------------------------------------------------------------------------

describe('examContentAdmin — actualizarComision', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, 'fetch');
  });
  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it('PATCH al endpoint con comisionId en URL, token y body; devuelve ComisionResponse', async () => {
    const mock = {
      id: 'com-5',
      materia_id: 'mat-3',
      codigo: '2A',
      nombre: 'Comisión 2A — actualizada',
      periodo: '2026-2',
      anio: 2026,
    };
    fetchSpy.mockResolvedValueOnce({ ok: true, status: 200, json: async () => mock } as Response);

    const { actualizarComision } = await import('./examContentAdmin');
    const res = await actualizarComision('com-5', {
      nombre: 'Comisión 2A — actualizada',
      periodo: '2026-2',
      anio: 2026,
    });

    expect(res.nombre).toBe('Comisión 2A — actualizada');
    expect(res.anio).toBe(2026);
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/exam-content/comisiones/com-5',
      expect.objectContaining({
        method: 'PATCH',
        headers: expect.objectContaining({ Authorization: 'Bearer tok' }),
        body: JSON.stringify({ nombre: 'Comisión 2A — actualizada', periodo: '2026-2', anio: 2026 }),
      }),
    );
  });

  it('lanza error con status=404 si la comision no existe', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({}),
    } as Response);

    const { actualizarComision } = await import('./examContentAdmin');
    const promise = actualizarComision('no-existe', { nombre: 'X' });

    await expect(promise).rejects.toThrow();
    const err = await promise.catch((e: unknown) => e as Error & { status?: number });
    expect(err.status).toBe(404);
  });

  it('acepta periodo y anio nulos para limpiar los campos', async () => {
    const mock = { id: 'com-6', materia_id: 'mat-1', codigo: '1C', nombre: 'Sin periodo', periodo: null, anio: null };
    fetchSpy.mockResolvedValueOnce({ ok: true, status: 200, json: async () => mock } as Response);

    const { actualizarComision } = await import('./examContentAdmin');
    const res = await actualizarComision('com-6', { nombre: 'Sin periodo', periodo: null, anio: null });

    expect(res.periodo).toBeNull();
    expect(res.anio).toBeNull();
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/exam-content/comisiones/com-6',
      expect.objectContaining({
        body: JSON.stringify({ nombre: 'Sin periodo', periodo: null, anio: null }),
      }),
    );
  });
});
