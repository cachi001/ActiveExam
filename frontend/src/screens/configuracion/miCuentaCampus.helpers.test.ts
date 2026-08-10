/**
 * TDD: RED → GREEN → TRIANGULATE
 * Helper puro de aviso de vencimiento de la credencial Moodle del tutor (C-73 §12).
 *
 * La credencial vence a los 30 días desde `actualizado_en` (calculado en el
 * backend, ver `esta_vencida` en credencial_docente_service.py). Acá solo se
 * decide QUÉ mostrarle al docente antes de que llegue ese momento.
 */

import { describe, expect, it } from 'vitest';
import { avisoConexion } from './miCuentaCampus.helpers';

describe('avisoConexion', () => {
  it('sin conectar (estado null) da sin_conectar', () => {
    expect(avisoConexion(null, null, new Date('2026-08-01'))).toEqual({ tipo: 'sin_conectar' });
  });

  it('caida da caida sin importar la antigüedad', () => {
    expect(avisoConexion('caida', '2026-07-01T00:00:00Z', new Date('2026-08-01'))).toEqual({
      tipo: 'caida',
    });
  });

  it('vencida (estado ya calculado por el backend) da vencida', () => {
    expect(avisoConexion('vencida', '2026-06-01T00:00:00Z', new Date('2026-08-01'))).toEqual({
      tipo: 'vencida',
    });
  });

  it('activa recién conectada da ok', () => {
    const ahora = new Date('2026-08-01T00:00:00Z');
    expect(avisoConexion('activa', '2026-08-01T00:00:00Z', ahora)).toEqual({ tipo: 'ok' });
  });

  it('activa a 20 días de conectada (10 restantes) todavía da ok', () => {
    const ahora = new Date('2026-08-21T00:00:00Z');
    expect(avisoConexion('activa', '2026-08-01T00:00:00Z', ahora)).toEqual({ tipo: 'ok' });
  });

  it('activa a 24 días de conectada (6 restantes, <=7) avisa por_vencer', () => {
    const ahora = new Date('2026-08-25T00:00:00Z');
    expect(avisoConexion('activa', '2026-08-01T00:00:00Z', ahora)).toEqual({
      tipo: 'por_vencer',
      diasRestantes: 6,
    });
  });

  it('activa a 30 días exactos igual avisa por_vencer con 0 restantes (el backend todavía no la marcó vencida)', () => {
    const ahora = new Date('2026-08-31T00:00:00Z');
    expect(avisoConexion('activa', '2026-08-01T00:00:00Z', ahora)).toEqual({
      tipo: 'por_vencer',
      diasRestantes: 0,
    });
  });
});
