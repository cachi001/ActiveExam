/**
 * Tests para las funciones puras del navegador de preguntas (QuestionNavigator).
 *
 * TDD — ciclo RED → GREEN → TRIANGULATE → REFACTOR.
 *
 * Las funciones se agregan a ExamenLogic.ts para mantener toda la lógica de
 * navegación pura en un mismo módulo testeable sin DOM.
 */

import { describe, expect, it } from 'vitest';
import { indicesRespondidos, irAIndice } from './ExamenLogic';

// ---------------------------------------------------------------------------
// indicesRespondidos
// ---------------------------------------------------------------------------

describe('indicesRespondidos — índices (0-based) de preguntas con respuesta seleccionada', () => {
  // 5.1 RED: conjunto vacío cuando no hay respuestas
  it('5.1 retorna Set vacío cuando respuestas está vacío', () => {
    const preguntas = [
      { id: 'p1' },
      { id: 'p2' },
    ];
    const result = indicesRespondidos(preguntas, {});
    expect(result).toBeInstanceOf(Set);
    expect(result.size).toBe(0);
  });

  // 5.2 GREEN: una pregunta respondida
  it('5.2 retorna el índice de la pregunta que tiene respuesta', () => {
    const preguntas = [{ id: 'p1' }, { id: 'p2' }, { id: 'p3' }];
    const respuestas = { p2: 'op-A' };
    const result = indicesRespondidos(preguntas, respuestas);
    expect(result.has(1)).toBe(true); // índice 1 = pregunta p2
    expect(result.size).toBe(1);
  });

  // 5.3 TRIANGULATE: múltiples preguntas respondidas
  it('5.3 incluye todos los índices de preguntas respondidas', () => {
    const preguntas = [{ id: 'q1' }, { id: 'q2' }, { id: 'q3' }, { id: 'q4' }];
    const respuestas = { q1: 'x', q3: 'y' };
    const result = indicesRespondidos(preguntas, respuestas);
    expect(result.has(0)).toBe(true);   // q1
    expect(result.has(1)).toBe(false);  // q2 sin respuesta
    expect(result.has(2)).toBe(true);   // q3
    expect(result.has(3)).toBe(false);  // q4 sin respuesta
    expect(result.size).toBe(2);
  });

  // 5.4 TRIANGULATE: lista vacía de preguntas
  it('5.4 retorna Set vacío con lista de preguntas vacía', () => {
    const result = indicesRespondidos([], { p1: 'op-X' });
    expect(result.size).toBe(0);
  });

  // 5.5 TRIANGULATE: todas las preguntas respondidas
  it('5.5 retorna todos los índices cuando todas están respondidas', () => {
    const preguntas = [{ id: 1 }, { id: 2 }, { id: 3 }];
    const respuestas = { 1: 'a', 2: 'b', 3: 'c' };
    const result = indicesRespondidos(preguntas, respuestas);
    expect(result.size).toBe(3);
    expect(result.has(0)).toBe(true);
    expect(result.has(1)).toBe(true);
    expect(result.has(2)).toBe(true);
  });

  // 5.6 TRIANGULATE: id numérico (la API puede usar number o string)
  it('5.6 funciona con ids numéricos', () => {
    const preguntas = [{ id: 10 }, { id: 20 }];
    const respuestas = { 10: 'op-1' };
    const result = indicesRespondidos(preguntas, respuestas);
    expect(result.has(0)).toBe(true);
    expect(result.has(1)).toBe(false);
  });

  // 5.7 TRIANGULATE: respuesta con valor string vacío no cuenta como respondida
  it('5.7 respuesta undefined no cuenta (la clave no está en el mapa)', () => {
    const preguntas = [{ id: 'p1' }, { id: 'p2' }];
    // Solo 'p1' tiene respuesta en el mapa; 'p2' no está
    const respuestas = { p1: 'op-A' };
    const result = indicesRespondidos(preguntas, respuestas);
    expect(result.has(0)).toBe(true);
    expect(result.has(1)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// irAIndice
// ---------------------------------------------------------------------------

describe('irAIndice — valida y retorna un índice destino para el navegador', () => {
  // 5.8 RED: índice válido dentro del rango retorna el índice
  it('5.8 retorna el índice cuando está en rango válido [0, total-1]', () => {
    expect(irAIndice(0, 5)).toBe(0);
    expect(irAIndice(2, 5)).toBe(2);
    expect(irAIndice(4, 5)).toBe(4);
  });

  // 5.9 GREEN: índice fuera de rango retorna null
  it('5.9 retorna null para índice negativo', () => {
    expect(irAIndice(-1, 5)).toBeNull();
  });

  // 5.10 TRIANGULATE: índice >= total retorna null
  it('5.10 retorna null para índice igual a total (fuera del rango)', () => {
    expect(irAIndice(5, 5)).toBeNull();
  });

  it('5.10b retorna null para índice mayor que total', () => {
    expect(irAIndice(10, 5)).toBeNull();
  });

  // 5.11 TRIANGULATE: total <= 0
  it('5.11 retorna null si total es 0', () => {
    expect(irAIndice(0, 0)).toBeNull();
  });

  it('5.11b retorna null si total es negativo', () => {
    expect(irAIndice(0, -1)).toBeNull();
  });

  // 5.12 TRIANGULATE: caso límite exacto — el último índice válido
  it('5.12 retorna total-1 para el último índice válido', () => {
    expect(irAIndice(4, 5)).toBe(4);
    expect(irAIndice(0, 1)).toBe(0);
  });
});
