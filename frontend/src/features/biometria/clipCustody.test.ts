/**
 * Tests de la custodia del clip en el cliente (C-09, RN-BIO-07).
 *
 * Formato Vitest. Cubre el hash SHA-256 del clip (custodia inicial) y la subida
 * directa por URL firmada (no transita el backend, RN-CC-04).
 */

import { describe, expect, it, vi } from "vitest";

import { bufferToHex, hashClip, uploadClip } from "./clipCustody";

describe("hash del clip (custodia inicial)", () => {
  it("calcula SHA-256 hex via WebCrypto inyectable", async () => {
    // SHA-256 de bytes vacios es e3b0c442... (vector conocido).
    const subtle = {
      digest: async (_alg: string, _data: ArrayBuffer) =>
        // Devuelve un buffer fijo para verificar el formateo hex.
        new Uint8Array([0xde, 0xad, 0xbe, 0xef]).buffer,
    } as unknown as SubtleCrypto;
    const hex = await hashClip(new ArrayBuffer(0), subtle);
    expect(hex).toBe("deadbeef");
  });

  it("bufferToHex formatea con padding de dos digitos", () => {
    expect(bufferToHex(new Uint8Array([0, 15, 255]).buffer)).toBe("000fff");
  });
});

describe("subida del clip por URL firmada", () => {
  it("hace PUT directo al storage y devuelve el object_key", async () => {
    const fetchImpl = vi.fn(async () => ({ ok: true, status: 200 }) as Response);
    const key = await uploadClip(
      { upload_url: "https://storage/clip?sig=abc", object_key: "clips/1", expires_in: 900 },
      new ArrayBuffer(8),
      fetchImpl as unknown as typeof fetch,
    );
    expect(key).toBe("clips/1");
    expect(fetchImpl).toHaveBeenCalledWith(
      "https://storage/clip?sig=abc",
      expect.objectContaining({ method: "PUT" }),
    );
  });

  it("lanza si el storage rechaza la subida", async () => {
    const fetchImpl = vi.fn(async () => ({ ok: false, status: 403 }) as Response);
    await expect(
      uploadClip(
        { upload_url: "u", object_key: "k", expires_in: 900 },
        new ArrayBuffer(8),
        fetchImpl as unknown as typeof fetch,
      ),
    ).rejects.toThrow();
  });
});
