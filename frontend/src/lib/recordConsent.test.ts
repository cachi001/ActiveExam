// @vitest-environment jsdom
/**
 * RED → GREEN → TRIANGULATE: recordConsent (consentimiento POR EXAMEN) debe enviar
 * al backend la VERSIÓN VIGENTE REAL del consentimiento (la que sincroniza
 * /consent/text), NO una constante mock hardcodeada.
 *
 * Enviar una versión falsa al registro legal de consentimiento viola la regla dura
 * #7 (Ley 25.326: consentimiento demostrable, versionado y atado al usuario). Hoy
 * "funcionaba de casualidad" porque el mock y el backend coincidían en 'v1'.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { api } from './api';
import { setConsentVersionVigente } from './apiCore';

describe('recordConsent — versión vigente real (no mock)', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;
  beforeEach(() => { fetchSpy = vi.spyOn(globalThis, 'fetch'); });
  afterEach(() => { fetchSpy.mockRestore(); });

  it('envía en el body la versión vigente sincronizada, no la constante hardcodeada', async () => {
    setConsentVersionVigente('v-real-2099');
    fetchSpy.mockResolvedValueOnce({
      ok: true, status: 200, json: async () => ({ estado: 'otorgado' }),
    } as Response);

    await api.recordConsent('EX-1');

    const init = fetchSpy.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(init.body as string);
    expect(body.version_texto).toBe('v-real-2099');
  });

  it('triangulación: otra versión vigente también se refleja en el body', async () => {
    setConsentVersionVigente('2027.3');
    fetchSpy.mockResolvedValueOnce({
      ok: true, status: 200, json: async () => ({ estado: 'otorgado' }),
    } as Response);

    await api.recordConsent('EX-2');

    const body = JSON.parse((fetchSpy.mock.calls[0][1] as RequestInit).body as string);
    expect(body.version_texto).toBe('2027.3');
    expect(body.exam_id).toBe('EX-2');
  });
});
