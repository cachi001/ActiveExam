import { describe, expect, it } from 'vitest';

import { camaraCaida } from './camaraObligatoria';

/** MediaStream mínimo: solo lo que `camaraCaida` mira. */
const stream = (pistas: Array<{ readyState: string; enabled: boolean }>) =>
  ({ getVideoTracks: () => pistas }) as unknown as MediaStream;

const viva = { readyState: 'live', enabled: true };
const muerta = { readyState: 'ended', enabled: true };
const apagada = { readyState: 'live', enabled: false };

describe('cámara obligatoria durante el examen', () => {
  it('con la cámara viva no bloquea', () => {
    expect(camaraCaida({ stream: stream([viva]) })).toBe(false);
  });

  it('bloquea si nunca se pudo abrir', () => {
    expect(camaraCaida({ stream: null })).toBe(true);
  });

  it('bloquea si la desenchufan a mitad de examen', () => {
    // Desenchufar deja la pista en `ended`: es el caso que motivó esto.
    expect(camaraCaida({ stream: stream([muerta]) })).toBe(true);
  });

  it('bloquea si la deshabilitan sin desenchufarla', () => {
    expect(camaraCaida({ stream: stream([apagada]) })).toBe(true);
  });

  it('bloquea si el stream se quedó sin pista de video', () => {
    expect(camaraCaida({ stream: stream([]) })).toBe(true);
  });

  it('con varias pistas alcanza que UNA esté viva', () => {
    // Algunas cámaras exponen más de una; exigir todas bloquearía de más.
    expect(camaraCaida({ stream: stream([muerta, viva]) })).toBe(false);
  });
});
