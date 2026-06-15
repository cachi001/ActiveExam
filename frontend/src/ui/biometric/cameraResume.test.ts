/**
 * Tests para decideCameraResumeActions (C-67 — fix: cámara congelada al
 * volver de una pestaña oculta / app en background).
 *
 * TDD: ciclo RED → GREEN → TRIANGULATE.
 *
 * Especificación: cuando la página vuelve a ser visible, hay que decidir qué
 * acciones tomar para "descongelar" la cámara:
 *  - Si el track de video murió (típico en mobile al salir de la pestaña/app),
 *    re-adquirir la cámara desde cero ('reacquire'). Esta acción es total: el
 *    re-adquirir ya reanuda el <video> y reinicia el loop, así que NO se combina
 *    con 'play' ni 'restart-loop'.
 *  - Si el track sigue vivo pero el <video> quedó pausado (frame congelado),
 *    reanudarlo ('play').
 *  - Si estamos capturando pero el loop RAF se murió, reiniciarlo ('restart-loop').
 *  - Si la página NO está visible, no hacer nada (esperar a que vuelva).
 */

import { describe, expect, it } from 'vitest';
import { decideCameraResumeActions } from './cameraResume';
import type { CameraResumeState } from './cameraResume';

// Estado base: visible, todo sano (cámara viva, video reproduciendo, loop activo
// mientras se captura). Cada test sobreescribe lo que necesita.
const base: CameraResumeState = {
  visible: true,
  trackEnded: false,
  videoPaused: false,
  loopActive: true,
  capturing: true,
};

describe('decideCameraResumeActions', () => {
  // ── No visible → no hacer nada ──────────────────────────────────────────
  it('página NO visible → [] (esperar a que vuelva)', () => {
    expect(decideCameraResumeActions({ ...base, visible: false })).toEqual([]);
  });

  it('no visible aunque el track haya muerto → [] (no re-adquirir en background)', () => {
    expect(
      decideCameraResumeActions({ ...base, visible: false, trackEnded: true }),
    ).toEqual([]);
  });

  // ── Track muerto → re-adquirir (acción total) ───────────────────────────
  it('visible + track muerto → ["reacquire"]', () => {
    expect(decideCameraResumeActions({ ...base, trackEnded: true })).toEqual([
      'reacquire',
    ]);
  });

  it('track muerto tiene prioridad: aunque el video esté pausado y el loop caído → solo ["reacquire"]', () => {
    expect(
      decideCameraResumeActions({
        ...base,
        trackEnded: true,
        videoPaused: true,
        loopActive: false,
      }),
    ).toEqual(['reacquire']);
  });

  // ── Track vivo pero video pausado → reanudar ────────────────────────────
  it('visible + track vivo + video pausado + capturando + loop caído → ["play","restart-loop"]', () => {
    expect(
      decideCameraResumeActions({
        ...base,
        videoPaused: true,
        loopActive: false,
      }),
    ).toEqual(['play', 'restart-loop']);
  });

  it('visible + video pausado pero NO capturando → solo ["play"] (no reiniciar loop)', () => {
    expect(
      decideCameraResumeActions({
        ...base,
        videoPaused: true,
        loopActive: false,
        capturing: false,
      }),
    ).toEqual(['play']);
  });

  // ── Loop caído mientras se captura, video OK → reiniciar loop ────────────
  it('visible + video reproduciendo + capturando + loop caído → ["restart-loop"]', () => {
    expect(
      decideCameraResumeActions({ ...base, loopActive: false }),
    ).toEqual(['restart-loop']);
  });

  // ── Todo sano → nada que hacer ──────────────────────────────────────────
  it('visible + cámara viva + video reproduciendo + loop activo → []', () => {
    expect(decideCameraResumeActions(base)).toEqual([]);
  });

  it('visible + no capturando + todo reproduciendo → [] (loop apagado es esperado fuera de captura)', () => {
    expect(
      decideCameraResumeActions({ ...base, capturing: false, loopActive: false }),
    ).toEqual([]);
  });
});
