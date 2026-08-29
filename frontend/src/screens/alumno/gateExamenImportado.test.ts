import { describe, it, expect } from 'vitest';
import {
  formatFechaHora,
  gateExamenImportado,
  textoVentana,
} from './gateExamenImportado';
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

// ---------------------------------------------------------------------------
// textoVentana — hasta cuándo se puede rendir, EN LA CARD
// ---------------------------------------------------------------------------
//
// Hasta ahora la ventana solo aparecía cuando el gate BLOQUEABA ("Disponible
// desde…", "Cerrado el…"). Mientras el examen estaba disponible, el alumno no
// tenía forma de saber hasta cuándo, salvo entrando a la ficha. Pedido del
// dueño: la card lo dice antes de entrar.

describe('textoVentana', () => {
  const APERTURA = '2026-08-27T12:00:00Z'; // 09:00 en Argentina (UTC-3)
  const CIERRE = '2026-08-31T02:59:00Z'; // 23:59 del 30 en Argentina

  it('con apertura y cierre dice el rango completo', () => {
    const t = textoVentana(APERTURA, CIERRE);
    expect(t).toMatch(/^Del .+ al .+$/);
    expect(t).toContain('27');
    expect(t).toContain('30');
  });

  it('con solo cierre dice hasta cuándo', () => {
    expect(textoVentana(null, CIERRE)).toMatch(/^Hasta el /);
  });

  it('con solo apertura dice desde cuándo', () => {
    expect(textoVentana(APERTURA, null)).toMatch(/^Desde el /);
  });

  it('sin fechas no inventa una ventana', () => {
    expect(textoVentana(null, null)).toBeNull();
    expect(textoVentana(undefined, undefined)).toBeNull();
  });

  it('escribe la hora en 24 horas, sin el "p. m." de es-AR', () => {
    expect(textoVentana(APERTURA, CIERRE)).not.toMatch(/[ap]\.\s?m\./i);
  });

  it('una fecha ilegible no rompe la card', () => {
    expect(textoVentana('no-es-una-fecha', null)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Examen sin preguntas: no se puede rendir
// ---------------------------------------------------------------------------
//
// Detectado el 28/8/2026 mirando el listado del alumno: "Primer parcial —
// Límites y continuidad" figuraba con 0 preguntas, publicado y con botón para
// entrar. Si el alumno entraba, llegaba a un examen vacío.
//
// Se BLOQUEA con motivo en vez de esconderlo: si el alumno espera ese parcial y
// no lo ve, no sabe si es un error suyo o del sistema.

describe('gateExamenImportado — examen sin preguntas', () => {
  const VACIO = { ...EXAMEN, cantidad_preguntas: 0 } as ExamenContenidoResumen;

  it('bloquea el examen que no tiene ninguna pregunta', () => {
    const g = gateExamenImportado(VACIO, []);
    expect(g.habilitado).toBe(false);
    expect(g.motivo).toMatch(/pregunta/i);
  });

  it('el motivo no culpa al alumno', () => {
    const g = gateExamenImportado(VACIO, []);
    expect(g.motivo).not.toMatch(/tu perfil|completá/i);
  });

  it('con preguntas cargadas no bloquea por este motivo', () => {
    expect(gateExamenImportado(EXAMEN, []).habilitado).toBe(true);
  });

  it('la ventana de fechas gana sobre el examen vacío', () => {
    const cerradoYVacio = { ...VACIO, cierre: '2020-01-01T10:00:00Z' } as ExamenContenidoResumen;
    const g = gateExamenImportado(cerradoYVacio, [], Date.parse('2026-08-28T10:00:00Z'));
    expect(g.motivo).toMatch(/cerrado/i);
  });
});

describe('formatFechaHora', () => {
  it('escribe la hora en 24 horas, igual que el resto de la tarjeta', () => {
    // La tarjeta mostraba "Hasta el 27-ago 22:49" y justo debajo "Cerrado el
    // 27/08/2026, 10:49 p. m.": la misma fecha en dos formatos distintos.
    expect(formatFechaHora('2026-08-28T01:49:00Z')).not.toMatch(/[ap]\.\s?m\./i);
  });

  it('sigue incluyendo el año: un examen cerrado puede ser de otro cuatrimestre', () => {
    expect(formatFechaHora('2026-08-28T01:49:00Z')).toMatch(/2026/);
  });
});
