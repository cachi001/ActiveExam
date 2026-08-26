/**
 * Los envíos de proctoring tienen que DECIR LA VERDAD sobre si llegaron (c-78).
 *
 * ## El bug que estos tests fijan
 *
 * Las tres funciones de envío de la sesión se tragaban cualquier error y
 * devolvían un valor de éxito:
 *
 *   - `enviarEventoProctoring` → `catch { return null }`
 *   - `enviarBiometriaProctoring` → `catch { return { ok: true } }`  ← decía OK
 *   - `finalizarSesionProctoring` → `catch { return null }`
 *
 * El comentario las llamaba "fire-and-forget seguro", pero el llamador NO es
 * fire-and-forget: es un buffer con reintento. El patrón buffer-first del examen
 * hace `append → POST → confirm(purgar)`, y como el POST nunca rechazaba, el
 * `confirm` corría SIEMPRE — incluso con la red caída. **El buffer de IndexedDB
 * se vaciaba solo en cada evento y el replay no encontraba nunca nada que
 * reenviar.** Toda la resiliencia ante cortes era decorativa.
 *
 * La biométrica era peor: devolvía `{ ok: true }` con la red caída, así que el
 * llamador borraba el payload dándolo por entregado.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { sesionApi } from "./sesion";

const PAYLOAD_EVENTO = {
  tipo: "multiples_rostros",
  severidad: "alta",
  ts_cliente: "2026-08-25T12:00:00.000Z",
};

const PAYLOAD_BIO = {
  liveness_ok: true,
  retos_resueltos: ["parpadeo"],
  resultado: "verificado",
};

function mockFetchQueFalla(motivo: Error) {
  return vi.fn().mockRejectedValue(motivo);
}

function mockFetchConEstado(status: number) {
  return vi.fn().mockResolvedValue({
    ok: false,
    status,
    json: async () => ({ detail: "no" }),
    text: async () => "no",
  });
}

describe("los envíos de proctoring no pueden mentir sobre el resultado", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  describe("enviarEventoProctoring", () => {
    it("propaga el fallo de red en vez de devolver null", async () => {
      // Si no propaga, el llamador purga el evento del buffer creyendo que llegó.
      vi.stubGlobal("fetch", mockFetchQueFalla(new TypeError("Failed to fetch")));

      await expect(
        sesionApi.enviarEventoProctoring("sesion-1", PAYLOAD_EVENTO),
      ).rejects.toThrow();
    });

    it("propaga el error del servidor (500) en vez de darlo por bueno", async () => {
      vi.stubGlobal("fetch", mockFetchConEstado(500));

      await expect(
        sesionApi.enviarEventoProctoring("sesion-1", PAYLOAD_EVENTO),
      ).rejects.toThrow();
    });

    it("cuando sale bien devuelve la respuesta del backend", async () => {
      const respuesta = {
        evento_id: "e1",
        veredicto_reinferencia: "coincide",
        face_count_servidor: 1,
        screenshot_sha256: "abc",
      };
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => respuesta }),
      );

      await expect(
        sesionApi.enviarEventoProctoring("sesion-1", PAYLOAD_EVENTO),
      ).resolves.toEqual(respuesta);
    });

    it("manda el hash del cliente que el backend usa para la cadena de custodia", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValue({ ok: true, status: 200, json: async () => ({}) });
      vi.stubGlobal("fetch", fetchMock);

      await sesionApi.enviarEventoProctoring("sesion-1", {
        ...PAYLOAD_EVENTO,
        screenshot_sha256_cliente: "a".repeat(64),
      });

      const body = JSON.parse(fetchMock.mock.calls[0][1].body as string);
      expect(body.screenshot_sha256_cliente).toBe("a".repeat(64));
    });
  });

  describe("enviarBiometriaProctoring", () => {
    it("NO devuelve ok:true con la red caída", async () => {
      // Era el peor de los tres: afirmaba éxito, así que el llamador borraba el
      // payload de la verificación de identidad dándolo por entregado.
      vi.stubGlobal("fetch", mockFetchQueFalla(new TypeError("Failed to fetch")));

      await expect(
        sesionApi.enviarBiometriaProctoring("sesion-1", PAYLOAD_BIO),
      ).rejects.toThrow();
    });

    it("cuando sale bien devuelve la respuesta del backend", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ ok: true }) }),
      );

      await expect(
        sesionApi.enviarBiometriaProctoring("sesion-1", PAYLOAD_BIO),
      ).resolves.toEqual({ ok: true });
    });
  });

  describe("finalizarSesionProctoring", () => {
    it("propaga el fallo: una sesión que no se finalizó queda 'en vivo' para siempre", async () => {
      vi.stubGlobal("fetch", mockFetchQueFalla(new TypeError("Failed to fetch")));

      await expect(
        sesionApi.finalizarSesionProctoring("sesion-1"),
      ).rejects.toThrow();
    });

    it("sin sessionId no toca la red (no es un fallo, no hay nada que finalizar)", async () => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      await expect(sesionApi.finalizarSesionProctoring("")).resolves.toBeNull();
      expect(fetchMock).not.toHaveBeenCalled();
    });
  });
});
