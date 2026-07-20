/**
 * TDD: RED → GREEN → TRIANGULATE
 * Test de la capa de API para las estadísticas institucionales (C-20).
 *
 * Cubre `obtenerResumenStats`: URL, método GET, auth header y el manejo de
 * error HTTP (que NO debe devolverse como datos en cero). Sin tocar la DB:
 * se mockea `fetch` en el borde (regla dura #4 aplica a la DB, no al fetch de
 * red; acá el "no confiable" es el transporte).
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

vi.mock('./authProvider', () => ({
  authProvider: { getToken: () => 'tok', refresh: undefined },
}));

const RESUMEN_OK = {
  total_examenes: 12,
  total_materias: 4,
  total_comisiones: 7,
  total_sesiones: 30,
  sesiones_finalizadas: 25,
  sesiones_en_riesgo: 3,
  umbral_riesgo: 70,
  distribucion_scores: { '0-24': 18, '25-49': 6, '50-69': 3, '70-100': 3 },
};

describe('apiStats — obtenerResumenStats', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, 'fetch');
  });
  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it('GET a /stats/resumen con token, devuelve el sumario tipado', async () => {
    fetchSpy.mockResolvedValueOnce({ ok: true, status: 200, json: async () => RESUMEN_OK } as Response);

    const { api } = await import('./api');
    const res = await api.obtenerResumenStats();

    expect(res.total_examenes).toBe(12);
    expect(res.sesiones_en_riesgo).toBe(3);
    expect(res.distribucion_scores['70-100']).toBe(3);
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/stats/resumen',
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({ Authorization: 'Bearer tok' }),
      }),
    );
  });

  it('propaga el error HTTP (NO lo devuelve como datos en cero)', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: false,
      status: 403,
      clone: () => ({ json: async () => ({}) }),
      json: async () => ({}),
    } as unknown as Response);

    const { api } = await import('./api');
    await expect(api.obtenerResumenStats()).rejects.toMatchObject({ status: 403 });
  });
});
