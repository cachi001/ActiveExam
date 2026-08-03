/**
 * TDD — RED → GREEN → TRIANGULATE: pure helpers de dashboards.
 *
 * Cycle (examenContenidoSubtitulo):
 *  RED:        tests escritos antes de la función.
 *  GREEN:      función implementada, todos pasan.
 *  TRIANGULATE: cuatro casos (ambos, solo materia, solo comision, fallback).
 *
 * Sin DOM ni React — solo lógica pura, corre en node (vitest default).
 */
import { describe, it, expect } from 'vitest';
import {
  examenContenidoSubtitulo,
  formatVentanaExamen,
  formatDuracionExamen,
  statExamenesValue,
} from './dashboards.helpers';
import type { ExamenContenidoResumen } from '../lib/types';

// ---------------------------------------------------------------------------
// statExamenesValue — valor de la stat "Exámenes" del AdminDashboard (C-73 2.1/2.2).
// Lo crítico: un fetch en ERROR NUNCA muestra "0" (dato fantasma); muestra un
// marcador de error. Cargando → placeholder; ready → la cantidad (0 legítimo).
// ---------------------------------------------------------------------------
describe('statExamenesValue', () => {
  it('error → marcador de error, NUNCA 0 fantasma', () => {
    const v = statExamenesValue('error', 0);
    expect(v).toBe('—');
    expect(v).not.toBe(0);
    expect(v).not.toBe('0');
  });

  it('cargando (loading/idle) → placeholder, no un número', () => {
    expect(statExamenesValue('loading', 0)).toBe('…');
    expect(statExamenesValue('idle', 0)).toBe('…');
  });

  it('ready → la cantidad real (incluye 0 legítimo y N)', () => {
    expect(statExamenesValue('ready', 0)).toBe(0); // 0 real, no fantasma
    expect(statExamenesValue('ready', 1)).toBe(1);
    expect(statExamenesValue('ready', 7)).toBe(7);
  });
});

// ---------------------------------------------------------------------------
// 1. RED → GREEN: caso feliz con materia y comision
// ---------------------------------------------------------------------------

describe('examenContenidoSubtitulo — materia y comision presentes', () => {
  it('concatena materia_nombre · comision_nombre cuando ambos tienen valor', () => {
    const e: ExamenContenidoResumen = {
      id: 'e-1',
      titulo: 'Parcial de Álgebra',
      cantidad_preguntas: 5,
      materia_nombre: 'Álgebra',
      comision_nombre: 'Comisión A',
    };
    expect(examenContenidoSubtitulo(e)).toBe('Álgebra · Comisión A');
  });
});

// ---------------------------------------------------------------------------
// 2. TRIANGULATE: solo materia (sin comision)
// ---------------------------------------------------------------------------

describe('examenContenidoSubtitulo — solo materia_nombre', () => {
  it('devuelve solo materia_nombre cuando comision_nombre es undefined', () => {
    const e: ExamenContenidoResumen = {
      id: 'e-2',
      titulo: 'Final de Física',
      cantidad_preguntas: 10,
      materia_nombre: 'Física I',
    };
    expect(examenContenidoSubtitulo(e)).toBe('Física I');
  });

  it('devuelve solo materia_nombre cuando comision_nombre es null', () => {
    const e: ExamenContenidoResumen = {
      id: 'e-3',
      titulo: 'Parcial',
      cantidad_preguntas: 8,
      materia_nombre: 'Química',
      comision_nombre: null,
    };
    expect(examenContenidoSubtitulo(e)).toBe('Química');
  });
});

// ---------------------------------------------------------------------------
// 3. TRIANGULATE: solo comision (sin materia)
// ---------------------------------------------------------------------------

describe('examenContenidoSubtitulo — solo comision_nombre', () => {
  it('devuelve solo comision_nombre cuando materia_nombre es undefined', () => {
    const e: ExamenContenidoResumen = {
      id: 'e-4',
      titulo: 'Parcial',
      cantidad_preguntas: 4,
      comision_nombre: 'Comisión B',
    };
    expect(examenContenidoSubtitulo(e)).toBe('Comisión B');
  });
});

// ---------------------------------------------------------------------------
// 4. TRIANGULATE: fallback a cantidad_preguntas
// ---------------------------------------------------------------------------

describe('examenContenidoSubtitulo — fallback a cantidad_preguntas', () => {
  it('devuelve "N preguntas" cuando no hay materia ni comision', () => {
    const e: ExamenContenidoResumen = {
      id: 'e-5',
      titulo: 'Test sin contexto',
      cantidad_preguntas: 12,
    };
    expect(examenContenidoSubtitulo(e)).toBe('12 preguntas');
  });

  it('devuelve "0 preguntas" para examen sin preguntas aún', () => {
    const e: ExamenContenidoResumen = {
      id: 'e-6',
      titulo: 'Borrador',
      cantidad_preguntas: 0,
    };
    expect(examenContenidoSubtitulo(e)).toBe('0 preguntas');
  });
});

// ---------------------------------------------------------------------------
// formatVentanaExamen — ventana de rendición legible
// (no aserta el render exacto de fecha para no acoplar el test al timezone)
// ---------------------------------------------------------------------------

describe('formatVentanaExamen', () => {
  it('sin apertura ni cierre → "Sin ventana de fechas"', () => {
    expect(formatVentanaExamen(null, null)).toBe('Sin ventana de fechas');
    expect(formatVentanaExamen(undefined, undefined)).toBe('Sin ventana de fechas');
  });

  it('apertura y cierre → rango con flecha', () => {
    const r = formatVentanaExamen('2026-07-03T14:00:00Z', '2026-07-03T16:00:00Z');
    expect(r).toContain('→');
  });

  it('solo apertura → prefijo "Desde"', () => {
    expect(formatVentanaExamen('2026-07-03T14:00:00Z', null)).toMatch(/^Desde /);
  });

  it('solo cierre → prefijo "Hasta"', () => {
    expect(formatVentanaExamen(null, '2026-07-03T16:00:00Z')).toMatch(/^Hasta /);
  });
});

// ---------------------------------------------------------------------------
// formatDuracionExamen — duración legible (determinística)
// ---------------------------------------------------------------------------

describe('formatDuracionExamen', () => {
  it('sin límite (null/0) → "Sin límite de tiempo"', () => {
    expect(formatDuracionExamen(null)).toBe('Sin límite de tiempo');
    expect(formatDuracionExamen(0)).toBe('Sin límite de tiempo');
    expect(formatDuracionExamen(undefined)).toBe('Sin límite de tiempo');
  });

  it('menos de una hora → "N min"', () => {
    expect(formatDuracionExamen(45)).toBe('45 min');
  });

  it('horas exactas → "N h"', () => {
    expect(formatDuracionExamen(120)).toBe('2 h');
  });

  it('horas + minutos → "N h M min"', () => {
    expect(formatDuracionExamen(90)).toBe('1 h 30 min');
  });
});

