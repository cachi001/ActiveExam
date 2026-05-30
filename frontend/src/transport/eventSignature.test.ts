/**
 * Tests de la firma de eventos en el cliente (C-10). Formato Vitest.
 *
 * Verifica que el mensaje canonico del cliente coincida EXACTAMENTE con el del
 * backend (mismo orden/separador) y que la firma HMAC sea determinista.
 */

import { describe, expect, it } from "vitest";

import { canonicalMessage, signEvent, type SignableEvent } from "./eventSignature";

const EV: SignableEvent = {
  id: "ID",
  session_id: "SES",
  exam_id: "EXA",
  tipo: "heartbeat",
  severidad: "baseline",
  ts_client: "TS",
  schema_version: 1,
};

describe("mensaje canonico", () => {
  it("coincide con el contrato del backend (orden y separador)", () => {
    expect(canonicalMessage(EV)).toBe("ID|SES|EXA|heartbeat|baseline|TS|1");
  });
});

describe("firma HMAC", () => {
  it("es determinista para la misma clave y evento", async () => {
    const a = await signEvent(EV, "clave-hex");
    const b = await signEvent(EV, "clave-hex");
    expect(a).toBe(b);
    expect(a).toMatch(/^[0-9a-f]{64}$/); // HMAC-SHA256 hex
  });

  it("cambia si cambia la clave de sesion", async () => {
    const a = await signEvent(EV, "clave-1");
    const b = await signEvent(EV, "clave-2");
    expect(a).not.toBe(b);
  });

  it("cambia si se altera un campo (integridad)", async () => {
    const a = await signEvent(EV, "k");
    const b = await signEvent({ ...EV, severidad: "alta" }, "k");
    expect(a).not.toBe(b);
  });
});
