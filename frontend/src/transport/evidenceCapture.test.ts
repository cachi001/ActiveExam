/**
 * Tests de la captura de evidencia en el cliente (C-12, etapa 1). Formato Vitest.
 *
 * Disparo SOLO por severidad alta/critica; hash + firma en origen; upload directo por
 * presigned URL (no transita el backend).
 */

import { describe, expect, it, vi } from "vitest";

import { capturarEvidencia, disparaCaptura, firmarClip } from "./evidenceCapture";

describe("disparo por severidad (RN-CC-01)", () => {
  it("alta y critica disparan captura", () => {
    expect(disparaCaptura("alta")).toBe(true);
    expect(disparaCaptura("critica")).toBe(true);
  });
  it("media, baja y baseline NO disparan", () => {
    expect(disparaCaptura("media")).toBe(false);
    expect(disparaCaptura("baja")).toBe(false);
    expect(disparaCaptura("baseline")).toBe(false);
  });
});

describe("capturarEvidencia", () => {
  const clip = new TextEncoder().encode("clip-de-evidencia").buffer;

  function deps(fetchImpl: typeof fetch) {
    return {
      sessionId: "sess-1",
      examId: "e1",
      sessionKey: "clave-hex",
      presign: vi.fn().mockResolvedValue({
        upload_url: "https://storage/bucket/key?sig",
        object_key: "evidence/clip-1.bin",
        expires_in: 900,
      }),
      fetchImpl,
    };
  }

  it("no captura nada si la severidad no es severa", async () => {
    const result = await capturarEvidencia("media", clip, deps(vi.fn()));
    expect(result).toBeNull();
  });

  it("hashea, firma y sube directo por presigned URL ante evento severo", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, status: 200 } as Response);
    const result = await capturarEvidencia("alta", clip, deps(fetchImpl));
    expect(result).not.toBeNull();
    expect(result!.hash_cliente).toMatch(/^[0-9a-f]{64}$/);
    expect(result!.firma_cliente).toMatch(/^[0-9a-f]{64}$/);
    expect(result!.object_key).toBe("evidence/clip-1.bin");
    // Subida DIRECTA al storage (PUT a la upload_url, no al backend).
    expect(fetchImpl).toHaveBeenCalledWith(
      "https://storage/bucket/key?sig",
      expect.objectContaining({ method: "PUT" }),
    );
  });

  it("la firma del clip es estable para el mismo hash y clave", async () => {
    const a = await firmarClip("abc123", "clave-hex");
    const b = await firmarClip("abc123", "clave-hex");
    expect(a).toBe(b);
    expect(a).toMatch(/^[0-9a-f]{64}$/);
  });
});
