/**
 * Preferencias de UI persistidas (C-73, sección 3). Lo crítico: `partialize` es un
 * allowlist explícito (no filtra funciones ni campos no declarados) y el estado
 * de shape/version viejo se descarta (migrate).
 *
 * @vitest-environment jsdom
 */
import { beforeEach, describe, expect, it } from 'vitest';
import { useUiPrefs, UI_PREFS_STORAGE_KEY } from './useUiPrefs';

function leerPersistido(): { state: Record<string, unknown>; version: number } {
  return JSON.parse(localStorage.getItem(UI_PREFS_STORAGE_KEY) as string);
}

describe('useUiPrefs — persistencia de prefs de UI', () => {
  beforeEach(() => {
    localStorage.clear();
    useUiPrefs.setState({ sidebarColapsado: false });
  });

  it('toggle persiste la preferencia en localStorage', () => {
    useUiPrefs.getState().setSidebarColapsado(true);
    expect(leerPersistido().state.sidebarColapsado).toBe(true);
    useUiPrefs.getState().toggleSidebar();
    expect(leerPersistido().state.sidebarColapsado).toBe(false);
  });

  it('partialize es un allowlist: SOLO persiste sidebarColapsado (sin funciones ni otros campos)', () => {
    useUiPrefs.getState().setSidebarColapsado(true);
    expect(Object.keys(leerPersistido().state)).toEqual(['sidebarColapsado']);
  });

  it('rehidrata desde el storage al "volver" (persist.rehydrate)', async () => {
    localStorage.setItem(
      UI_PREFS_STORAGE_KEY,
      JSON.stringify({ state: { sidebarColapsado: true }, version: 1 }),
    );
    await useUiPrefs.persist.rehydrate();
    expect(useUiPrefs.getState().sidebarColapsado).toBe(true);
  });

  it('migrate: estado con version vieja se descarta → vuelve al default (no hereda campos)', async () => {
    localStorage.setItem(
      UI_PREFS_STORAGE_KEY,
      JSON.stringify({ state: { sidebarColapsado: true, campoSensible: 'no' }, version: 0 }),
    );
    await useUiPrefs.persist.rehydrate();
    expect(useUiPrefs.getState().sidebarColapsado).toBe(false);
    expect((useUiPrefs.getState() as Record<string, unknown>).campoSensible).toBeUndefined();
  });
});
