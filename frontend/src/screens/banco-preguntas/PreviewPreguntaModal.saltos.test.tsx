/**
 * La vista previa tiene que respetar los saltos de línea del enunciado.
 *
 * Bug real (29/8/2026, encontrado mirando la pantalla y no la base): una pregunta
 * de completar código se veía así en «Ver como la ve el alumno»:
 *
 *     Consigna: … def promedio(notas): ____ ____ return ____
 *
 * Todo en un renglón. En la base el texto tiene sus `\n`, pero el modal lo vuelca
 * con `dangerouslySetInnerHTML` y en HTML un salto de línea es un espacio más. El
 * parser ya quita todas las etiquetas de Moodle, así que no queda ningún `<br>` ni
 * `<p>` que produzca el corte: el texto llega plano y se pega todo.
 *
 * En una pregunta de completar código, la estructura por líneas ES el enunciado.
 * La pantalla del examen ya usaba `whitespace-pre-wrap`; esta se había quedado sin él.
 */

import { describe, it, expect } from 'vitest';

import { CLASE_ENUNCIADO } from './PreviewPreguntaModal';

describe('enunciado de la vista previa', () => {
  it('conserva los saltos de línea', () => {
    // `pre-wrap` es lo que hace que `\n` corte renglón en vez de volverse espacio.
    expect(CLASE_ENUNCIADO).toContain('whitespace-pre-wrap');
  });

  it('conserva también los espacios del principio de cada línea', () => {
    // Misma propiedad: `pre-wrap` no colapsa la sangría. Es lo que va a hacer
    // visible la indentación del código cuando se reimporte el banco.
    expect(CLASE_ENUNCIADO).toContain('whitespace-pre-wrap');
  });
});
