import { describe, it, expect } from 'vitest';
import { gateExamenImportado } from './gateExamenImportado';
import type { ExamenContenidoResumen, NotaExamen } from '../../lib/types';

const EXAMEN: ExamenContenidoResumen = {
  id: 'EX-1',
  titulo: 'Programación 1',
  cantidad_preguntas: 20,
  intentos_permitidos: 2,
  apertura: null,
  cierre: null,
} as ExamenContenidoResumen;

const nota = (examen_id: string): NotaExamen => ({ examen_id } as NotaExamen);

describe('gateExamenImportado — conteo de intentos', () => {
  it('sin intentos rendidos: habilitado, usados 0 de 2', () => {
    const g = gateExamenImportado(EXAMEN, []);
    expect(g.habilitado).toBe(true);
    expect(g.usados).toBe(0);
    expect(g.permitidos).toBe(2);
  });

  it('con 1 intento rendido: habilitado, usados 1 (queda 1 de 2)', () => {
    const g = gateExamenImportado(EXAMEN, [nota('EX-1')]);
    expect(g.habilitado).toBe(true);
    expect(g.usados).toBe(1);
    expect(g.permitidos).toBe(2);
  });

  it('con 2 intentos rendidos: bloqueado (2/2)', () => {
    const g = gateExamenImportado(EXAMEN, [nota('EX-1'), nota('EX-1')]);
    expect(g.habilitado).toBe(false);
    expect(g.usados).toBe(2);
    expect(g.motivo).toContain('2/2');
  });

  it('notas de OTRO examen no cuentan para este', () => {
    const g = gateExamenImportado(EXAMEN, [nota('OTRO'), nota('EX-1')]);
    expect(g.usados).toBe(1);
    expect(g.habilitado).toBe(true);
  });

  it('fuera de ventana (aún no abrió): bloqueado pero reporta usados/permitidos', () => {
    const futuro = { ...EXAMEN, apertura: '2099-01-01T10:00:00Z' } as ExamenContenidoResumen;
    const g = gateExamenImportado(futuro, [], Date.parse('2026-07-08T10:00:00Z'));
    expect(g.habilitado).toBe(false);
    expect(g.usados).toBe(0);
    expect(g.permitidos).toBe(2);
  });
});
