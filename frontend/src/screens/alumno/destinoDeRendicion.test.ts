/**
 * A dónde manda «Rendir» según haya o no un examen empezado.
 *
 * Bug real (29/8/2026, probándolo el dueño): cerró la ventana a mitad del examen y
 * volvió con «Continuar examen». La tarjeta decía continuar, pero lo dejaba al
 * principio del ingreso —biometría, calibración, sala de espera— y con el botón
 * final diciendo «Comenzar examen». O sea: prometía retomar y arrancaba de cero.
 *
 * Peor que la molestia: `setProctoringSessionId(null)` descartaba el id de la
 * sesión viva, así que el examen volvía a arrancar como si fuera un intento nuevo
 * mientras el cronómetro de la sesión original seguía corriendo server-side.
 */

import { describe, expect, it } from 'vitest';

import { destinoDeRendicion } from './destinoDeRendicion';

const SESION = {
  session_id: 'sess-1',
  examen_contenido_id: 'ex-1',
  examen_titulo: 'Parcial',
  creada_en: '2026-08-29T08:11:41Z',
  examen_iniciado_en: '2026-08-29T08:11:45Z',
};

describe('destino de la rendición', () => {
  it('sin sesión abierta arranca el ingreso completo', () => {
    // Camino normal: consentimiento, biometría, calibración y sala de espera.
    expect(destinoDeRendicion(null)).toEqual({ ruta: '/pre-examen', sessionId: null });
  });

  it('con el examen ya empezado va derecho al examen', () => {
    expect(destinoDeRendicion(SESION)).toEqual({ ruta: '/examen', sessionId: 'sess-1' });
  });

  it('con el examen empezado conserva el id de la sesión viva', () => {
    // Es lo que evita abrir un intento nuevo sobre una sesión que sigue corriendo.
    expect(destinoDeRendicion(SESION).sessionId).toBe('sess-1');
  });

  it('si la sesión se creó pero el examen nunca arrancó, rehace el ingreso', () => {
    // `examen_iniciado_en` en null = se cayó DURANTE el ingreso (biometría,
    // calibración): nunca llegó a ver una pregunta ni arrancó el cronómetro. Ahí
    // saltearle la verificación lo dejaría rindiendo sin haberla pasado nunca.
    expect(destinoDeRendicion({ ...SESION, examen_iniciado_en: null })).toEqual({
      ruta: '/pre-examen',
      sessionId: 'sess-1',
    });
  });
});
