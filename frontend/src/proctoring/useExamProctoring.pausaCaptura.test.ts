/**
 * Test de la cadencia de captura_pausa (C-76 bloque 5, D6/Q3 follow-up).
 *
 * El backend (`chat_pausa_service.finalizar_pausa`) emite `pausa_sin_captura`
 * (BASELINE, señal — nunca veredicto, L2.5) si al cerrar una ventana de pausa
 * APROBADA no hubo ningún evento `captura_pausa` posteado por el cliente. Este
 * test cubre la CONTRAPARTE del cliente: `crearControladorCapturaPausa`, la
 * función pura que arranca/detiene el heartbeat de capturas mientras la pausa
 * está `aprobada`.
 *
 * Se testea la función pura extraída (no el hook completo) — mismo criterio
 * que `useExamProctoring.idempotencia.test.ts` para `obtenerOCrearSesion`:
 * montar el hook completo requeriría mockear MediaPipe/video/IndexedDB, que
 * no aporta nada a la cobertura de ESTA lógica (arrancar/detener un timer).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { crearControladorCapturaPausa, PAUSA_CAPTURA_INTERVAL_MS } from './useExamProctoring';

describe('crearControladorCapturaPausa — cadencia de captura durante pausa aprobada', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('setActiva(true) captura INMEDIATAMENTE, sin esperar el primer tick', () => {
    const capturar = vi.fn();
    const ctrl = crearControladorCapturaPausa({ capturar });

    ctrl.setActiva(true);

    expect(capturar).toHaveBeenCalledTimes(1);
  });

  it('mientras la pausa sigue aprobada, captura de nuevo en cada tick del intervalo (TRIANGULACIÓN: 2+ ticks)', () => {
    const capturar = vi.fn();
    const ctrl = crearControladorCapturaPausa({ capturar });

    ctrl.setActiva(true);
    expect(capturar).toHaveBeenCalledTimes(1); // captura inicial

    vi.advanceTimersByTime(PAUSA_CAPTURA_INTERVAL_MS);
    expect(capturar).toHaveBeenCalledTimes(2);

    vi.advanceTimersByTime(PAUSA_CAPTURA_INTERVAL_MS);
    expect(capturar).toHaveBeenCalledTimes(3);
  });

  it('setActiva(false) detiene la cadencia: no captura más allá del momento en que se resolvió/finalizó la pausa', () => {
    const capturar = vi.fn();
    const ctrl = crearControladorCapturaPausa({ capturar });

    ctrl.setActiva(true);
    vi.advanceTimersByTime(PAUSA_CAPTURA_INTERVAL_MS);
    expect(capturar).toHaveBeenCalledTimes(2);

    ctrl.setActiva(false);
    vi.advanceTimersByTime(PAUSA_CAPTURA_INTERVAL_MS * 3);

    // Sin nuevas capturas: la pausa ya no está aprobada (rechazada/finalizada/sin pausa).
    expect(capturar).toHaveBeenCalledTimes(2);
  });

  it('nunca hubo pausa aprobada → nunca captura (no dispara nada fuera de la ventana)', () => {
    const capturar = vi.fn();
    const ctrl = crearControladorCapturaPausa({ capturar });

    vi.advanceTimersByTime(PAUSA_CAPTURA_INTERVAL_MS * 5);

    expect(capturar).not.toHaveBeenCalled();
  });

  it('setActiva(true) es idempotente: llamarlo dos veces seguidas no duplica el timer', () => {
    const capturar = vi.fn();
    const ctrl = crearControladorCapturaPausa({ capturar });

    ctrl.setActiva(true);
    ctrl.setActiva(true); // segunda llamada — no debe arrancar un segundo intervalo
    expect(capturar).toHaveBeenCalledTimes(1); // solo la captura inicial de la primera llamada

    vi.advanceTimersByTime(PAUSA_CAPTURA_INTERVAL_MS);
    // Si hubiera dos timers corriendo en paralelo, este tick dispararía 2 capturas más (total 3).
    expect(capturar).toHaveBeenCalledTimes(2);
  });

  it('detener() corta el timer incondicionalmente (cleanup de desmontaje)', () => {
    const capturar = vi.fn();
    const ctrl = crearControladorCapturaPausa({ capturar });

    ctrl.setActiva(true);
    ctrl.detener();
    vi.advanceTimersByTime(PAUSA_CAPTURA_INTERVAL_MS * 2);

    expect(capturar).toHaveBeenCalledTimes(1); // solo la captura inicial, nada más
  });
});
