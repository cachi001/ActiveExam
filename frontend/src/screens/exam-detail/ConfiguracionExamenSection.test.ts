/**
 * Test de formToPatch (C-72 secciones 6/18/7.7 — candado DIRECCIONAL).
 *
 * Con el examen ya rendido (`bloqueada`):
 *  - Los campos CONGELADO_DURO (tiempo, apertura, notas, mezclar) NO se envían nunca
 *    (enviarlos gatillaría el 409 del backend).
 *  - La publicación (mostrar_nota / revision_habilitada) siempre se envía (direccional).
 *  - `cierre` (solo EXTENDER) e `intentos_permitidos` (solo AUMENTAR) SÍ se pueden
 *    tocar, pero se envían SOLO si el docente los cambió — así un guardado sin tocarlos
 *    no dispara un falso 409 por truncamiento de precisión.
 * Sin bloqueo, se envía todo.
 */

import { describe, it, expect } from 'vitest';
import { formToPatch, type ConfigForm } from './ConfiguracionExamenSection';

const form: ConfigForm = {
  sinLimite: false,
  tiempoLimiteMin: '40',
  intentosPermitidos: '2',
  apertura: '2026-01-01T09:00',
  cierre: '2026-12-31T20:00',
  notaMaxima: '10',
  notaAprobacion: '6',
  mezclarPreguntas: false,
  mostrarNota: 'al_cerrar',
  revisionHabilitada: true,
};

describe('formToPatch', () => {
  it('sin bloqueo envía toda la config (incluye mecánica/nota)', () => {
    const patch = formToPatch(form, false, form);
    expect(patch).toHaveProperty('tiempo_limite_min', 40);
    expect(patch).toHaveProperty('nota_maxima', 10);
    expect(patch).toHaveProperty('mezclar_preguntas', false);
    expect(patch).toHaveProperty('mostrar_nota', 'al_cerrar');
  });

  it('bloqueado sin tocar cierre/intentos envía SOLO publicación', () => {
    const patch = formToPatch(form, true, form);
    expect(Object.keys(patch).sort()).toEqual(['mostrar_nota', 'revision_habilitada']);
  });

  it('bloqueado: si el docente EXTIENDE el cierre, se envía cierre', () => {
    const editado = { ...form, cierre: '2027-03-01T20:00' };
    const patch = formToPatch(editado, true, form);
    expect(patch).toHaveProperty('cierre');
    expect(patch.cierre).toBe(new Date('2027-03-01T20:00').toISOString());
  });

  it('bloqueado: si el docente SUBE los intentos, se envía intentos_permitidos', () => {
    const editado = { ...form, intentosPermitidos: '3' };
    const patch = formToPatch(editado, true, form);
    expect(patch).toHaveProperty('intentos_permitidos', 3);
  });

  it('bloqueado NUNCA envía campos congelado-duro (tiempo/apertura/notas/mezclar)', () => {
    const editado = { ...form, cierre: '2027-03-01T20:00', intentosPermitidos: '9' };
    const patch = formToPatch(editado, true, form);
    expect(patch).not.toHaveProperty('tiempo_limite_min');
    expect(patch).not.toHaveProperty('apertura');
    expect(patch).not.toHaveProperty('nota_maxima');
    expect(patch).not.toHaveProperty('nota_aprobacion');
    expect(patch).not.toHaveProperty('mezclar_preguntas');
  });
});
