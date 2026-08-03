/**
 * TDD: RED → GREEN → TRIANGULATE
 *
 * Bug real encontrado en verificación E2E de C-73 (selección de evidencia del
 * revisor, el cambio más grande de esta rama): el backend GET
 * /proctoring/sessions/{id} devuelve cada evento con la clave `id` (ver
 * `EventoDetalle` en app/presentation/api/v1/proctoring/sessions/schemas.py),
 * pero el tipo del frontend `EventoProctoringDetalle` espera `evento_id`.
 * `getSesionProctoring` hacía un cast directo sin mapear, así que
 * `ev.evento_id` quedaba `undefined` en TODOS los eventos — y como todos
 * comparten el mismo valor `undefined`, seleccionar UNA captura como
 * evidencia en `DecisionRevisorForm` marcaba las 15 (o las que hubiera) como
 * seleccionadas a la vez. Verificado en vivo contra datos reales: el
 * `aria-pressed` de los 15 botones de "elegir evidencia" quedaba en `true`
 * apenas se tocaba uno solo.
 *
 * Este test fija el contrato: `getSesionProctoring` debe mapear `id` →
 * `evento_id` para que cada evento tenga un identificador ÚNICO y utilizable
 * por la selección de evidencia.
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../authProvider', () => ({
  authProvider: { getToken: () => 'tok', refresh: undefined },
}));

const SESION_RAW = {
  id: 'sess-1',
  modo: 'examen',
  etiqueta: null,
  examen_contenido_id: 'exam-1',
  creada_en: '2026-08-03T10:00:00Z',
  finalizada_en: '2026-08-03T10:30:00Z',
  score: 100,
  biometria: null,
  cierre_forzado_en: null,
  cierre_forzado_motivo: null,
  eventos: [
    {
      id: 'evt-AAA',
      tipo: 'rostro_ausente',
      severidad: 'critica',
      ts_cliente: '2026-08-03T10:10:00Z',
      ts_backend: '2026-08-03T10:10:00Z',
      payload: null,
      screenshot_base64: 'AAAA',
      screenshot_sha256: 'hash-aaaa',
      face_count_cliente: 0,
      face_count_servidor: 0,
      veredicto_reinferencia: 'coincide',
      en_pausa_autorizada: false,
    },
    {
      id: 'evt-BBB',
      tipo: 'rostro_ausente',
      severidad: 'critica',
      ts_cliente: '2026-08-03T10:11:00Z',
      ts_backend: '2026-08-03T10:11:00Z',
      payload: null,
      // Screenshot IDÉNTICO al del otro evento (mismo hash) — la selección
      // NO puede depender del hash, cada evento necesita su PROPIO id.
      screenshot_base64: 'AAAA',
      screenshot_sha256: 'hash-aaaa',
      face_count_cliente: 0,
      face_count_servidor: 0,
      veredicto_reinferencia: 'coincide',
      en_pausa_autorizada: false,
    },
  ],
};

describe('revisionApi.getSesionProctoring — mapeo de evento_id', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, 'fetch');
  });
  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it('mapea el id de cada evento del backend a evento_id, distinto por evento', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => SESION_RAW,
    } as Response);

    const { revisionApi } = await import('./revision');
    const detalle = await revisionApi.getSesionProctoring('sess-1');

    expect(detalle.eventos).toHaveLength(2);
    expect(detalle.eventos[0].evento_id).toBe('evt-AAA');
    expect(detalle.eventos[1].evento_id).toBe('evt-BBB');
    expect(detalle.eventos[0].evento_id).not.toBe(detalle.eventos[1].evento_id);
  });

  it('triangulación: con un solo evento, evento_id sigue viajando (no queda undefined)', async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ ...SESION_RAW, eventos: [SESION_RAW.eventos[0]] }),
    } as Response);

    const { revisionApi } = await import('./revision');
    const detalle = await revisionApi.getSesionProctoring('sess-1');

    expect(detalle.eventos[0].evento_id).toBe('evt-AAA');
    expect(detalle.eventos[0].evento_id).toBeDefined();
  });
});
