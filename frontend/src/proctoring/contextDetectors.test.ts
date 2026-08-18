/**
 * Tests de los detectores de contexto del navegador (C-11, C-32). Formato Vitest.
 *
 * FocusDetector con doc/win fake; detectExtraMonitor con provider inyectado;
 * requestAndDetectExtraMonitor con mock de window.getScreenDetails (C-32 Task 5.4).
 */

import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { ClipboardDetector, detectExtraMonitor, FocusDetector, requestAndDetectExtraMonitor } from "./contextDetectors";

class FakeTarget {
  handlers: Record<string, (arg?: unknown) => void> = {};
  addEventListener(type: string, fn: (arg?: unknown) => void): void {
    this.handlers[type] = fn;
  }
  removeEventListener(type: string): void {
    delete this.handlers[type];
  }
  fire(type: string, arg?: unknown): void {
    this.handlers[type]?.(arg);
  }
}

/** SubtleCrypto fake determinista: hashea sumando los code points del texto (NO
 * es SHA-256 real — no importa para el test, solo que sea funcion pura del input). */
function fakeSubtle(): SubtleCrypto {
  return {
    digest: async (_alg: unknown, data: BufferSource) => {
      const bytes = data instanceof Uint8Array ? data : new Uint8Array(data as ArrayBuffer);
      const out = new Uint8Array(32);
      bytes.forEach((b, i) => { out[i % 32] ^= b; });
      return out.buffer;
    },
  } as unknown as SubtleCrypto;
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

// ---------------------------------------------------------------------------
// C-76 (15.2/15.6): ClipboardDetector — hash del contenido pegado, sin persistir
// el contenido en si.
// ---------------------------------------------------------------------------

describe("ClipboardDetector", () => {
  it("emite copy sin clipboard_sha256", () => {
    const doc = new FakeTarget();
    const signals: Array<ReturnType<typeof Object>> = [];
    const det = new ClipboardDetector((s) => signals.push(s), {
      doc: doc as unknown as Document,
      subtle: fakeSubtle(),
    });
    det.start();
    doc.fire("copy");
    expect(signals).toEqual([{ clipboard_action: "copy" }]);
  });

  it("emite paste con clipboard_sha256 cuando el evento expone texto plano", async () => {
    const doc = new FakeTarget();
    const signals: Array<{ clipboard_action?: string; clipboard_sha256?: string }> = [];
    const det = new ClipboardDetector((s) => signals.push(s), {
      doc: doc as unknown as Document,
      subtle: fakeSubtle(),
    });
    det.start();
    const fakeEvent = { clipboardData: { getData: (t: string) => (t === "text/plain" ? "hola mundo" : "") } };
    doc.fire("paste", fakeEvent);
    // El hash se calcula async (promesa de SubtleCrypto.digest) — esperar el microtask.
    await Promise.resolve();
    await Promise.resolve();
    expect(signals).toHaveLength(1);
    expect(signals[0].clipboard_action).toBe("paste");
    expect(signals[0].clipboard_sha256).toBeTruthy();
    expect(typeof signals[0].clipboard_sha256).toBe("string");
  });

  it("hashes distintos para textos distintos (no es un valor fijo)", async () => {
    const doc = new FakeTarget();
    const hashes: string[] = [];
    const det = new ClipboardDetector((s) => {
      if (s.clipboard_sha256) hashes.push(s.clipboard_sha256);
    }, { doc: doc as unknown as Document, subtle: fakeSubtle() });
    det.start();
    doc.fire("paste", { clipboardData: { getData: () => "texto A" } });
    await Promise.resolve(); await Promise.resolve();
    doc.fire("paste", { clipboardData: { getData: () => "texto B, mucho mas largo y distinto" } });
    await Promise.resolve(); await Promise.resolve();
    expect(hashes).toHaveLength(2);
    expect(hashes[0]).not.toBe(hashes[1]);
  });

  it("degrada en silencio (sin hash) cuando no hay texto plano en el evento", async () => {
    const doc = new FakeTarget();
    const signals: Array<{ clipboard_action?: string; clipboard_sha256?: string }> = [];
    const det = new ClipboardDetector((s) => signals.push(s), {
      doc: doc as unknown as Document,
      subtle: fakeSubtle(),
    });
    det.start();
    // Paste de una imagen: sin text/plain.
    doc.fire("paste", { clipboardData: { getData: () => "" } });
    expect(signals).toEqual([{ clipboard_action: "paste" }]);
  });

  it("degrada en silencio cuando no hay SubtleCrypto disponible", () => {
    // deps.subtle: undefined cae al `crypto.subtle` global por defecto (igual que
    // `doc`); para probar la degradacion hay que quitar tambien el global.
    vi.stubGlobal("crypto", {} as Crypto);
    try {
      const doc = new FakeTarget();
      const signals: Array<{ clipboard_action?: string; clipboard_sha256?: string }> = [];
      const det = new ClipboardDetector((s) => signals.push(s), {
        doc: doc as unknown as Document,
      });
      det.start();
      doc.fire("paste", { clipboardData: { getData: () => "contenido" } });
      expect(signals).toEqual([{ clipboard_action: "paste" }]);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
