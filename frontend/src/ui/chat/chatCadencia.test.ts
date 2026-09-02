/**
 * Cadencia adaptativa del poller del chat.
 *
 * Lo que estos tests sostienen: mientras nadie escribió, el chat NO puede estar
 * preguntando cada 3,5 s, porque con 100 alumnos eso se lleva más de un tercio del
 * techo de requests y termina frenando el autoguardado del examen de todos.
 */
import { describe, expect, it } from 'vitest';
import {
  POLL_CHAT_ACTIVO_MS,
  POLL_CHAT_INACTIVO_MS,
  VENTANA_CONVERSACION_VIVA_MS,
  intervaloDeChat,
} from './chatCadencia';

const AHORA = new Date('2026-09-05T14:00:00.000Z').getTime();

function haceMs(ms: number): string {
  return new Date(AHORA - ms).toISOString();
}

describe('intervaloDeChat', () => {
  it('sin ningún mensaje, pregunta espaciado', () => {
    expect(intervaloDeChat(null, AHORA)).toBe(POLL_CHAT_INACTIVO_MS);
    expect(intervaloDeChat(undefined, AHORA)).toBe(POLL_CHAT_INACTIVO_MS);
  });

  it('con un mensaje recién llegado, vuelve a la cadencia rápida', () => {
    expect(intervaloDeChat(haceMs(1000), AHORA)).toBe(POLL_CHAT_ACTIVO_MS);
  });

  it('triangulación: con el último mensaje viejo, vuelve a espaciar', () => {
    const viejo = haceMs(VENTANA_CONVERSACION_VIVA_MS + 60_000);
    expect(intervaloDeChat(viejo, AHORA)).toBe(POLL_CHAT_INACTIVO_MS);
  });

  it('en el borde exacto de la ventana todavía cuenta como viva', () => {
    const borde = haceMs(VENTANA_CONVERSACION_VIVA_MS);
    expect(intervaloDeChat(borde, AHORA)).toBe(POLL_CHAT_ACTIVO_MS);
  });

  it('una fecha ilegible cae del lado seguro: pregunta seguido', () => {
    expect(intervaloDeChat('no-es-una-fecha', AHORA)).toBe(POLL_CHAT_ACTIVO_MS);
  });

  it('un mensaje con fecha futura (relojes desfasados) cuenta como recién llegado', () => {
    const futuro = new Date(AHORA + 30_000).toISOString();
    expect(intervaloDeChat(futuro, AHORA)).toBe(POLL_CHAT_ACTIVO_MS);
  });

  // Las dos guardas de abajo son el intercambio completo, y van juntas a
  // propósito: cada una sola invita a romper la otra sin darse cuenta.

  it('el reposo ahorra de verdad: con 100 alumnos no pasa de 13 req/s', () => {
    // Con 3,5 s fijos eran ~29 req/s, más de un tercio del presupuesto, para un
    // canal que en casi ninguna sesión se usa. Cuando ese techo satura no se pone
    // lento el chat: se pone lento el autoguardado del examen de todos.
    const reqPorSegundoCon100 = 100 / (POLL_CHAT_INACTIVO_MS / 1000);
    expect(reqPorSegundoCon100).toBeLessThanOrEqual(13);
  });

  it('pero el alumno no espera más de 10 s el mensaje del tutor', () => {
    // La otra mitad: el ahorro no se paga con una persona esperando. El tutor
    // escribe para avisar algo AHORA, y el reposo es exactamente el peor caso de
    // esa espera.
    expect(POLL_CHAT_INACTIVO_MS).toBeLessThanOrEqual(10_000);
  });

  it('una charla con pausas no se cae a lento en el medio', () => {
    // Cinco minutos: nadie contesta al toque siempre, y que el tutor insista dos
    // minutos después no puede costarle al alumno otra espera completa.
    expect(VENTANA_CONVERSACION_VIVA_MS).toBeGreaterThanOrEqual(5 * 60 * 1000);
  });
});
