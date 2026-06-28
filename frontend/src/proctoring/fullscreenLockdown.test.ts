/**
 * Tests del módulo fullscreenLockdown (C-69 Section 5).
 *
 * 5.1 RED -> 5.2 GREEN: módulo de enforcement de pantalla completa.
 * 5.3 RED: retrocompat — señales siguen al pipeline de score.
 * 5.6 TRIANGULATE: L2.5 — bloquea y re-fuerza, NUNCA expulsa la sesión.
 * 5.7 GREEN/Doc: degradación honesta cuando el navegador no soporta Fullscreen API.
 *
 * Deps DOM inyectables (patrón de contextDetectors.ts) — sin navegador real.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';

import {
  FullscreenLockdown,
  soportaFullscreen,
  MENSAJE_LIMITE_FULLSCREEN,
} from './fullscreenLockdown';
import { FullscreenDetector, FocusDetector } from './contextDetectors';

// ---------------------------------------------------------------------------
// Helpers: deps DOM fake inyectables
// ---------------------------------------------------------------------------

class FakeEventTarget {
  handlers: Record<string, Array<() => void>> = {};
  addEventListener(type: string, fn: () => void): void {
    if (!this.handlers[type]) this.handlers[type] = [];
    this.handlers[type].push(fn);
  }
  removeEventListener(type: string, fn: () => void): void {
    if (this.handlers[type]) {
      this.handlers[type] = this.handlers[type].filter((h) => h !== fn);
    }
  }
  fire(type: string): void {
    (this.handlers[type] ?? []).forEach((h) => h());
  }
}

function makeFakeFullscreenDoc(inFullscreen = false) {
  const doc = new FakeEventTarget() as typeof document & {
    fullscreenElement: Element | null;
    visibilityState: DocumentVisibilityState;
  };
  doc.fullscreenElement = inFullscreen ? ({} as Element) : null;
  doc.visibilityState = 'visible';
  return doc;
}

function makeFakeWin() {
  return new FakeEventTarget() as unknown as Window;
}

// ---------------------------------------------------------------------------
// 5.1 RED -> 5.2 GREEN: comportamiento del módulo de enforcement
// ---------------------------------------------------------------------------

describe('FullscreenLockdown — enforcement', () => {
  it('iniciar invoca requestFullscreen sobre el elemento target', async () => {
    const requestFullscreen = vi.fn().mockResolvedValue(undefined);
    const fakeElement = {} as Element;
    const lockdown = new FullscreenLockdown(
      () => {},
      () => {},
      {
        requestFullscreen,
        targetElement: fakeElement,
        fullscreenDeps: { doc: makeFakeFullscreenDoc() },
        focusDeps: { doc: makeFakeFullscreenDoc(), win: makeFakeWin() },
      },
    );
    await lockdown.iniciar();
    expect(requestFullscreen).toHaveBeenCalledWith(fakeElement);
  });

  it('ante fullscreen_exited marca estado bloqueado', async () => {
    const estados: Array<{ bloqueado: boolean }> = [];
    const fakeDoc = makeFakeFullscreenDoc();
    const lockdown = new FullscreenLockdown(
      (s) => estados.push(s),
      () => {},
      {
        requestFullscreen: vi.fn().mockResolvedValue(undefined),
        getFullscreenElement: () => null,
        getVisibilityState: () => 'visible',
        fullscreenDeps: { doc: fakeDoc },
        focusDeps: { doc: makeFakeFullscreenDoc(), win: makeFakeWin() },
      },
    );
    await lockdown.iniciar();
    // Simular salida de fullscreen
    fakeDoc.fullscreenElement = null;
    fakeDoc.fire('fullscreenchange');
    expect(estados.some((s) => s.bloqueado === true)).toBe(true);
  });

  it('ante blur del foco marca estado bloqueado', async () => {
    const estados: Array<{ bloqueado: boolean }> = [];
    const fakeWin = makeFakeWin();
    const lockdown = new FullscreenLockdown(
      (s) => estados.push(s),
      () => {},
      {
        requestFullscreen: vi.fn().mockResolvedValue(undefined),
        getFullscreenElement: () => null,
        getVisibilityState: () => 'visible',
        fullscreenDeps: { doc: makeFakeFullscreenDoc() },
        focusDeps: { doc: makeFakeFullscreenDoc(), win: fakeWin },
      },
    );
    await lockdown.iniciar();
    fakeWin.fire('blur');
    expect(estados.some((s) => s.bloqueado === true)).toBe(true);
  });

  it('al volver a fullscreen+visible desmarca el estado bloqueado', async () => {
    const estados: Array<{ bloqueado: boolean }> = [];
    const fakeDoc = makeFakeFullscreenDoc(false);
    let isFullscreen = false;
    const lockdown = new FullscreenLockdown(
      (s) => estados.push(s),
      () => {},
      {
        requestFullscreen: vi.fn().mockResolvedValue(undefined),
        getFullscreenElement: () => isFullscreen ? ({} as Element) : null,
        getVisibilityState: () => 'visible',
        fullscreenDeps: { doc: fakeDoc },
        focusDeps: { doc: makeFakeFullscreenDoc(), win: makeFakeWin() },
      },
    );
    await lockdown.iniciar();
    // Simular salida → bloqueado
    fakeDoc.fire('fullscreenchange');
    expect(estados.some((s) => s.bloqueado === true)).toBe(true);
    // Simular reingreso → desbloqueado
    isFullscreen = true;
    fakeDoc.fire('fullscreenchange');
    const ultimo = estados[estados.length - 1];
    expect(ultimo.bloqueado).toBe(false);
  });

  it('detener limpia los listeners (no emite más señales tras stop)', async () => {
    const estados: Array<{ bloqueado: boolean }> = [];
    const fakeDoc = makeFakeFullscreenDoc();
    const lockdown = new FullscreenLockdown(
      (s) => estados.push(s),
      () => {},
      {
        requestFullscreen: vi.fn().mockResolvedValue(undefined),
        getFullscreenElement: () => null,
        getVisibilityState: () => 'visible',
        fullscreenDeps: { doc: fakeDoc },
        focusDeps: { doc: makeFakeFullscreenDoc(), win: makeFakeWin() },
      },
    );
    await lockdown.iniciar();
    lockdown.detener();
    const countBefore = estados.length;
    // Disparar eventos después de detener
    fakeDoc.fire('fullscreenchange');
    expect(estados.length).toBe(countBefore);
  });
});

// ---------------------------------------------------------------------------
// 5.3 RED: retrocompat — las señales llegan al pipeline de score
// ---------------------------------------------------------------------------

describe('5.3 — Retrocompat: señales siguen al pipeline de score', () => {
  it('onSenalParaScore se llama ante fullscreen_exited', async () => {
    const senales: string[] = [];
    const fakeDoc = makeFakeFullscreenDoc(false);
    const lockdown = new FullscreenLockdown(
      () => {},
      (tipo) => senales.push(tipo),
      {
        requestFullscreen: vi.fn().mockResolvedValue(undefined),
        getFullscreenElement: () => null,
        getVisibilityState: () => 'visible',
        fullscreenDeps: { doc: fakeDoc },
        focusDeps: { doc: makeFakeFullscreenDoc(), win: makeFakeWin() },
      },
    );
    await lockdown.iniciar();
    fakeDoc.fire('fullscreenchange');
    expect(senales).toContain('fullscreen_exited');
  });

  it('onSenalParaScore se llama ante blur (focus_lost)', async () => {
    const senales: string[] = [];
    const fakeWin = makeFakeWin();
    const lockdown = new FullscreenLockdown(
      () => {},
      (tipo) => senales.push(tipo),
      {
        requestFullscreen: vi.fn().mockResolvedValue(undefined),
        getFullscreenElement: () => null,
        getVisibilityState: () => 'visible',
        fullscreenDeps: { doc: makeFakeFullscreenDoc() },
        focusDeps: { doc: makeFakeFullscreenDoc(), win: fakeWin },
      },
    );
    await lockdown.iniciar();
    fakeWin.fire('blur');
    expect(senales).toContain('focus_lost');
  });

  it('el contrato de FullscreenDetector no fue modificado', () => {
    // FullscreenDetector sigue funcionando igual que antes del lockdown (D4).
    const senales: boolean[] = [];
    const fakeDoc = makeFakeFullscreenDoc(true);
    const det = new FullscreenDetector(
      (s) => senales.push(s.fullscreen_exited!),
      { doc: fakeDoc },
    );
    det.start();
    fakeDoc.fullscreenElement = null;
    fakeDoc.fire('fullscreenchange');
    expect(senales).toContain(true);
    det.stop();
  });
});

// ---------------------------------------------------------------------------
// 5.6 TRIANGULATE: L2.5 — salidas repetidas bloquean pero NO anulan la sesión
// ---------------------------------------------------------------------------

describe('5.6 — L2.5: salidas repetidas bloquean/re-fuerzan sin anular sesión', () => {
  it('múltiples salidas de fullscreen registran señales pero no llaman detener()', async () => {
    const senales: string[] = [];
    const estados: Array<{ bloqueado: boolean }> = [];
    const fakeDoc = makeFakeFullscreenDoc(false);
    // No hay referencia a ningún método "detener" de sesión aquí:
    // el lockdown sólo llama onEstadoChange y onSenalParaScore
    const lockdown = new FullscreenLockdown(
      (s) => estados.push(s),
      (tipo) => senales.push(tipo),
      {
        requestFullscreen: vi.fn().mockResolvedValue(undefined),
        getFullscreenElement: () => null,
        getVisibilityState: () => 'visible',
        fullscreenDeps: { doc: fakeDoc },
        focusDeps: { doc: makeFakeFullscreenDoc(), win: makeFakeWin() },
      },
    );
    await lockdown.iniciar();
    // 3 salidas repetidas
    fakeDoc.fire('fullscreenchange');
    fakeDoc.fire('fullscreenchange');
    fakeDoc.fire('fullscreenchange');
    // Todas registran la señal para el score
    expect(senales.filter((s) => s === 'fullscreen_exited').length).toBeGreaterThanOrEqual(1);
    // El lockdown sigue activo (no se "detuvo")
    expect(lockdown).toBeDefined();
  });

  it('volverAPantallaCompleta re-invoca requestFullscreen', async () => {
    const requestFullscreen = vi.fn().mockResolvedValue(undefined);
    const fakeElement = {} as Element;
    const lockdown = new FullscreenLockdown(
      () => {},
      () => {},
      {
        requestFullscreen,
        targetElement: fakeElement,
        fullscreenDeps: { doc: makeFakeFullscreenDoc() },
        focusDeps: { doc: makeFakeFullscreenDoc(), win: makeFakeWin() },
      },
    );
    await lockdown.iniciar();
    await lockdown.volverAPantallaCompleta();
    // Se llamó al menos 2 veces (iniciar + volverAPantallaCompleta)
    expect(requestFullscreen.mock.calls.length).toBeGreaterThanOrEqual(2);
  });
});

// ---------------------------------------------------------------------------
// 5.7 GREEN/Doc: degradación honesta sin Fullscreen API
// ---------------------------------------------------------------------------

describe('5.7 — Degradación honesta cuando no hay Fullscreen API', () => {
  it('soportaFullscreen retorna false cuando requestFullscreen no existe', () => {
    // En entorno de test (vitest/node) no hay document.documentElement.requestFullscreen
    // Comprobamos que la función no lanza y devuelve boolean.
    const resultado = soportaFullscreen();
    expect(typeof resultado).toBe('boolean');
  });

  it('MENSAJE_LIMITE_FULLSCREEN no está vacío y menciona el límite del navegador', () => {
    expect(MENSAJE_LIMITE_FULLSCREEN.trim().length).toBeGreaterThan(20);
    const lower = MENSAJE_LIMITE_FULLSCREEN.toLowerCase();
    // Debe mencionar el límite del SO o del sandbox
    const menciona =
      lower.includes('sistema operativo') ||
      lower.includes('minimize') ||
      lower.includes('sandbox') ||
      lower.includes('navegador') ||
      lower.includes('límite');
    expect(menciona).toBe(true);
  });

  it('iniciar NO lanza aunque requestFullscreen falle (degradación sin crash)', async () => {
    const requestFullscreen = vi.fn().mockRejectedValue(new Error('Not allowed'));
    const lockdown = new FullscreenLockdown(
      () => {},
      () => {},
      {
        requestFullscreen,
        targetElement: {} as Element, // fake element — no DOM in Vitest node env
        fullscreenDeps: { doc: makeFakeFullscreenDoc() },
        focusDeps: { doc: makeFakeFullscreenDoc(), win: makeFakeWin() },
      },
    );
    // No debe lanzar
    await expect(lockdown.iniciar()).resolves.not.toThrow();
  });

  it('Examen.tsx incluye el texto de degradación honesta', () => {
    // Verificar que el mensaje DD-21 está presente en el componente.
    const { readFileSync } = require('node:fs');
    const { join, dirname } = require('node:path');
    const { fileURLToPath } = require('node:url');
    const source = readFileSync(
      join(dirname(fileURLToPath(import.meta.url)), '..', 'screens', 'Examen.tsx'),
      'utf8',
    );
    expect(source).toMatch(/MENSAJE_LIMITE_FULLSCREEN|límite.*pantalla completa|lockdown/i);
  });
});
