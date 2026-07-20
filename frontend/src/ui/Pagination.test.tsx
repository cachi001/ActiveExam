// Ventana de páginas visibles (con elipsis) del componente Pagination.
import { describe, expect, it } from 'vitest';
import { paginasVisibles } from './Pagination';

describe('paginasVisibles', () => {
  it('pocas páginas (<=4): las lista todas, sin elipsis', () => {
    expect(paginasVisibles(1, 1)).toEqual([1]);
    expect(paginasVisibles(2, 3)).toEqual([1, 2, 3]);
    expect(paginasVisibles(1, 4)).toEqual([1, 2, 3, 4]);
  });

  it('al inicio: muestra 1 2 3 … última', () => {
    expect(paginasVisibles(1, 20)).toEqual([1, 2, 3, '…', 20]);
    expect(paginasVisibles(2, 20)).toEqual([1, 2, 3, '…', 20]);
  });

  it('en el medio: 1 … actual-1 actual actual+1 … última', () => {
    expect(paginasVisibles(10, 20)).toEqual([1, '…', 9, 10, 11, '…', 20]);
  });

  it('al final: 1 … antepenúltima penúltima última', () => {
    expect(paginasVisibles(20, 20)).toEqual([1, '…', 18, 19, 20]);
    expect(paginasVisibles(19, 20)).toEqual([1, '…', 18, 19, 20]);
  });
});
