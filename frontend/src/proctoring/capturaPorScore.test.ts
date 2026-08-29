/**
 * Con el score en el tope, se dejan de GUARDAR capturas.
 *
 * Decisión del dueño (29/8/2026), que revierte la de esa misma mañana: al llegar a
 * 100 el score ya está topeado (`Math.min(100, ...)`), así que cada imagen nueva no
 * cambia nada de la priorización ni del orden de la cola de revisión — solo ocupa
 * lugar. "Cualquier cosa en un futuro lo cambiamos".
 *
 * Lo que se pierde, y quedó dicho: si un alumno llega a 100 en el minuto 5, no hay
 * imágenes de los 55 minutos siguientes. Los EVENTOS se siguen registrando siempre
 * (eso no se toca), así que el revisor ve que pasó algo aunque no tenga la foto.
 */

import { describe, expect, it } from 'vitest';

import { SCORE_TOPE, debeGuardarCaptura, debeRegistrarEvento } from './capturaPorScore';

describe('guardado de capturas según el score', () => {
  it('con score bajo se guarda', () => {
    expect(debeGuardarCaptura(0)).toBe(true);
    expect(debeGuardarCaptura(35)).toBe(true);
  });

  it('justo debajo del tope todavía se guarda', () => {
    expect(debeGuardarCaptura(SCORE_TOPE - 1)).toBe(true);
  });

  it('en el tope ya no se guarda', () => {
    expect(debeGuardarCaptura(SCORE_TOPE)).toBe(false);
  });

  it('por encima del tope tampoco', () => {
    // El score viene topeado, pero el llamador podría pasar el acumulado sin capar.
    expect(debeGuardarCaptura(SCORE_TOPE + 40)).toBe(false);
  });
});

/**
 * Los EVENTOS también frenan en el tope.
 *
 * Decisión del dueño (29/8/2026): "ya alcanzó el máximo de score, para qué saturar
 * más". Con el score topeado, un evento nuevo no cambia la prioridad de la sesión
 * ni su lugar en la cola de revisión — la sesión ya está arriba de todo.
 *
 * El costo, dicho: alguien que llegue a 100 a propósito en los primeros minutos
 * queda sin registro el resto del examen. Lo que lo acota es que llegar a 100 deja
 * la sesión marcada en lo más alto de la cola, así que un revisor humano la va a
 * mirar igual — que es exactamente lo que el sistema promete (L2.5: prioriza, no
 * sanciona).
 */
describe('registro de eventos según el score', () => {
  it('con score bajo se registra', () => {
    expect(debeRegistrarEvento(0)).toBe(true);
    expect(debeRegistrarEvento(65)).toBe(true);
  });

  it('el evento que JUSTO llega al tope se registra', () => {
    // Se evalúa con el score PREVIO: si no, el evento que te lleva a 100 —el que
    // explica cómo llegaste— sería el único que se pierde.
    expect(debeRegistrarEvento(SCORE_TOPE - 1)).toBe(true);
  });

  it('en el tope ya no se registra', () => {
    expect(debeRegistrarEvento(SCORE_TOPE)).toBe(false);
  });

  it('por encima del tope tampoco', () => {
    expect(debeRegistrarEvento(SCORE_TOPE + 30)).toBe(false);
  });
});
