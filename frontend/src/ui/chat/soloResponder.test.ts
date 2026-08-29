import { describe, expect, it } from 'vitest';

import { AVISO_SOLO_RESPONDER, puedeResponder } from './soloResponder';
import type { MensajeChat } from '../../lib/types';

const msg = (autor: 'alumno' | 'tutor', id = autor): MensajeChat => ({
  id,
  autor,
  texto: 'hola',
  creado_en: '2026-08-29T10:00:00Z',
});

describe('chat del alumno durante el examen', () => {
  it('sin mensajes NO puede escribir: no inicia la conversación', () => {
    expect(puedeResponder([])).toBe(false);
  });

  it('puede responder en cuanto el tutor le escribe', () => {
    expect(puedeResponder([msg('tutor')])).toBe(true);
  });

  it('sigue habilitado después de contestar', () => {
    // Cortarlo a la mitad sería peor: no podría aclarar lo que le preguntaron.
    expect(puedeResponder([msg('tutor', '1'), msg('alumno', '2')])).toBe(true);
  });

  it('sus propios mensajes no lo habilitan', () => {
    // La guarda no se puede abrir sola: si un mensaje del alumno contara, un
    // envío que se colara dejaría el canal abierto para siempre.
    expect(puedeResponder([msg('alumno')])).toBe(false);
  });

  it('el aviso dice qué puede hacer, no solo que está bloqueado', () => {
    expect(AVISO_SOLO_RESPONDER).toMatch(/responder/i);
    expect(AVISO_SOLO_RESPONDER).toMatch(/tutor/i);
  });
});
