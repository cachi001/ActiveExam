/**
 * Tests de detectorActivo — helper puro para filtrar eventos según detectores_activos.
 *
 * TDD cycle:
 *  RED  → tests escritos antes de la implementación (o en paralelo para helper puro).
 *  GREEN → implementación mínima en detectorActivo.ts.
 *  TRIANGULATE → al menos 2 casos por comportamiento.
 *  REFACTOR → función ya limpia, sin duplicación.
 */

import { describe, it, expect } from 'vitest';
import { detectorActivo } from './detectorActivo';

describe('detectorActivo', () => {
  // --- Fail-open: undefined/null → true (config no cargada, no suprimir nada) ---

  it('devuelve true si detectoresActivos es undefined (fail-open)', () => {
    expect(detectorActivo('rostro_ausente', undefined)).toBe(true);
  });

  it('devuelve true si detectoresActivos es null (fail-open)', () => {
    expect(detectorActivo('mirada_desviada', null)).toBe(true);
  });

  // Triangulación: distintos tipos con lista undefined siguen siendo true
  it('fail-open aplica para cualquier tipo cuando lista es undefined', () => {
    expect(detectorActivo('monitor_adicional', undefined)).toBe(true);
    expect(detectorActivo('copiar_pegar', undefined)).toBe(true);
  });

  // --- Lista con el tipo: devuelve true ---

  it('devuelve true si el tipo está en la lista', () => {
    const activos = ['rostro_ausente', 'mirada_desviada', 'copiar_pegar'];
    expect(detectorActivo('rostro_ausente', activos)).toBe(true);
  });

  // Triangulación: otro tipo que también está
  it('devuelve true para cualquier tipo que esté en la lista', () => {
    const activos = ['rostro_ausente', 'mirada_desviada'];
    expect(detectorActivo('mirada_desviada', activos)).toBe(true);
  });

  // --- Lista sin el tipo: devuelve false ---

  it('devuelve false si el tipo NO está en la lista', () => {
    const activos = ['rostro_ausente', 'mirada_desviada'];
    expect(detectorActivo('copiar_pegar', activos)).toBe(false);
  });

  // Triangulación: otro tipo ausente
  it('devuelve false para cualquier tipo ausente en la lista', () => {
    const activos = ['rostro_ausente'];
    expect(detectorActivo('monitor_adicional', activos)).toBe(false);
  });

  // --- Lista vacía: false para todo tipo (ningún detector activo) ---

  it('devuelve false si la lista está vacía', () => {
    expect(detectorActivo('rostro_ausente', [])).toBe(false);
  });

  // Triangulación: otro tipo con lista vacía
  it('devuelve false para cualquier tipo con lista vacía', () => {
    expect(detectorActivo('mirada_desviada', [])).toBe(false);
    expect(detectorActivo('copiar_pegar', [])).toBe(false);
  });
});
