/**
 * Tests de la captura de evidencia en el cliente (C-12 + C-24, etapa 1).
 * Formato Vitest.
 *
 * C-24: el artefacto pasa de clip a SCREENSHOT (frame único).
 * Disparo por:
 *   - trigger "event"    → SOLO severidad alta/critica (RN-CC-01).
 *   - trigger "heartbeat" → siempre (cadencia de línea base, DD-24-02).
 * Hash + firma en origen; upload directo por presigned URL (no transita el backend).
 */

import { describe, expect, it, vi } from "vitest";

import {
  capturarEvidencia,
  disparaCaptura,
  firmarScreenshot,
} from "./evidenceCapture";

// ---------------------------------------------------------------------------
// Disparo por severidad (RN-CC-01)
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// capturarEvidencia — trigger "event"
// ---------------------------------------------------------------------------

describe("capturarEvidencia — trigger event", () => {
  const screenshot = new TextEncoder().encode("screenshot-de-evidencia").buffer;

  function deps(fetchImpl: typeof fetch) {
    return {
      sessionId: "sess-1",
      examId: "e1",
      sessionKey: "clave-hex",
      presign: vi.fn().mockResolvedValue({
        upload_url: "https://storage/bucket/key?sig",
        object_key: "evidence/screenshot-1.png",
        expires_in: 900,
      }),
      fetchImpl,
    };
  }

  it("no captura nada si la severidad no es severa (trigger event)", async () => {
    const result = await capturarEvidencia("media", screenshot, deps(vi.fn()), "event");
    expect(result).toBeNull();
  });

  it("hashea, firma y sube directo por presigned URL ante evento severo", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, status: 200 } as Response);
    const result = await capturarEvidencia("alta", screenshot, deps(fetchImpl), "event");
    expect(result).not.toBeNull();
    expect(result!.hash_cliente).toMatch(/^[0-9a-f]{64}$/);
    expect(result!.firma_cliente).toMatch(/^[0-9a-f]{64}$/);
    expect(result!.object_key).toBe("evidence/screenshot-1.png");
    expect(result!.trigger).toBe("event");
    expect(result!.severidad).toBe("alta");
    // Subida DIRECTA al storage (PUT a la upload_url, no al backend).
    expect(fetchImpl).toHaveBeenCalledWith(
      "https://storage/bucket/key?sig",
      expect.objectContaining({ method: "PUT" }),
    );
  });

  it("trigger omitido (default) = 'event': respeta RN-CC-01", async () => {
    // Sin pasar trigger, se usa el default "event".
    const result = await capturarEvidencia("media", screenshot, deps(vi.fn()));
    expect(result).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// capturarEvidencia — trigger "heartbeat" (C-24, DD-24-02)
// ---------------------------------------------------------------------------

describe("capturarEvidencia — trigger heartbeat", () => {
  const screenshot = new TextEncoder().encode("heartbeat-frame").buffer;

  function deps(fetchImpl: typeof fetch) {
    return {
      sessionId: "sess-hb",
      examId: "e2",
      sessionKey: "clave-heartbeat",
      presign: vi.fn().mockResolvedValue({
        upload_url: "https://storage/bucket/hb?sig",
        object_key: "evidence/hb-1.png",
        expires_in: 900,
      }),
      fetchImpl,
    };
  }

  it("heartbeat siempre captura, independientemente de la severidad", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, status: 200 } as Response);
    // Heartbeat con severidad "baseline" (normalmente no dispara captura event-driven).
    const result = await capturarEvidencia("baseline", screenshot, deps(fetchImpl), "heartbeat");
    expect(result).not.toBeNull();
    expect(result!.trigger).toBe("heartbeat");
    expect(result!.severidad).toBeUndefined(); // heartbeats no tienen severidad de evento
    expect(result!.hash_cliente).toMatch(/^[0-9a-f]{64}$/);
    expect(result!.object_key).toBe("evidence/hb-1.png");
  });

  it("heartbeat también sube directo al storage por presigned URL", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, status: 200 } as Response);
    await capturarEvidencia("baseline", screenshot, deps(fetchImpl), "heartbeat");
    expect(fetchImpl).toHaveBeenCalledWith(
      "https://storage/bucket/hb?sig",
      expect.objectContaining({ method: "PUT" }),
    );
  });
});

// ---------------------------------------------------------------------------
// firmarScreenshot — estabilidad HMAC (C-24)
// ---------------------------------------------------------------------------

describe("firmarScreenshot", () => {
  it("la firma es estable para el mismo hash y clave", async () => {
    const a = await firmarScreenshot("abc123", "clave-hex");
    const b = await firmarScreenshot("abc123", "clave-hex");
    expect(a).toBe(b);
    expect(a).toMatch(/^[0-9a-f]{64}$/);
  });

  it("firmas distintas para claves distintas", async () => {
    const a = await firmarScreenshot("abc123", "clave-1");
    const b = await firmarScreenshot("abc123", "clave-2");
    expect(a).not.toBe(b);
  });
});
