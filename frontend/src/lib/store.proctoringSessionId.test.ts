// @vitest-environment jsdom
/**
 * VULN CRÍTICA — reload durante la rendición reinicia el examen y deja una
 * sesión de proctoring "zombie".
 *
 * Causa raíz (parte frontend): `proctoringSessionId` vivía SOLO en memoria de
 * Zustand. Una recarga de página durante el examen lo volvía a `null`, y
 * `useExamProctoring` crea sesión `if (!proctoringSessionId)` → el reload
 * disparaba un POST /sessions nuevo (el backend ahora es idempotente y reanuda,
 * pero sin persistir acá el cliente ni siquiera sabía que ya tenía una).
 *
 * Fix: `setProctoringSessionId` persiste el id en sessionStorage (mismo patrón
 * que `_EXAMEN_ACTIVO_KEY` en store.examenActivo.test.ts) y `resetSesion` lo
 * limpia. No mockea sessionStorage (jsdom lo provee real).
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { useApp } from './store';

const KEY = 'ae_proctoring_session_id';

describe('store — persistencia de proctoringSessionId en sessionStorage', () => {
  beforeEach(() => {
    sessionStorage.clear();
    useApp.getState().setProctoringSessionId(null);
    sessionStorage.clear();
  });

  it('setProctoringSessionId persiste el id en sessionStorage (sobrevive un F5)', () => {
    useApp.getState().setProctoringSessionId('sesion-abc-123');

    expect(sessionStorage.getItem(KEY)).toBe('sesion-abc-123');
    expect(useApp.getState().proctoringSessionId).toBe('sesion-abc-123');
  });

  it('setProctoringSessionId(null) borra la clave (no deja "null" serializado)', () => {
    useApp.getState().setProctoringSessionId('sesion-abc-123');
    useApp.getState().setProctoringSessionId(null);

    expect(sessionStorage.getItem(KEY)).toBeNull();
    expect(useApp.getState().proctoringSessionId).toBeNull();
  });

  it('resetSesion limpia también la persistencia en sessionStorage (no solo la memoria)', () => {
    useApp.getState().setProctoringSessionId('sesion-abc-123');
    expect(sessionStorage.getItem(KEY)).not.toBeNull();

    useApp.getState().resetSesion();

    expect(sessionStorage.getItem(KEY)).toBeNull();
    expect(useApp.getState().proctoringSessionId).toBeNull();
  });
});

const CREADA_EN_KEY = 'ae_proctoring_session_creada_en';

describe('store — persistencia de proctoringSessionCreadaEn (ancla del timer server-autoritativo)', () => {
  beforeEach(() => {
    sessionStorage.clear();
    useApp.getState().setProctoringSessionCreadaEn(null);
    sessionStorage.clear();
  });

  it('setProctoringSessionCreadaEn persiste la fecha en sessionStorage', () => {
    useApp.getState().setProctoringSessionCreadaEn('2026-07-13T10:00:00Z');

    expect(sessionStorage.getItem(CREADA_EN_KEY)).toBe('2026-07-13T10:00:00Z');
    expect(useApp.getState().proctoringSessionCreadaEn).toBe('2026-07-13T10:00:00Z');
  });

  it('resetSesion limpia proctoringSessionCreadaEn (memoria y sessionStorage)', () => {
    useApp.getState().setProctoringSessionCreadaEn('2026-07-13T10:00:00Z');

    useApp.getState().resetSesion();

    expect(sessionStorage.getItem(CREADA_EN_KEY)).toBeNull();
    expect(useApp.getState().proctoringSessionCreadaEn).toBeNull();
  });
});
