/**
 * El glosario se le muestra al alumno: no cita normativa ni promete borrados.
 *
 * Decisión del dueño (28/8/2026), la misma que rige el texto de consentimiento
 * (ver `backend/tests/test_consentimiento_dice_lo_que_hacemos.py`):
 *
 *  - Nada de citar leyes. El sistema describe lo que hace con los datos.
 *  - Nada de prometer una eliminación que nadie ejecuta: la definición de
 *    "embedding" decía "se elimina al egreso" y esa purga no está implementada.
 *    Lo que sí ocurre es que la referencia vence a los 24 meses y hay que
 *    rehacerla; la anterior queda marcada como no vigente.
 */

import { describe, expect, it } from 'vitest';

import { GLOSSARY } from './glossary';

const textoVisible = () =>
  Object.values(GLOSSARY)
    .flatMap((entrada) => [entrada.label, entrada.definition, ...Object.values(entrada)])
    .filter((valor): valor is string => typeof valor === 'string')
    .join(' ')
    .toLowerCase();

describe('glosario', () => {
  it('no cita ninguna ley', () => {
    const cuerpo = textoVisible();
    for (const cita of ['ley ', '25.326', '25326', 'artículo', 'articulo']) {
      expect(cuerpo, `el glosario vuelve a citar normativa: ${cita}`).not.toContain(cita);
    }
  });

  it('no promete que la referencia biométrica se elimina al egreso', () => {
    const cuerpo = textoVisible();
    expect(cuerpo).not.toContain('egres');
  });

  it('sigue explicando qué es un embedding sin mostrar el dato', () => {
    expect(GLOSSARY.embedding.definition.toLowerCase()).toContain('rostro');
    expect(GLOSSARY.embedding.definition.toLowerCase()).toContain('no es una foto');
  });
});
