// @vitest-environment jsdom
/**
 * Regresión del bug "el paso 2 (Consentimiento) no avanza al confirmar".
 *
 * Causa raíz: el flujo de rendición leía `examenActivo` SOLO de la memoria del
 * store Zustand. Una recarga de página entre /requisitos y /consentimiento
 * reiniciaba el módulo y `examenActivo` volvía a null → en Consent el guard
 * `if (!acepto || !examen) return` dejaba el botón "Confirmar y continuar" inerte.
 *
 * Fix: `setExamenActivo` persiste el examen en sessionStorage y el store lo
 * rehidrata al inicializarse; `resetSesion` lo limpia. Este test fija ese contrato.
 *
 * No mockea sessionStorage (jsdom lo provee real) ni red ni base de datos.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { useApp } from './store';
import type { Examen } from './types';

const EXAMEN_FIXTURE: Examen = {
  id: 'EX-TEST-1',
  nombre: 'Examen de prueba',
  catedra: 'Cátedra X',
  estado: 'en_curso',
  inicio: '2026-06-29T10:00:00',
  duracion_min: 60,
  umbral_score: 70,
  detectores: [],
  retencion_dias: 30,
  inscriptos: 0,
  rindiendo: 0,
  examen_contenido_id: 'contenido-123',
};

const KEY = 'ae_examen_activo';

describe('store — persistencia de examenActivo en sessionStorage', () => {
  beforeEach(() => {
    sessionStorage.clear();
    useApp.getState().setExamenActivo(null);
    sessionStorage.clear();
  });

  it('setExamenActivo persiste el examen en sessionStorage (sobrevive recargas)', () => {
    useApp.getState().setExamenActivo(EXAMEN_FIXTURE);

    const raw = sessionStorage.getItem(KEY);
    expect(raw).not.toBeNull();
    const persistido = JSON.parse(raw as string) as Examen;
    expect(persistido.id).toBe('EX-TEST-1');
    // El examen_contenido_id debe persistir: sin él la nota no podría computarse.
    expect(persistido.examen_contenido_id).toBe('contenido-123');
    // El store en memoria también lo refleja.
    expect(useApp.getState().examenActivo?.id).toBe('EX-TEST-1');
  });

  it('resetSesion limpia el examen persistido (evita arrastrar un examen viejo)', () => {
    useApp.getState().setExamenActivo(EXAMEN_FIXTURE);
    expect(sessionStorage.getItem(KEY)).not.toBeNull();

    useApp.getState().resetSesion();

    expect(sessionStorage.getItem(KEY)).toBeNull();
    expect(useApp.getState().examenActivo).toBeNull();
  });

  it('setExamenActivo(null) borra la clave (no deja "null" serializado)', () => {
    useApp.getState().setExamenActivo(EXAMEN_FIXTURE);
    useApp.getState().setExamenActivo(null);
    expect(sessionStorage.getItem(KEY)).toBeNull();
  });
});

describe('store — reset de la sesión de proctoring entre intentos', () => {
  beforeEach(() => {
    useApp.getState().setProctoringSessionId(null);
    useApp.getState().setProctoringExamId(null);
    useApp.getState().setExamenActivo(null);
    sessionStorage.clear();
  });

  // Bug real de corrección: `resetSesion` reseteaba scorePropio/anomalías/examenActivo
  // pero NO `proctoringSessionId`. El intento 2 reusaba la sesión FINALIZADA del intento
  // 1 (Consent solo crea sesión `if (!proctoringSessionId)`), las respuestas del intento
  // 2 se rechazaban (409 sesión finalizada) y la revisión mostraba las respuestas del
  // intento 1. resetSesion debe dejar la sesión en null para que cada intento nazca limpio.
  it('resetSesion limpia proctoringSessionId y proctoringExamId', () => {
    useApp.getState().setProctoringSessionId('sesion-intento-1');
    useApp.getState().setProctoringExamId('EX-TEST-1');
    expect(useApp.getState().proctoringSessionId).toBe('sesion-intento-1');

    useApp.getState().resetSesion();

    expect(useApp.getState().proctoringSessionId).toBeNull();
    expect(useApp.getState().proctoringExamId).toBeNull();
  });
});
