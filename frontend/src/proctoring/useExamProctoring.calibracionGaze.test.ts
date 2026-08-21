/**
 * Tests de capturarBaselineGaze — calibracion de mirada al inicio del examen
 * (pentest 2026-08-21, miedo del usuario: "si tengo la camara descentrada,
 * mirar bien a la pantalla me puede detectar mirada desviada"). Logica pura de
 * cliente (sin red, sin DB) con un VisionEngine fake — no aplica la regla de
 * "tests contra Postgres real", que es para el backend.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { RefObject } from 'react';
import type { VisionEngine } from '../vision/VisionEngine';
import { capturarBaselineGaze } from './useExamProctoring';

function fakeVideoRef(readyState = 2): RefObject<HTMLVideoElement> {
  return { current: { readyState } as HTMLVideoElement };
}

function fakeEngineConGaze(gazes: ({ x: number; y: number } | undefined)[]): VisionEngine {
  let i = 0;
  return {
    detectFaces: vi.fn().mockImplementation(async () => ({ face_count: 1 })),
    detectFaceMesh: vi.fn().mockImplementation(async () => {
      const gaze = gazes[Math.min(i, gazes.length - 1)];
      i += 1;
      return { gaze };
    }),
  } as unknown as VisionEngine;
}

describe('capturarBaselineGaze', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    globalThis.createImageBitmap = vi
      .fn()
      .mockResolvedValue({ close: vi.fn() }) as unknown as typeof createImageBitmap;
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('promedia las muestras de gaze capturadas durante la ventana de calibracion', async () => {
    const engine = fakeEngineConGaze([
      { x: 0.28, y: 0.02 },
      { x: 0.3, y: 0 },
      { x: 0.32, y: -0.02 },
    ]);
    const promesa = capturarBaselineGaze(fakeVideoRef(), engine, 300, 100, () => false);
    await vi.runAllTimersAsync();
    const baseline = await promesa;
    expect(baseline).not.toBeNull();
    expect(baseline!.x).toBeCloseTo(0.3, 5);
    expect(baseline!.y).toBeCloseTo(0, 5);
  });

  it('devuelve null si nunca se detecto un rostro (sin muestras validas)', async () => {
    const engine = {
      detectFaces: vi.fn().mockResolvedValue({ face_count: 0 }),
      detectFaceMesh: vi.fn(),
    } as unknown as VisionEngine;
    const promesa = capturarBaselineGaze(fakeVideoRef(), engine, 300, 100, () => false);
    await vi.runAllTimersAsync();
    expect(await promesa).toBeNull();
    expect(engine.detectFaceMesh).not.toHaveBeenCalled();
  });

  it('devuelve null si el video nunca esta listo (readyState bajo, camara no cargo)', async () => {
    const engine = fakeEngineConGaze([{ x: 0.1, y: 0.1 }]);
    const promesa = capturarBaselineGaze(fakeVideoRef(1), engine, 300, 100, () => false);
    await vi.runAllTimersAsync();
    expect(await promesa).toBeNull();
    expect(engine.detectFaces).not.toHaveBeenCalled();
  });

  it('no ejecuta ninguna captura si ya esta cancelado desde el arranque (unmount inmediato)', async () => {
    const engine = fakeEngineConGaze([{ x: 0.5, y: 0.5 }]);
    const baseline = await capturarBaselineGaze(fakeVideoRef(), engine, 1000, 100, () => true);
    expect(baseline).toBeNull();
    expect(engine.detectFaces).not.toHaveBeenCalled();
  });
});
