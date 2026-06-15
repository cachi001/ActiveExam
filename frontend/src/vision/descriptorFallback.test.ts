/**
 * Tests para firstDescriptor (C-67 fix: "todo perfecto y me da error en la captura").
 *
 * TDD: ciclo RED → GREEN → TRIANGULATE.
 *
 * Problema: el descriptor 128-d se sacaba de UN solo frame con el detector de
 * face-api (tinyFaceDetector), que es OTRO modelo distinto a MediaPipe. Si no
 * enganchaba la cara en ese frame → null → error, aunque los gestos de MediaPipe
 * salieran perfectos. firstDescriptor prueba varios frames candidatos y devuelve
 * el primer descriptor válido, dándole a face-api múltiples oportunidades.
 */

import { describe, expect, it, vi } from 'vitest';
import { firstDescriptor } from './descriptorFallback';

// En entorno node no hay HTMLCanvasElement real; usamos objetos opacos casteados.
// firstDescriptor NO toca el DOM: solo itera y delega en `compute`.
const f = (id: number) => ({ __id: id } as unknown as HTMLCanvasElement);
const D128 = Array.from({ length: 128 }, (_, i) => i / 128);

describe('firstDescriptor', () => {
  it('primer frame válido → devuelve su descriptor', async () => {
    const compute = vi.fn(async () => D128);
    const res = await firstDescriptor([f(1), f(2)], compute);
    expect(res).toEqual(D128);
    expect(compute).toHaveBeenCalledTimes(1); // corta en el primero que sirve
  });

  it('primer frame falla (null), segundo engancha → devuelve el segundo', async () => {
    const compute = vi
      .fn<(c: HTMLCanvasElement) => Promise<number[] | null>>()
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce(D128);
    const res = await firstDescriptor([f(1), f(2)], compute);
    expect(res).toEqual(D128);
    expect(compute).toHaveBeenCalledTimes(2);
  });

  it('todos los frames fallan → null', async () => {
    const compute = vi.fn(async () => null);
    const res = await firstDescriptor([f(1), f(2), f(3)], compute);
    expect(res).toBeNull();
    expect(compute).toHaveBeenCalledTimes(3);
  });

  it('array vacío → null (sin llamar a compute)', async () => {
    const compute = vi.fn(async () => D128);
    const res = await firstDescriptor([], compute);
    expect(res).toBeNull();
    expect(compute).not.toHaveBeenCalled();
  });

  it('saltea frames null/undefined del array', async () => {
    const compute = vi.fn(async () => D128);
    const res = await firstDescriptor([null, undefined, f(1)], compute);
    expect(res).toEqual(D128);
    expect(compute).toHaveBeenCalledTimes(1);
    expect(compute).toHaveBeenCalledWith(f(1));
  });

  it('un frame que hace throw no rompe: pasa al siguiente', async () => {
    const compute = vi
      .fn<(c: HTMLCanvasElement) => Promise<number[] | null>>()
      .mockRejectedValueOnce(new Error('boom'))
      .mockResolvedValueOnce(D128);
    const res = await firstDescriptor([f(1), f(2)], compute);
    expect(res).toEqual(D128);
    expect(compute).toHaveBeenCalledTimes(2);
  });
});
