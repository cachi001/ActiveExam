/**
 * Tests de withTimeout (C-67 fix): red de seguridad para que la carga del motor
 * de visión NUNCA quede colgada infinitamente en el teléfono. Si la promesa no
 * resuelve a tiempo, rechaza con un error claro y el caller cae al fallback manual.
 */

import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { withTimeout } from "./withTimeout";

describe("withTimeout", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("resuelve con el valor original si la promesa resuelve antes del timeout", async () => {
    const p = Promise.resolve("ok");
    await expect(withTimeout(p, 1000)).resolves.toBe("ok");
  });

  it("rechaza con el error original si la promesa rechaza antes del timeout", async () => {
    const p = Promise.reject(new Error("falla real"));
    await expect(withTimeout(p, 1000)).rejects.toThrow("falla real");
  });

  it("rechaza con un error de timeout si la promesa no resuelve a tiempo", async () => {
    // Promesa que nunca settlea
    const p = new Promise<string>(() => {});
    const racer = withTimeout(p, 5000, "tardó demasiado");
    // Adelantar el reloj más allá del timeout
    vi.advanceTimersByTime(5001);
    await expect(racer).rejects.toThrow(/tardó demasiado/i);
  });

  it("no dispara el timeout si la promesa ya resolvió (no rechaza después)", async () => {
    const p = Promise.resolve(42);
    const result = await withTimeout(p, 1000);
    expect(result).toBe(42);
    // Avanzar el reloj: no debe haber rechazo pendiente ni efecto
    vi.advanceTimersByTime(2000);
  });
});
