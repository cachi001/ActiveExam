/**
 * El envío de RESPUESTAS tiene que decir la verdad sobre si llegó (c-78).
 *
 * ## El bug
 *
 * `enviarRespuestasProctoring` propagaba solo los 409 de plazo y degradaba
 * CUALQUIER otro error a `null`, incluida la caída de red. Eso dejaba muerto el
 * manejo de error de los dos llamadores de `Examen.tsx`:
 *
 *  - **La entrega manual** (`entregar`) tiene una rama explícita: "error de RED en
 *    entrega manual: revertir para permitir reintento. No finalizamos", con el
 *    comentario "terminarle el examen sin haber guardado nada sería el peor
 *    resultado posible". Como la función nunca lanzaba por red, esa rama NUNCA
 *    corría: el examen se finalizaba y navegaba a /cierre igual, con las
 *    respuestas sin llegar al servidor.
 *  - **El autoguardado** marca `guardadoEnRiesgo` para mostrarle al alumno "no
 *    estamos pudiendo guardar tus respuestas". Como el POST resolvía con `null`
 *    en vez de rechazar, corría el `.then` y el aviso se APAGABA justo cuando
 *    había que encenderlo.
 *
 * Los dos caminos estaban escritos bien; lo que fallaba era esta capa, que se
 * comía el error antes de que llegaran a enterarse.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { respuestasApi } from "./respuestas";

const ITEMS = [{ pregunta_id: "p1", opcion_elegida_id: "o1" }];

function respuestaHttp(status: number, body: unknown = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  };
}

describe("enviarRespuestasProctoring", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("PROPAGA la caída de red en vez de devolver null", async () => {
    // Sin esto, `entregar()` finaliza el examen y navega a /cierre creyendo que
    // las respuestas llegaron.
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(
      respuestasApi.enviarRespuestasProctoring("sesion-1", ITEMS),
    ).rejects.toThrow();
  });

  it("PROPAGA un 500 del servidor", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respuestaHttp(500, { detail: "boom" })));

    await expect(
      respuestasApi.enviarRespuestasProctoring("sesion-1", ITEMS),
    ).rejects.toThrow();
  });

  it("sigue propagando el 409 de plazo con su código, como antes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(respuestaHttp(409, { code: "tiempo_agotado" })),
    );

    await expect(
      respuestasApi.enviarRespuestasProctoring("sesion-1", ITEMS),
    ).rejects.toMatchObject({ status: 409 });
  });

  it("cuando llega bien devuelve el conteo del backend", async () => {
    const body = { session_id: "sesion-1", respuestas_guardadas: 1 };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respuestaHttp(200, body)));

    await expect(
      respuestasApi.enviarRespuestasProctoring("sesion-1", ITEMS),
    ).resolves.toEqual(body);
  });

  it("sin sessionId devuelve null sin tocar la red (no hay nada que mandar)", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await expect(respuestasApi.enviarRespuestasProctoring("", ITEMS)).resolves.toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("NO manda identidad del cliente: el backend usa la del JWT (H4)", async () => {
    const fetchMock = vi.fn().mockResolvedValue(respuestaHttp(200, {}));
    vi.stubGlobal("fetch", fetchMock);

    await respuestasApi.enviarRespuestasProctoring("sesion-1", ITEMS);

    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(Object.keys(body)).toEqual(["respuestas"]);
  });
});

describe("obtenerRespuestasProctoring", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("PROPAGA el fallo en vez de devolver [] (que se lee como 'no contestaste nada')", async () => {
    // Es la restauración tras recargar la página a mitad del examen. Devolver []
    // ante un error de red le muestra al alumno un examen EN BLANCO aunque el
    // servidor tenga sus respuestas — y lo empuja a contestar todo de nuevo.
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(
      respuestasApi.obtenerRespuestasProctoring("sesion-1"),
    ).rejects.toThrow();
  });

  it("cuando llega bien devuelve las respuestas guardadas", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        respuestaHttp(200, { session_id: "sesion-1", respuestas: ITEMS }),
      ),
    );

    await expect(
      respuestasApi.obtenerRespuestasProctoring("sesion-1"),
    ).resolves.toEqual(ITEMS);
  });

  it("sin sessionId devuelve [] sin tocar la red", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await expect(respuestasApi.obtenerRespuestasProctoring("")).resolves.toEqual([]);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
