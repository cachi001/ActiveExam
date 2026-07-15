/**
 * Tests de equipmentGate — helper puro que decide si el alumno puede AVANZAR
 * desde el chequeo de requisitos al examen.
 *
 * Regla dura de dominio (pedido del owner): si NO se cumplen TODOS los
 * requisitos de entorno (cámara, red, navegador, un solo monitor), el avance
 * queda BLOQUEADO. Un requisito en 'falla', 'pendiente' o 'verificando' impide
 * continuar. Solo con todos en 'ok' se habilita el paso al examen.
 *
 * TDD cycle:
 *  RED  → test escrito antes de exportar puedeContinuar desde equipmentGate.ts.
 *  GREEN → implementación mínima.
 *  TRIANGULATE → happy path + cada estado no-ok + lista vacía.
 */

import { describe, it, expect } from 'vitest';
import { puedeContinuar, type RequisitoCheck } from './equipmentGate';

const ok = (): RequisitoCheck => ({ estado: 'ok' });

describe('puedeContinuar', () => {
  it('habilita el avance solo cuando TODOS los requisitos están en ok', () => {
    expect(puedeContinuar([ok(), ok(), ok(), ok()])).toBe(true);
  });

  it('bloquea si algún requisito está en falla (p. ej. 2 monitores)', () => {
    expect(puedeContinuar([ok(), ok(), ok(), { estado: 'falla' }])).toBe(false);
  });

  it('bloquea si algún requisito sigue pendiente', () => {
    expect(puedeContinuar([ok(), { estado: 'pendiente' }, ok(), ok()])).toBe(false);
  });

  it('bloquea mientras un requisito se está verificando', () => {
    expect(puedeContinuar([{ estado: 'verificando' }, ok(), ok(), ok()])).toBe(false);
  });

  it('bloquea si la lista está vacía (no hay evidencia de chequeo)', () => {
    expect(puedeContinuar([])).toBe(false);
  });

  it('bloquea con múltiples fallas (cámara y monitor)', () => {
    expect(puedeContinuar([{ estado: 'falla' }, ok(), ok(), { estado: 'falla' }])).toBe(false);
  });
});
