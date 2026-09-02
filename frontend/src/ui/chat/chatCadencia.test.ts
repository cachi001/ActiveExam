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

  it('el intervalo en reposo ahorra de verdad: al menos 4 veces menos requests', () => {
    // Con 100 alumnos, 3,5 s son ~29 req/s. El punto del cambio es ese ahorro,
    // así que se vigila la relación, no un número suelto que alguien pueda tocar
    // sin darse cuenta de lo que cuesta.
    expect(POLL_CHAT_INACTIVO_MS / POLL_CHAT_ACTIVO_MS).toBeGreaterThanOrEqual(4);
  });
});
