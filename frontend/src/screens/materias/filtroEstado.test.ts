import { describe, expect, it } from 'vitest';
import {
  contarDeBaja,
  estaDeBaja,
  filtrarPorEstado,
  seleccionSigueVisible,
  etiquetaConBaja,
  OPCIONES_ESTADO_BAJA,
} from './filtroEstado';

const VIGENTE = { id: '1', activa: true };
const DE_BAJA = { id: '2', activa: false };
// Respuestas viejas del backend no traían `activa`.
const SIN_CAMPO = { id: '3' };

describe('filtro de baja lógica de materias y comisiones', () => {
  it('por defecto se ven las vigentes y NO las dadas de baja', () => {
    const r = filtrarPorEstado([VIGENTE, DE_BAJA], 'activa');
    expect(r.map((x) => x.id)).toEqual(['1']);
  });

  it('"Dadas de baja" muestra solo esas: es la papelera', () => {
    const r = filtrarPorEstado([VIGENTE, DE_BAJA], 'inactiva');
    expect(r.map((x) => x.id)).toEqual(['2']);
  });

  it('"Todas" no esconde nada', () => {
    const r = filtrarPorEstado([VIGENTE, DE_BAJA], 'todas');
    expect(r.map((x) => x.id)).toEqual(['1', '2']);
  });

  it('sin el campo `activa` se considera vigente, no dada de baja', () => {
    // Al revés escondería materias que nunca nadie dio de baja.
    expect(estaDeBaja(SIN_CAMPO)).toBe(false);
    expect(filtrarPorEstado([SIN_CAMPO], 'activa')).toHaveLength(1);
    expect(filtrarPorEstado([SIN_CAMPO], 'inactiva')).toHaveLength(0);
  });

  it('cuenta las dadas de baja para poder avisar que existen', () => {
    expect(contarDeBaja([VIGENTE, DE_BAJA, SIN_CAMPO, { activa: false }])).toBe(2);
  });

  it('una lista vacía no rompe ningún filtro', () => {
    for (const { valor } of OPCIONES_ESTADO_BAJA) {
      expect(filtrarPorEstado([], valor)).toEqual([]);
    }
  });
});

// ---------------------------------------------------------------------------
// seleccionSigueVisible — el panel de detalle no puede sobrevivir al filtro
// ---------------------------------------------------------------------------
//
// Auditado el 28/8/2026 con una materia dada de baja: la lista de la izquierda
// mostraba "Materias (1)" con solo la activa, y el panel de la derecha seguía
// abierto en "Comisiones de Análisis Matemático I" — justo la que el filtro
// acababa de ocultar. Quien mira la pantalla ve el detalle de algo que, según
// la lista, no existe.

describe('seleccionSigueVisible', () => {
  const visibles = [{ id: 'a' }, { id: 'b' }];

  it('mantiene la selección cuando sigue en la lista', () => {
    expect(seleccionSigueVisible('a', visibles)).toBe(true);
  });

  it('la descarta cuando el filtro la sacó de la lista', () => {
    expect(seleccionSigueVisible('z', visibles)).toBe(false);
  });

  it('sin selección no hay nada que descartar', () => {
    expect(seleccionSigueVisible(null, visibles)).toBe(true);
  });

  it('con la lista todavía vacía no descarta: es carga en curso, no un filtro', () => {
    // Descartar acá cerraría el panel en cada recarga, antes de que llegue el fetch.
    expect(seleccionSigueVisible('a', [])).toBe(true);
  });
});

describe('etiquetaConBaja', () => {
  it('marca las dadas de baja en los desplegables de filtro', () => {
    expect(etiquetaConBaja({ id: '1', activa: false }, 'AM1 — Análisis')).toBe(
      'AM1 — Análisis (dada de baja)',
    );
  });

  it('no toca la etiqueta de una vigente', () => {
    expect(etiquetaConBaja({ id: '1', activa: true }, 'PROG1 — Programación')).toBe(
      'PROG1 — Programación',
    );
  });

  it('sin el campo `activa` la trata como vigente (respuestas viejas del backend)', () => {
    expect(etiquetaConBaja({ id: '1' }, 'X')).toBe('X');
  });
});
