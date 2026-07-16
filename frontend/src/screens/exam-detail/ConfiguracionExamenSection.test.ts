/**
 * Test de formToPatch — cuando el examen está BLOQUEADO (>= 1 intento
 * finalizado) el PATCH debe enviar SOLO los campos de publicación de resultados.
 * Enviar los campos congelados (aunque sin cambios) gatillaría el 409 del
 * backend. Sin bloqueo, se envían todos.
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
    const patch = formToPatch(form, false);
    expect(patch).toHaveProperty('tiempo_limite_min', 40);
    expect(patch).toHaveProperty('nota_maxima', 10);
    expect(patch).toHaveProperty('mezclar_preguntas', false);
    expect(patch).toHaveProperty('mostrar_nota', 'al_cerrar');
  });

  it('bloqueado envía SOLO publicación (mostrar_nota + revision_habilitada)', () => {
    const patch = formToPatch(form, true);
    expect(Object.keys(patch).sort()).toEqual(['mostrar_nota', 'revision_habilitada']);
    expect(patch.mostrar_nota).toBe('al_cerrar');
    expect(patch.revision_habilitada).toBe(true);
  });

  it('bloqueado NO envía ningún campo de mecánica/nota', () => {
    const patch = formToPatch(form, true);
    expect(patch).not.toHaveProperty('tiempo_limite_min');
    expect(patch).not.toHaveProperty('nota_maxima');
    expect(patch).not.toHaveProperty('intentos_permitidos');
    expect(patch).not.toHaveProperty('mezclar_preguntas');
  });
});
