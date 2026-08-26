/**
 * La revisión del alumno NO le explica la fórmula de la nota (c-78, pedido del dueño).
 *
 *     "en la revicion no se debe mostrar como se le calcula la nota al alumno,
 *      y yo creo que lo mostraba"
 *
 * Lo mostraba: decía literalmente *"Cada pregunta vale lo mismo; la nota =
 * correctas ÷ total × 10"*.
 *
 * El alumno tiene que ver **su resultado** — la nota, cuántas acertó, cuántas no
 * — pero no el mecanismo con el que se calculó. La fórmula no le agrega nada
 * para estudiar y sí invita a discutir el redondeo en vez del contenido.
 *
 * Este test mira el TEXTO que se arma, no el componente entero: la pantalla pide
 * datos al backend y montarla acá traería medio sistema. Lo que se sostiene es
 * el contenido del mensaje, que es exactamente lo que el dueño pidió cambiar.
 */
import { describe, expect, it } from 'vitest';

import { textoResultadoRevision } from './ExamenRevision.texto';

describe('texto del resultado en la revisión del alumno', () => {
  it('no le muestra la fórmula de cálculo', () => {
    const texto = textoResultadoRevision({ correctas: 6, total: 10, notaMaxima: 10 });

    expect(texto).not.toMatch(/÷/);
    expect(texto).not.toMatch(/correctas ÷ total/i);
    expect(texto).not.toMatch(/nota =/i);
  });

  it('sí le dice cuántas acertó sobre el total', () => {
    const texto = textoResultadoRevision({ correctas: 6, total: 10, notaMaxima: 10 });

    expect(texto).toMatch(/6/);
    expect(texto).toMatch(/10/);
  });

  it('no menciona la nota máxima como parte de una cuenta', () => {
    const texto = textoResultadoRevision({ correctas: 7, total: 12, notaMaxima: 100 });

    expect(texto).not.toMatch(/× *100/);
  });

  it('sin preguntas no arma una frase rota ni divide por cero', () => {
    const texto = textoResultadoRevision({ correctas: 0, total: 0, notaMaxima: 10 });

    expect(texto).not.toMatch(/NaN/);
    expect(texto.length).toBeGreaterThan(0);
  });

  it('el porcentaje acompaña al conteo, que es devolución y no fórmula', () => {
    const texto = textoResultadoRevision({ correctas: 5, total: 10, notaMaxima: 10 });

    expect(texto).toMatch(/50\s*%/);
  });
});
