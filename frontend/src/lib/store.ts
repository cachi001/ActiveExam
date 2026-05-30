// Estado de sesión de la demo, compartido entre pantallas (rol activo, examen
// seleccionado, anomalías generadas durante el examen que el panel del proctor refleja).
import { create } from 'zustand';
import type { Principal, Rol, EventoSesion, Examen, SesionRevision } from './types';

interface AppState {
  principal: Principal | null;
  rol: Rol | null;
  examenActivo: Examen | null;
  // anomalías acumuladas durante el examen del estudiante (alimenta panel proctor)
  anomaliasVivo: EventoSesion[];
  scorePropio: number;
  revisionSeleccionada: SesionRevision | null;

  setPrincipal: (p: Principal | null, rol: Rol | null) => void;
  setExamenActivo: (e: Examen | null) => void;
  setRevisionSeleccionada: (s: SesionRevision | null) => void;
  pushAnomalia: (e: EventoSesion) => void;
  addScore: (delta: number) => void;
  resetSesion: () => void;
}

export const useApp = create<AppState>((set) => ({
  principal: null,
  rol: null,
  examenActivo: null,
  anomaliasVivo: [],
  scorePropio: 0,
  revisionSeleccionada: null,

  setPrincipal: (principal, rol) => set({ principal, rol }),
  setExamenActivo: (examenActivo) => set({ examenActivo }),
  setRevisionSeleccionada: (revisionSeleccionada) => set({ revisionSeleccionada }),
  pushAnomalia: (e) => set((s) => ({ anomaliasVivo: [e, ...s.anomaliasVivo].slice(0, 50) })),
  addScore: (delta) => set((s) => ({ scorePropio: Math.min(100, s.scorePropio + delta) })),
  resetSesion: () => set({ anomaliasVivo: [], scorePropio: 0, examenActivo: null }),
}));
