/**
 * El cartel del destino de la nota decía "Vacío = usa el destino global", y el
 * backend hace exactamente lo contrario: sin curso y actividad cargados lanza
 * `MoodleDestinoNoConfiguradoError` y la nota queda retenida, nunca llega al
 * campus. No hay ningún destino global al que caer, y es a propósito: caer a uno
 * escribía la nota en la libreta de otra materia sin que nadie se enterara.
 *
 * O sea que el cartel inducía justo el error que el backend quiere prevenir. El
 * docente lee "vacío = global", deja los campos en blanco, y las notas de todo un
 * examen se quedan sin sincronizar hasta que alguien lo note a mano.
 *
 * Este test fija el contrato del texto: no puede prometer un destino global, y
 * tiene que decir que sin estos datos la nota no se envía.
 */
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

// Se escanea el código SIN comentarios: el comentario que explica este mismo bug
// nombra la frase prohibida, y si no se quitaran el test se acusaría a sí mismo.
const FUENTE = readFileSync(join(__dirname, 'DestinoMoodleSection.tsx'), 'utf8')
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/^\s*\/\/.*$/gm, '');

describe('texto del destino de la nota', () => {
  it('no promete un destino global: el backend no tiene ninguno', () => {
    expect(
      /destino global/i.test(FUENTE),
      'El backend lanza MoodleDestinoNoConfiguradoError cuando falta el destino. ' +
        'Prometer un "destino global" hace que el docente deje los campos vacíos y ' +
        'las notas queden sin enviar.',
    ).toBe(false);
  });

  it('avisa que sin destino la nota no se envía', () => {
    expect(
      /no se (envía|envia|puede enviar)/i.test(FUENTE),
      'El cartel tiene que decir qué pasa si queda vacío, que es que la nota no ' +
        'sale al campus.',
    ).toBe(true);
  });
});
