/**
 * c-78 §16.5 — el cliente manda la captura BINARIA, sin inflarla en base64.
 *
 * La captura viajaba como data URL dentro del JSON: base64 son 4 bytes de texto por
 * cada 3 de imagen, y encima el JSON escapa el string. Con 100 alumnos subiendo
 * capturas durante dos horas por el enlace de su casa, ese tercio se paga en tiempo
 * de subida.
 *
 * Lo que estos tests fijan es el contrato con el backend, porque equivocarlo NO da
 * un error visible: da un `screenshot_sha256` distinto, o sea evidencia que no
 * verifica, descubierta recién cuando alguien impugna una nota.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { enviarEventoProctoringBinario } from './eventoBinario';

const RESPUESTA_OK = {
  evento_id: 'ev-1',
  veredicto_reinferencia: 'coincide',
  face_count_servidor: 1,
  screenshot_sha256: 'abc123',
};

/** Data URL de una imagen mínima, como la produce `canvas.toDataURL()`. */
const PNG_B64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';
const DATA_URL = `data:image/png;base64,${PNG_B64}`;

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn(async () => ({
    ok: true,
    status: 201,
    json: async () => RESPUESTA_OK,
  }));
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function cuerpoEnviado(): FormData {
  return fetchMock.mock.calls[0][1].body as FormData;
}

describe('enviarEventoProctoringBinario', () => {
  it('manda la imagen como Blob, no como texto base64', async () => {
    await enviarEventoProctoringBinario('s-1', {
      tipo: 'rostro_ausente',
      severidad: 'media',
      ts_cliente: '2026-08-26T20:00:00Z',
      screenshot_base64: DATA_URL,
    });

    const captura = cuerpoEnviado().get('captura');
    expect(captura).toBeInstanceOf(Blob);
    // Los bytes crudos pesan menos que el texto base64 que los representaba.
    expect((captura as Blob).size).toBeLessThan(PNG_B64.length);
  });

  it('manda el prefijo del data URL aparte, para que el servidor rearme el string exacto', async () => {
    await enviarEventoProctoringBinario('s-1', {
      tipo: 'rostro_ausente',
      severidad: 'media',
      ts_cliente: '2026-08-26T20:00:00Z',
      screenshot_base64: DATA_URL,
    });

    // Sin el prefijo el servidor no puede reconstruir el mismo string y el hash
    // saldría distinto: evidencia que no verifica.
    expect(cuerpoEnviado().get('screenshot_prefijo')).toBe('data:image/png;base64');
  });

  it('conserva el mime original en vez de asumir PNG', async () => {
    const jpeg = 'data:image/jpeg;base64,' + PNG_B64;

    await enviarEventoProctoringBinario('s-1', {
      tipo: 'rostro_ausente',
      severidad: 'media',
      ts_cliente: '2026-08-26T20:00:00Z',
      screenshot_base64: jpeg,
    });

    expect(cuerpoEnviado().get('screenshot_prefijo')).toBe('data:image/jpeg;base64');
  });

  it('traduce la severidad al vocabulario del backend', async () => {
    // El frontend la maneja en femenino y el backend en masculino. Sin el mapeo el
    // POST da 422 y el evento se pierde en silencio, que es un bug ya visto.
    await enviarEventoProctoringBinario('s-1', {
      tipo: 'rostro_ausente',
      severidad: 'critica',
      ts_cliente: '2026-08-26T20:00:00Z',
    });

    expect(cuerpoEnviado().get('severidad')).toBe('critico');
  });

  it('manda el evento aunque no tenga captura', async () => {
    // `cambio_pestana` y `copiar_pegar` no traen imagen.
    await enviarEventoProctoringBinario('s-1', {
      tipo: 'cambio_pestana',
      severidad: 'baja',
      ts_cliente: '2026-08-26T20:00:00Z',
    });

    const cuerpo = cuerpoEnviado();
    expect(cuerpo.get('captura')).toBeNull();
    expect(cuerpo.get('tipo')).toBe('cambio_pestana');
  });

  it('NO fija Content-Type: el navegador tiene que poner el boundary del multipart', async () => {
    await enviarEventoProctoringBinario('s-1', {
      tipo: 'rostro_ausente',
      severidad: 'media',
      ts_cliente: '2026-08-26T20:00:00Z',
      screenshot_base64: DATA_URL,
    });

    const headers = (fetchMock.mock.calls[0][1].headers ?? {}) as Record<string, string>;
    expect(headers['Content-Type']).toBeUndefined();
  });

  it('pega en el endpoint binario, no en el JSON', async () => {
    await enviarEventoProctoringBinario('s-99', {
      tipo: 'rostro_ausente',
      severidad: 'media',
      ts_cliente: '2026-08-26T20:00:00Z',
    });

    expect(fetchMock.mock.calls[0][0]).toContain('/proctoring/sessions/s-99/events/binario');
  });

  it('PROPAGA el error si el envío falla', async () => {
    // Igual que el camino JSON: dar por enviado lo que no llegó vacía el buffer sin
    // haber mandado nada, y la resiliencia ante cortes queda decorativa.
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 503,
      clone: () => ({ json: async () => ({}) }),
      json: async () => ({}),
    });

    await expect(
      enviarEventoProctoringBinario('s-1', {
        tipo: 'rostro_ausente',
        severidad: 'media',
        ts_cliente: '2026-08-26T20:00:00Z',
      }),
    ).rejects.toThrow();
  });

  it('un data URL ilegible no rompe el envío: manda el evento sin captura', async () => {
    // Perder el registro de que algo pasó es peor que perder la imagen (L2.5).
    await enviarEventoProctoringBinario('s-1', {
      tipo: 'rostro_ausente',
      severidad: 'media',
      ts_cliente: '2026-08-26T20:00:00Z',
      screenshot_base64: 'esto no es un data url',
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(cuerpoEnviado().get('captura')).toBeNull();
  });
});
