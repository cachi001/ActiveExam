/**
 * Cadencia adaptativa del poller de pausas (c-78).
 *
 * ## El problema, medido
 *
 * `PausaAlumno` preguntaba cada 3,5 s durante TODO el examen — dos horas — por
 * algo que casi nunca pasa. Con 100 alumnos son **~29 req/s permanentes** sobre
 * un techo medido de 80 req/s, y cuando el techo satura no se pone lento el chat:
 * se pone lento **todo**, incluido el autoguardado de las respuestas (p50 de
 * 280 ms a 875 ms en la medición del 25/8/2026).
 *
 * ## Por qué se puede ir lento sin empeorar la espera
 *
 * La pausa **siempre la inicia el alumno** (verificado: `solicitar_pausa` es el
 * único endpoint de creación; el tutor solo aprueba o rechaza). O sea que
 * mientras el alumno no pidió nada, **no puede llegarle nada que no haya pedido**
 * — preguntar seguido no le ahorra un solo segundo.
 *
 * En cuanto toca el botón, el estado local pasa a `solicitada` y el poller vuelve
 * a 3,5 s en ese mismo instante. La espera percibida no cambia.
 *
 * OJO — esto NO vale para el chat: ahí el que inicia es el TUTOR (el alumno no
 * puede abrir el hilo, solo responder), así que bajarle la frecuencia le llegaría
 * el mensaje 20 s tarde. El chat se queda rápido.
 */

import { describe, expect, it } from 'vitest';

import {
  POLL_PAUSA_ACTIVO_MS,
  POLL_PAUSA_INACTIVO_MS,
  intervaloDePolling,
} from './pausaCadencia';

describe('intervaloDePolling', () => {
  it('sin ninguna pausa va LENTO: no hay nada que esperar', () => {
    expect(intervaloDePolling(null)).toBe(POLL_PAUSA_INACTIVO_MS);
  });

  it('con una pausa SOLICITADA va rápido: el alumno está esperando la respuesta', () => {
    expect(intervaloDePolling('solicitada')).toBe(POLL_PAUSA_ACTIVO_MS);
  });

  it('con la pausa APROBADA va rápido: hay que ver cuándo se cierra sola', () => {
    // La pausa tiene tope de duración y el backend la reanuda al vencer. Si acá
    // fuera lento, el alumno seguiría viendo "en pausa" después de que el
    // servidor ya lo devolvió al examen.
    expect(intervaloDePolling('aprobada')).toBe(POLL_PAUSA_ACTIVO_MS);
  });

  it('RECHAZADA vuelve a lento: ya se resolvió, no hay nada en vuelo', () => {
    expect(intervaloDePolling('rechazada')).toBe(POLL_PAUSA_INACTIVO_MS);
  });

  it('FINALIZADA vuelve a lento: el alumno ya volvió al examen', () => {
    expect(intervaloDePolling('finalizada')).toBe(POLL_PAUSA_INACTIVO_MS);
  });

  it('un estado desconocido va RÁPIDO (falla del lado seguro)', () => {
    // Si mañana aparece un estado nuevo, el error barato es preguntar de más;
    // el caro es dejar al alumno esperando sin enterarse de nada.
    expect(intervaloDePolling('un_estado_que_no_existe')).toBe(POLL_PAUSA_ACTIVO_MS);
  });

  it('el intervalo lento ahorra de verdad, pero no tanto como para no enterarse', () => {
    // Fija el orden de magnitud: si alguien lo pone en 3,6 s el cambio no sirve,
    // y si lo pone en 2 minutos el alumno queda desinformado demasiado tiempo.
    expect(POLL_PAUSA_INACTIVO_MS).toBeGreaterThanOrEqual(4 * POLL_PAUSA_ACTIVO_MS);
    expect(POLL_PAUSA_INACTIVO_MS).toBeLessThanOrEqual(30_000);
  });
});
