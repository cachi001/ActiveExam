/**
 * Los catálogos tienen que salir CON el token en el primer intento.
 *
 * ## El defecto
 *
 * `fetchAutenticado` no arma el header `Authorization`: lo espera en el `init`
 * que le pasa quien llama, y solo lo agrega en el REINTENTO posterior al 401.
 * `catalogosNota` lo llamaba sin ningún `init`, así que cada carga de catálogo
 * hacía tres viajes en vez de uno:
 *
 *   GET /catalogos/resultados-nota  -> 401 "Falta el Bearer token."
 *   POST /auth/refresh              -> 200
 *   GET /catalogos/resultados-nota  -> 200
 *
 * Visible en la consola del alumno apenas entra a «Mis exámenes» (el chip de
 * resultado de cada nota usa este catálogo). No filtraba nada — el endpoint
 * rechaza correctamente sin token — pero gastaba un refresh por catálogo y
 * llenaba la consola de 401 que parecían un problema de seguridad.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./authProvider', () => ({
  authProvider: {
    getToken: () => 'token-de-prueba',
    refresh: vi.fn(async () => 'token-fresco'),
  },
}));

import { cargarResultados, _resetCacheCatalogos } from './catalogosNota';

const respuestaOk = () =>
  Promise.resolve(
    new Response(JSON.stringify([{ valor: 'aprobado', etiqueta: 'Aprobado', tono: 'success' }]), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  );

beforeEach(() => {
  _resetCacheCatalogos();
  vi.stubGlobal('fetch', vi.fn(respuestaOk));
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('carga de catálogos de nota', () => {
  it('manda el Authorization en el PRIMER intento', async () => {
    await cargarResultados();

    const [, init] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const headers = new Headers((init as RequestInit).headers);
    expect(headers.get('Authorization')).toBe('Bearer token-de-prueba');
  });

  it('un solo viaje: sin 401 no hay refresh ni reintento', async () => {
    await cargarResultados();
    expect((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls).toHaveLength(1);
  });

  it('cachea: la segunda llamada no vuelve a pegarle a la red', async () => {
    await cargarResultados();
    await cargarResultados();
    expect((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls).toHaveLength(1);
  });

  it('sin sesión no rompe la pantalla: cae al respaldo', async () => {
    // Degradación silenciosa: el chip de nota tiene que pintar igual.
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('{"detail":"Falta el Bearer token."}', { status: 401 })),
    );
    const items = await cargarResultados();
    expect(items.length).toBeGreaterThan(0);
  });
});
