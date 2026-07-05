/**
 * Tests de regresión: la capa de API es SIEMPRE real (modo demo eliminado).
 *
 * Bloquean que vuelva a aparecer el "modo demo/mock": estos tests FALLARÍAN con
 * el código previo (donde existían `api.modoDemo`, `USE_REAL_BACKEND` y los
 * métodos mock-only) y PASAN con la capa real-only.
 *
 * Estilo del repo: import del módulo + aserciones puras (sin red, sin DOM).
 */

import { describe, expect, it } from 'vitest';
import * as apiModule from './api';
import { api } from './api';

describe('api real-only — modo demo eliminado', () => {
  it('el objeto api NO expone la propiedad modoDemo', () => {
    expect('modoDemo' in api).toBe(false);
  });

  it('el módulo NO exporta el flag USE_REAL_BACKEND', () => {
    expect((apiModule as Record<string, unknown>).USE_REAL_BACKEND).toBeUndefined();
  });

  it('los métodos mock-only fueron eliminados del objeto api', () => {
    const eliminados = [
      'login',
      'verifyIdentity',
      'listExams',
      'saveExam',
      'inscribir',
      'liveSessions',
      'reviewQueue',
      'resolveReview',
      'reportes',
    ] as const;
    for (const metodo of eliminados) {
      expect((api as Record<string, unknown>)[metodo]).toBeUndefined();
    }
  });
});

describe('api real-only — comportamiento colapsado', () => {
  it('misInscripciones() devuelve [] (no hay modelo de inscripción en real)', async () => {
    await expect(api.misInscripciones()).resolves.toEqual([]);
  });

  it('getExam() devuelve undefined (sin catálogo mock; el examen real viene de exam-content)', async () => {
    await expect(api.getExam('EX-CUALQUIERA')).resolves.toBeUndefined();
  });
});
