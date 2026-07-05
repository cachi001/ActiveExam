/**
 * Tests para QuestionNavigator — navegador estilo Moodle de preguntas del examen.
 *
 * Sin @testing-library/react (no instalado). Usa inspección de fuente (mismo patrón
 * que Examen.test.ts y CaptureOval.test.tsx) para verificar estructura, clases CSS
 * semánticas y atributos de accesibilidad.
 *
 * TDD — ciclo RED → GREEN → TRIANGULATE → REFACTOR.
 */

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, 'QuestionNavigator.tsx'), 'utf8');

// ---------------------------------------------------------------------------
// 6.1 RED — Estructura del componente
// ---------------------------------------------------------------------------

describe('6.1 QuestionNavigator — exportación y props', () => {
  it('6.1a exporta QuestionNavigator como named export', () => {
    expect(src).toMatch(/export\s+function\s+QuestionNavigator/);
  });

  it('6.1b declara la interfaz QuestionNavigatorProps', () => {
    expect(src).toMatch(/QuestionNavigatorProps/);
  });

  it('6.1c la prop total está tipada', () => {
    expect(src).toMatch(/total\s*:/);
  });

  it('6.1d la prop indiceActual está tipada', () => {
    expect(src).toMatch(/indiceActual\s*:/);
  });

  it('6.1e la prop respondidas es de tipo Set<number>', () => {
    expect(src).toMatch(/respondidas\s*:\s*Set<number>/);
  });

  it('6.1f la prop onIr es callback con índice', () => {
    expect(src).toMatch(/onIr\s*:\s*\(indice\s*:\s*number\)\s*=>/);
  });
});

// ---------------------------------------------------------------------------
// 6.2 GREEN — Renderizado de botones
// ---------------------------------------------------------------------------

describe('6.2 QuestionNavigator — renderizado de N botones', () => {
  it('6.2a usa Array.from para generar los botones dinámicamente', () => {
    expect(src).toMatch(/Array\.from/);
  });

  it('6.2b renderiza elementos <button>', () => {
    expect(src).toMatch(/<button/);
  });

  it('6.2c llama onIr con el índice 0-based al hacer click', () => {
    expect(src).toMatch(/onIr\s*\(\s*i\s*\)/);
  });

  it('6.2d muestra el número de pregunta (1-based) como contenido', () => {
    // El componente debe calcular numero = i + 1
    expect(src).toMatch(/i\s*\+\s*1/);
  });
});

// ---------------------------------------------------------------------------
// 6.3 TRIANGULATE — Estados visuales
// ---------------------------------------------------------------------------

describe('6.3 QuestionNavigator — tres estados visuales distintos', () => {
  it('6.3a estado "actual": clase de fondo primario (bg-primary)', () => {
    expect(src).toMatch(/bg-primary/);
  });

  it('6.3b estado "respondida": fondo neutro (bg-secondary-container, NO verde para no confundirlo con "correcta")', () => {
    // Decisión de diseño (ver docstring del componente): la pregunta respondida
    // NO usa verde/success, para no sugerir que la respuesta es correcta.
    expect(src).toMatch(/bg-secondary-container/);
    expect(src).not.toMatch(/bg-success/);
  });

  it('6.3c estado "sin responder": fondo neutro de superficie', () => {
    // Usa tokens del design system: bg-surface-container-low o similar
    expect(src).toMatch(/bg-surface-container/);
  });

  it('6.3d estado "actual" tiene texto blanco (text-on-primary)', () => {
    expect(src).toMatch(/text-on-primary/);
  });
});

// ---------------------------------------------------------------------------
// 6.4 TRIANGULATE — Accesibilidad
// ---------------------------------------------------------------------------

describe('6.4 QuestionNavigator — accesibilidad (aria-label)', () => {
  it('6.4a incluye aria-label en cada botón', () => {
    expect(src).toMatch(/aria-label/);
  });

  it('6.4b el aria-label incluye "respondida" para preguntas respondidas', () => {
    expect(src).toMatch(/respondida/);
  });

  it('6.4c el aria-label incluye "sin responder" para preguntas sin respuesta', () => {
    expect(src).toMatch(/sin responder/);
  });

  it('6.4d marca la pregunta actual con aria-current', () => {
    expect(src).toMatch(/aria-current/);
  });
});

// ---------------------------------------------------------------------------
// 6.5 TRIANGULATE — Responsivo y acceso táctil
// ---------------------------------------------------------------------------

describe('6.5 QuestionNavigator — diseño responsivo y touch-friendly', () => {
  it('6.5a contenedor usa flex-wrap para múltiples filas en mobile', () => {
    expect(src).toMatch(/flex-wrap/);
  });

  it('6.5b botones tienen tamaño mínimo táctil (w-10 h-10 = 40px)', () => {
    expect(src).toMatch(/w-10/);
    expect(src).toMatch(/h-10/);
  });

  it('6.5c usa respondidas.has(i) para verificar si está respondida', () => {
    expect(src).toMatch(/respondidas\.has\s*\(\s*i\s*\)/);
  });
});

// ---------------------------------------------------------------------------
// 6.6 REFACTOR — Limpieza final
// ---------------------------------------------------------------------------

describe('6.6 QuestionNavigator — convenciones del proyecto', () => {
  it('6.6a no importa @testing-library (no está instalado)', () => {
    expect(src).not.toMatch(/@testing-library/);
  });

  it('6.6b importa React o usa JSX sin import explícito (Vite/React 17+)', () => {
    // O importa React, o confía en el transform automático de Vite
    const hasReactImport = src.includes("from 'react'") || src.includes('from "react"');
    const hasJSX = src.includes('<button') || src.includes('<div');
    expect(hasReactImport || hasJSX).toBe(true);
  });

  it('6.6c usa key={i} en cada botón para evitar warnings de lista', () => {
    expect(src).toMatch(/key=\{i\}/);
  });
});
