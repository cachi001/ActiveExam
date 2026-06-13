/**
 * Tests de los detectores de contexto del navegador (C-11, C-32). Formato Vitest.
 *
 * FocusDetector con doc/win fake; detectExtraMonitor con provider inyectado;
 * requestAndDetectExtraMonitor con mock de window.getScreenDetails (C-32 Task 5.4).
 */

import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { detectExtraMonitor, FocusDetector, requestAndDetectExtraMonitor } from "./contextDetectors";

class FakeTarget {
  handlers: Record<string, () => void> = {};
  addEventListener(type: string, fn: () => void): void {
    this.handlers[type] = fn;
  }
  removeEventListener(type: string): void {
    delete this.handlers[type];
  }
  fire(type: string): void {
    this.handlers[type]?.();
  }
}

describe("FocusDetector", () => {
  it("emite focus_lost al perder el foco de la ventana", () => {
    const win = new FakeTarget();
    const doc = Object.assign(new FakeTarget(), { visibilityState: "visible" as DocumentVisibilityState });
    const signals: boolean[] = [];
    const det = new FocusDetector((s) => signals.push(s.focus_lost!), {
      win: win as unknown as Window,
      doc: doc as unknown as Document,
    });
    det.start();
    win.fire("blur");
    expect(signals).toContain(true);
    win.fire("focus");
    expect(signals).toContain(false);
  });

  it("emite tab_changed cuando la pestana queda oculta", () => {
    const doc = Object.assign(new FakeTarget(), { visibilityState: "hidden" as DocumentVisibilityState });
    // C-25: `visibilitychange` con la pestaña oculta emite `tab_changed` (señal
    // propia), NO `focus_lost` (que es blur de ventana del SO). El test anterior
    // esperaba `focus_lost` y quedó desactualizado tras separar ambas señales.
    let tabChanged: boolean | undefined;
    const det = new FocusDetector((s) => {
      tabChanged = s.tab_changed;
    }, { doc: doc as unknown as Document });
    det.start();
    doc.fire("visibilitychange");
    expect(tabChanged).toBe(true);
  });
});

describe("detectExtraMonitor", () => {
  it("senala extra_monitor cuando hay mas de una pantalla", async () => {
    const provider = vi.fn().mockResolvedValue({ screens: [{}, {}] });
    const signal = await detectExtraMonitor(provider);
    expect(signal).toEqual({ extra_monitor: true });
  });

  it("no senala monitor adicional con una sola pantalla", async () => {
    const provider = vi.fn().mockResolvedValue({ screens: [{}] });
    const signal = await detectExtraMonitor(provider);
    expect(signal).toEqual({ extra_monitor: false });
  });

  it("devuelve null sin abortar cuando la API no esta disponible", async () => {
    expect(await detectExtraMonitor(undefined)).toBeNull();
  });

  it("devuelve null sin abortar si el permiso es denegado", async () => {
    const provider = vi.fn().mockRejectedValue(new Error("denied"));
    expect(await detectExtraMonitor(provider)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// C-32 Task 5.4: requestAndDetectExtraMonitor
// ---------------------------------------------------------------------------

describe("requestAndDetectExtraMonitor", () => {
  // El runner corre en entorno node (sin jsdom): `window` no existe como global.
  // Stubeamos un `window` fresco por test para poder definir/borrar getScreenDetails
  // sin contaminar otros tests. `unstubAllGlobals` lo limpia después.
  beforeEach(() => {
    vi.stubGlobal("window", {} as Window & typeof globalThis);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("devuelve unsupported cuando getScreenDetails no existe en window", async () => {
    // Asegurar que la propiedad no existe
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      delete (window as any).getScreenDetails;
    } catch {
      // JSDOM puede no permitir delete; definir como undefined
      Object.defineProperty(window, "getScreenDetails", {
        value: undefined,
        writable: true,
        configurable: true,
      });
    }
    const result = await requestAndDetectExtraMonitor();
    expect(result).toEqual({ status: "unsupported" });
  });

  it("devuelve denied cuando getScreenDetails lanza NotAllowedError", async () => {
    const notAllowed = new DOMException("Permission denied", "NotAllowedError");
    Object.defineProperty(window, "getScreenDetails", {
      value: vi.fn().mockRejectedValue(notAllowed),
      writable: true,
      configurable: true,
    });
    const result = await requestAndDetectExtraMonitor();
    expect(result).toEqual({ status: "denied" });
  });

  it("devuelve granted con extra_monitor false cuando hay una sola pantalla", async () => {
    Object.defineProperty(window, "getScreenDetails", {
      value: vi.fn().mockResolvedValue({ screens: [{}] }),
      writable: true,
      configurable: true,
    });
    const result = await requestAndDetectExtraMonitor();
    expect(result).toEqual({ status: "granted", extra_monitor: false });
  });

  it("devuelve granted con extra_monitor true cuando hay dos o mas pantallas", async () => {
    Object.defineProperty(window, "getScreenDetails", {
      value: vi.fn().mockResolvedValue({ screens: [{}, {}] }),
      writable: true,
      configurable: true,
    });
    const result = await requestAndDetectExtraMonitor();
    expect(result).toEqual({ status: "granted", extra_monitor: true });
  });
});
