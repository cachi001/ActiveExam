// Preferencias de UI persistidas (C-73, sección 3).
//
// Store dedicado y DELIBERADAMENTE mínimo: acá SOLO viven preferencias de
// interfaz no sensibles (p. ej. si la sidebar está colapsada). NUNCA meter acá
// datos de autenticación (token/principal/roles) ni datos personales — esos son
// responsabilidad del provider de auth y jamás se persisten en el cliente.
//
// `partialize` es un ALLOWLIST explícito: agregar un campo nuevo al estado NO lo
// persiste salvo que se lo sume a mano a la lista. `version` + `migrate` descartan
// cualquier estado guardado con un shape viejo.
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

/** Clave del esquema anterior (bool crudo '1'/'0') — se migra una vez al nuevo store. */
const LEGACY_SIDEBAR_KEY = 'ae_sidebar_collapsed';

function legacySidebarColapsado(): boolean {
  try {
    return typeof localStorage !== 'undefined' && localStorage.getItem(LEGACY_SIDEBAR_KEY) === '1';
  } catch {
    return false;
  }
}

export interface UiPrefsState {
  /** Sidebar de staff/alumno colapsada (solo íconos). */
  sidebarColapsado: boolean;
  toggleSidebar: () => void;
  setSidebarColapsado: (v: boolean) => void;
}

export const UI_PREFS_STORAGE_KEY = 'ae_ui_prefs';
export const UI_PREFS_VERSION = 1;

export const useUiPrefs = create<UiPrefsState>()(
  persist(
    (set) => ({
      // Semilla desde el esquema viejo la primera vez (después manda lo persistido).
      sidebarColapsado: legacySidebarColapsado(),
      toggleSidebar: () => set((s) => ({ sidebarColapsado: !s.sidebarColapsado })),
      setSidebarColapsado: (v) => set({ sidebarColapsado: v }),
    }),
    {
      name: UI_PREFS_STORAGE_KEY,
      version: UI_PREFS_VERSION,
      // ALLOWLIST: SOLO estas prefs se persisten. No agregar auth ni PII acá.
      partialize: (s) => ({ sidebarColapsado: s.sidebarColapsado }),
      // Estado con version/shape desconocido → se descarta y se vuelve al default.
      migrate: (persisted, version) => {
        if (version < UI_PREFS_VERSION || typeof persisted !== 'object' || persisted === null) {
          return { sidebarColapsado: legacySidebarColapsado() };
        }
        const p = persisted as Partial<UiPrefsState>;
        return { sidebarColapsado: Boolean(p.sidebarColapsado) };
      },
    },
  ),
);
