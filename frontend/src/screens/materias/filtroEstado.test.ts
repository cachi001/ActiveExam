import { describe, expect, it } from 'vitest';
import {
  contarDeBaja,
  estaDeBaja,
  filtrarPorEstado,
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
