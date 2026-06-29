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
