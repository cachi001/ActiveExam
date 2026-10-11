/**
 * Tests de CalibracionCuatroPuntos — secuenciar las 4 esquinas y armar el
 * rango final. `capturarBaselineGaze` se mockea entero: su propia lógica de
 * muestreo ya está cubierta en `useExamProctoring.calibracionGaze.test.ts`;
 * acá interesa la SECUENCIA (orden, qué pasa si falta una esquina, cancelar,
 * pantalla completa), no el detalle de cómo se promedia cada punto.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createRef } from 'react';
import { act, cleanup, fireEvent, render } from '@testing-library/react';

const mockCapturar = vi.fn();
vi.mock('./useExamProctoring', () => ({
  capturarBaselineGaze: (...args: unknown[]) => mockCapturar(...args),
}));

import { CalibracionCuatroPuntos } from './CalibracionCuatroPuntos';
import type { VisionEngine } from '../vision/VisionEngine';

function fakeVideoRef() {
  return createRef<HTMLVideoElement>();
}

const ENGINE_FAKE = {} as VisionEngine;

/** Avanza las 4 esquinas paso a paso: un `act` por esquina para que React
 *  procese el `setIndice` (que dispara el siguiente `useEffect`) ANTES de
 *  avanzar el timer de la esquina que sigue. `runAllTimersAsync` de una sola
 *  vez no alcanza a intercalar los re-renders entre cada mock resuelto. */
async function correrTodo(pasos = 4) {
  for (let i = 0; i < pasos; i += 1) {
    // eslint-disable-next-line no-await-in-loop
    await act(async () => {
      await vi.advanceTimersByTimeAsync(700);
    });
  }
}

describe('CalibracionCuatroPuntos', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    Element.prototype.requestFullscreen = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(document, 'exitFullscreen', {
      value: vi.fn().mockResolvedValue(undefined),
      configurable: true,
    });
    // jsdom no simula el Fullscreen API real: se fuerza a "en fullscreen" para
    // poder probar la salida (exitFullscreen) sin un navegador de verdad.
    Object.defineProperty(document, 'fullscreenElement', {
      value: document.body,
      configurable: true,
    });
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.restoreAllMocks();
    mockCapturar.mockReset();
  });

  it('mide las 4 esquinas EN ORDEN y arma centro + rango a partir de las 4', async () => {
    mockCapturar
      .mockResolvedValueOnce({ x: -0.2, y: -0.5 }) // arriba_izquierda
      .mockResolvedValueOnce({ x: 0.2, y: -0.5 }) // arriba_derecha
      .mockResolvedValueOnce({ x: 0.2, y: 0.5 }) // abajo_derecha
      .mockResolvedValueOnce({ x: -0.2, y: 0.5 }); // abajo_izquierda
    const onCompleto = vi.fn();
    render(
      <CalibracionCuatroPuntos videoRef={fakeVideoRef()} engine={ENGINE_FAKE} onCompleto={onCompleto} />,
    );

    await correrTodo();

    expect(mockCapturar).toHaveBeenCalledTimes(4);
    expect(onCompleto).toHaveBeenCalledTimes(1);
    const rango = onCompleto.mock.calls[0][0];
    expect(rango).not.toBeNull();
    expect(rango.centro).toEqual({ x: 0, y: 0 });
    expect(rango.rangoX).toEqual([-0.2, 0.2]);
    expect(rango.rangoY).toEqual([-0.5, 0.5]);
  });

  it('si una esquina no midió nada, onCompleto recibe null (nunca un rectángulo a medias)', async () => {
    mockCapturar
      .mockResolvedValueOnce({ x: -0.2, y: -0.5 })
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce({ x: 0.2, y: 0.5 })
      .mockResolvedValueOnce({ x: -0.2, y: 0.5 });
    const onCompleto = vi.fn();
    render(
      <CalibracionCuatroPuntos videoRef={fakeVideoRef()} engine={ENGINE_FAKE} onCompleto={onCompleto} />,
    );

    await correrTodo();

    expect(onCompleto).toHaveBeenCalledWith(null);
  });

  it('NO pide pantalla completa por su cuenta: eso lo hace el click que lo monta', async () => {
    // Pedirla acá, en un efecto que corre DESPUÉS de montar, ya no cuenta como
    // gesto del usuario y el navegador la rechaza (confirmado en Chromium real:
    // "API can only be initiated by a user gesture"). Por eso el pedido vive en
    // el onClick síncrono de quien lo monta (`CalibracionPaso`/`CalibracionPanel`).
    mockCapturar.mockResolvedValue({ x: 0, y: 0 });
    render(
      <CalibracionCuatroPuntos videoRef={fakeVideoRef()} engine={ENGINE_FAKE} onCompleto={vi.fn()} />,
    );
    expect(Element.prototype.requestFullscreen).not.toHaveBeenCalled();
    await correrTodo();
  });

  it('si sale de pantalla completa a mitad de camino, la FUERZA de vuelta en vez de abortar', async () => {
    // Mismo patrón que fullscreenLockdown.ts (examen real): re-intenta en vez
    // de rendirse. onCompleto NO se llama con null solo por haber salido.
    mockCapturar.mockResolvedValue({ x: 0, y: 0 });
    const onCompleto = vi.fn();
    render(
      <CalibracionCuatroPuntos videoRef={fakeVideoRef()} engine={ENGINE_FAKE} onCompleto={onCompleto} />,
    );

    Object.defineProperty(document, 'fullscreenElement', { value: null, configurable: true });
    document.dispatchEvent(new Event('fullscreenchange'));

    expect(Element.prototype.requestFullscreen).toHaveBeenCalled();
    expect(onCompleto).not.toHaveBeenCalled();

    Object.defineProperty(document, 'fullscreenElement', { value: document.body, configurable: true });
    await correrTodo();
  });

  it('cancelar corta la medición: no arranca ninguna captura más y llama a onCancelar', async () => {
    mockCapturar.mockImplementation(() => new Promise(() => {})); // nunca resuelve
    const onCancelar = vi.fn();
    const onCompleto = vi.fn();
    const { getByText } = render(
      <CalibracionCuatroPuntos
        videoRef={fakeVideoRef()}
        engine={ENGINE_FAKE}
        onCompleto={onCompleto}
        onCancelar={onCancelar}
      />,
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(700); // deja arrancar la primera captura
    });
    fireEvent.click(getByText('Cancelar'));
    expect(onCancelar).toHaveBeenCalledTimes(1);
    expect(onCompleto).not.toHaveBeenCalled();
    expect(document.exitFullscreen).toHaveBeenCalled();
  });
});
