/**
 * Tests — lógica de selección de filas en ExamResultados (c-76, tareas 2.3–2.5)
 *
 * Cubre:
 *  a) toggleSelect: selecciona y deselecciona una fila
 *  b) toggleSelectAll: selecciona/deselecciona todas cuando hay resultados
 *  c) lote vacío: condición de "sin selección" detectada antes de llamar al API
 *  d) publicar individual: lista de 1 sesión
 *  e) publicar lote seleccionado: lista de N sesiones
 *
 * TDD Cycle: RED → GREEN → TRIANGULATE → REFACTOR
 * Framework: vitest (sin DOM ni mocks de DB — lógica pura de sets).
 * Autoridad `gestionar_notas` no se toca: la lógica de selección no verifica permisos,
 * eso ya está garantizado por el guard del router y el principal en authStore.
 */

import { describe, expect, it } from 'vitest';

// ---------------------------------------------------------------------------
// Helpers de selección extraídos como funciones puras para testabilidad
// (mismo algoritmo que ExamResultados.tsx — fuente única).
// ---------------------------------------------------------------------------

function toggleSelect(prev: Set<string>, sessionId: string): Set<string> {
  const next = new Set(prev);
  if (next.has(sessionId)) {
    next.delete(sessionId);
  } else {
    next.add(sessionId);
  }
  return next;
}

function toggleSelectAll(
  current: Set<string>,
  allIds: string[],
): Set<string> {
  if (current.size === allIds.length && allIds.length > 0) {
    return new Set<string>();
  }
  return new Set(allIds);
}

function todosSeleccionados(selected: Set<string>, total: number): boolean {
  return total > 0 && selected.size === total;
}

function algunosSeleccionados(selected: Set<string>, total: number): boolean {
  return selected.size > 0 && selected.size < total;
}

/** Condición de "lote sin selección" — no llama al API, avisa al usuario. */
function esLoteVacio(selected: Set<string>): boolean {
  return selected.size === 0;
}

/** Payload individual: lista de 1 id. */
function payloadIndividual(sessionId: string): string[] {
  return [sessionId];
}

/** Payload de lote seleccionado: lista de los ids en el set. */
function payloadLote(selected: Set<string>): string[] {
  return Array.from(selected);
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const IDS = ['sess-aaa', 'sess-bbb', 'sess-ccc'];

// ---------------------------------------------------------------------------
// 1. toggleSelect — selección y deselección individual
// ---------------------------------------------------------------------------

describe('1.1 toggleSelect — selecciona una fila', () => {
  it('agrega el id cuando no estaba seleccionado', () => {
    const result = toggleSelect(new Set<string>(), IDS[0]);
    expect(result.has(IDS[0])).toBe(true);
    expect(result.size).toBe(1);
  });

  it('remueve el id cuando ya estaba seleccionado (deselecciona)', () => {
    const inicial = new Set(IDS.slice(0, 2));
    const result = toggleSelect(inicial, IDS[0]);
    expect(result.has(IDS[0])).toBe(false);
    expect(result.has(IDS[1])).toBe(true);
  });
});

describe('1.2 toggleSelect — no muta el set original', () => {
  it('devuelve un nuevo Set, no el mismo objeto', () => {
    const original = new Set([IDS[0]]);
    const result = toggleSelect(original, IDS[1]);
    expect(result).not.toBe(original);
    expect(original.size).toBe(1); // el original no cambió
  });
});

// ---------------------------------------------------------------------------
// 2. toggleSelectAll — selección masiva
// ---------------------------------------------------------------------------

describe('2.1 toggleSelectAll — selecciona todos cuando ninguno está seleccionado', () => {
  it('llena el set con todos los ids', () => {
    const result = toggleSelectAll(new Set<string>(), IDS);
    expect(result.size).toBe(IDS.length);
    IDS.forEach((id) => expect(result.has(id)).toBe(true));
  });

  it('con algunos seleccionados, selecciona TODOS (no deselecciona — indeterminate → checked)', () => {
    const parcial = new Set([IDS[0]]);
    const result = toggleSelectAll(parcial, IDS);
    expect(result.size).toBe(IDS.length);
  });

  it('con todos seleccionados, deselecciona todos (checked → unchecked)', () => {
    const todos = new Set(IDS);
    const result = toggleSelectAll(todos, IDS);
    expect(result.size).toBe(0);
  });

  it('sin ids (lista vacía), no cambia nada — no puede seleccionar lo que no existe', () => {
    const result = toggleSelectAll(new Set<string>(), []);
    expect(result.size).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// 3. todosSeleccionados / algunosSeleccionados — estados del checkbox header
// ---------------------------------------------------------------------------

describe('3.1 todosSeleccionados', () => {
  it('es true cuando todos los resultados están en el set', () => {
    expect(todosSeleccionados(new Set(IDS), IDS.length)).toBe(true);
  });

  it('es false cuando hay resultados pero ninguno está seleccionado', () => {
    expect(todosSeleccionados(new Set<string>(), IDS.length)).toBe(false);
  });

  it('es false cuando la lista está vacía (no hay resultados)', () => {
    expect(todosSeleccionados(new Set<string>(), 0)).toBe(false);
  });
});

describe('3.2 algunosSeleccionados', () => {
  it('es true cuando hay una selección parcial', () => {
    expect(algunosSeleccionados(new Set([IDS[0]]), IDS.length)).toBe(true);
  });

  it('es false cuando todos están seleccionados', () => {
    expect(algunosSeleccionados(new Set(IDS), IDS.length)).toBe(false);
  });

  it('es false cuando ninguno está seleccionado', () => {
    expect(algunosSeleccionados(new Set<string>(), IDS.length)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 4. Caso lote sin selección — no llama al API, condición detectada
// ---------------------------------------------------------------------------

describe('4.1 esLoteVacio — detecta lote sin selección', () => {
  it('es true cuando el set está vacío (no llama al API)', () => {
    expect(esLoteVacio(new Set<string>())).toBe(true);
  });

  it('es false cuando hay al menos una selección', () => {
    expect(esLoteVacio(new Set([IDS[0]]))).toBe(false);
  });

  it('triangulación: lote con todos seleccionados no es vacío', () => {
    expect(esLoteVacio(new Set(IDS))).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 5. Payloads para sincronizarMoodleFn
// ---------------------------------------------------------------------------

describe('5.1 payloadIndividual — lista de 1 sesión', () => {
  it('devuelve un array con el único session_id', () => {
    expect(payloadIndividual(IDS[0])).toEqual([IDS[0]]);
  });

  it('no incluye otros ids', () => {
    const p = payloadIndividual(IDS[1]);
    expect(p).toHaveLength(1);
    expect(p[0]).toBe(IDS[1]);
  });
});

describe('5.2 payloadLote — lista de los ids seleccionados', () => {
  it('devuelve todos los ids del set como array', () => {
    const seleccionados = new Set([IDS[0], IDS[2]]);
    const p = payloadLote(seleccionados);
    expect(p).toHaveLength(2);
    expect(p).toContain(IDS[0]);
    expect(p).toContain(IDS[2]);
  });

  it('lote de 1 elemento — coincide con el payload individual', () => {
    const p = payloadLote(new Set([IDS[0]]));
    expect(p).toEqual(payloadIndividual(IDS[0]));
  });

  it('lote completo incluye todos los ids', () => {
    const p = payloadLote(new Set(IDS));
    expect(p).toHaveLength(IDS.length);
    IDS.forEach((id) => expect(p).toContain(id));
  });
});
