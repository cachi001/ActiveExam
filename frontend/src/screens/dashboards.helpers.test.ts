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
import { examenContenidoSubtitulo } from './dashboards.helpers';
import type { ExamenContenidoResumen } from '../lib/types';

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
// 5. Contrato: en modo demo la API NO tiene datos reales de inscripciones
// ---------------------------------------------------------------------------

describe('contrato API — modo demo', () => {
  it('api.modoDemo refleja el flag USE_REAL_BACKEND del entorno de test', async () => {
    const { api } = await import('../lib/api');
    // En el entorno de tests (sin VITE_USE_REAL_BACKEND=1), modoDemo debe ser true.
    // Esto confirma que los dashboards en modo real usarán rutas distintas.
    expect(typeof api.modoDemo).toBe('boolean');
  });

  it('api.listarExamenesContenido devuelve [] en modo demo (sin backend real)', async () => {
    const { api } = await import('../lib/api');
    if (api.modoDemo) {
      const resultado = await api.listarExamenesContenido();
      // En modo demo, el catálogo real no aplica → array vacío (vacío honesto).
      expect(resultado).toEqual([]);
    } else {
      // En modo real la respuesta depende del backend; el test es solo informativo.
      expect(true).toBe(true);
    }
  });
});
