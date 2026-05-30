/**
 * Tests de los detectores de contexto del navegador (C-11). Formato Vitest.
 *
 * FocusDetector con doc/win fake; detectExtraMonitor con provider inyectado.
 */

import { describe, expect, it, vi } from "vitest";

import { detectExtraMonitor, FocusDetector } from "./contextDetectors";

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

  it("emite focus_lost cuando la pestana queda oculta", () => {
    const doc = Object.assign(new FakeTarget(), { visibilityState: "hidden" as DocumentVisibilityState });
    let lost = false;
    const det = new FocusDetector((s) => {
      lost = s.focus_lost!;
    }, { doc: doc as unknown as Document });
    det.start();
    doc.fire("visibilitychange");
    expect(lost).toBe(true);
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
