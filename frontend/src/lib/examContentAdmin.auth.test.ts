/**
 * TDD: RED → GREEN → TRIANGULATE
 *
 * Bug real (2026-08-22): "Guardar destino" en el detalle del examen fallaba con
 * "Falta el Bearer token." después de ~15 minutos de sesión. El access token
 * vive 900 s; al expirar, `JwtAdapter._getStoredToken()` lo BORRA de
 * sessionStorage y `getToken()` devuelve undefined, así que `authHeaders()`
 * armaba el request SIN header `Authorization` y el backend respondía 401
 * ("Falta el Bearer token." — dependencies.py). `realFetch` ya resolvía esto
 * (401 → refresh → reintento, C-67), pero `examContentAdmin` usa `fetch` crudo
 * y nunca pasó por ahí: el refresh_token seguía siendo válido y nadie lo usaba.
 *
 * Estos tests fijan el contrato: toda llamada de este módulo se recupera de un
 * 401 refrescando UNA vez y reintentando.
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

const auth = vi.hoisted(() => ({
  getToken: vi.fn<[], string | undefined>(() => undefined),
  refresh: vi.fn<[], Promise<string | undefined>>(async () => 'tok-fresco'),
}));

vi.mock('./authProvider', () => ({ authProvider: auth }));

const RESP_401 = {
  ok: false,
  status: 401,
  json: async () => ({ detail: 'Falta el Bearer token.' }),
} as Response;

const okCon = (body: unknown) =>
  ({ ok: true, status: 200, json: async () => body }) as Response;

describe('examContentAdmin — recuperación del access token vencido', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, 'fetch');
    auth.getToken.mockReturnValue(undefined);
    auth.refresh.mockResolvedValue('tok-fresco');
  });
  afterEach(() => {
    fetchSpy.mockRestore();
    vi.clearAllMocks();
  });

  it('con el token vencido refresca y reintenta el guardado del destino', async () => {
    const guardado = { examen_id: 'ex-1', moodle_courseid: 12, moodle_cmid: 34 };
    fetchSpy.mockResolvedValueOnce(RESP_401).mockResolvedValueOnce(okCon(guardado));

    const { setMoodleTarget } = await import('./examContentAdmin');
    const res = await setMoodleTarget('ex-1', { moodle_courseid: 12, moodle_cmid: 34 });

    expect(res.moodle_courseid).toBe(12);
    expect(auth.refresh).toHaveBeenCalledTimes(1);
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(fetchSpy.mock.calls[1][1]).toMatchObject({
      method: 'POST',
      headers: expect.objectContaining({ Authorization: 'Bearer tok-fresco' }),
      body: JSON.stringify({ moodle_courseid: 12, moodle_cmid: 34 }),
    });
  });

  it('también se recupera al LEER el destino (no solo al guardar)', async () => {
    const destino = { examen_id: 'ex-2', moodle_courseid: 7, moodle_cmid: null };
    fetchSpy.mockResolvedValueOnce(RESP_401).mockResolvedValueOnce(okCon(destino));

    const { getMoodleTarget } = await import('./examContentAdmin');
    const res = await getMoodleTarget('ex-2');

    expect(res.moodle_courseid).toBe(7);
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(fetchSpy.mock.calls[1][1]).toMatchObject({
      method: 'GET',
      headers: expect.objectContaining({ Authorization: 'Bearer tok-fresco' }),
    });
  });

  it('si el refresh tampoco sirve, propaga el error sin reintentar en loop', async () => {
    auth.refresh.mockResolvedValue(undefined);
    fetchSpy.mockResolvedValue(RESP_401);

    const { setMoodleTarget } = await import('./examContentAdmin');
    await expect(
      setMoodleTarget('ex-3', { moodle_courseid: 1, moodle_cmid: 2 }),
    ).rejects.toThrow('Falta el Bearer token.');

    // Un solo intento: sin token fresco no tiene sentido repetir el request.
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it('con el token vigente no gasta un refresh de más', async () => {
    auth.getToken.mockReturnValue('tok-vigente');
    fetchSpy.mockResolvedValueOnce(okCon({ examen_id: 'ex-4', moodle_courseid: 1, moodle_cmid: 2 }));

    const { setMoodleTarget } = await import('./examContentAdmin');
    await setMoodleTarget('ex-4', { moodle_courseid: 1, moodle_cmid: 2 });

    expect(auth.refresh).not.toHaveBeenCalled();
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(fetchSpy.mock.calls[0][1]).toMatchObject({
      headers: expect.objectContaining({ Authorization: 'Bearer tok-vigente' }),
    });
  });
});
