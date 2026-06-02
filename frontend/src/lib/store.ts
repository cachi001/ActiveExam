// Estado de sesión de la demo, compartido entre pantallas (rol activo, examen
// seleccionado, anomalías generadas durante el examen que el panel del proctor refleja).
import { create } from 'zustand';
import type { Principal, Rol, EventoSesion, Examen, SesionRevision, EstadoEnrollment } from './types';

interface AppState {
  principal: Principal | null;
  rol: Rol | null;
  examenActivo: Examen | null;
  // anomalías acumuladas durante el examen del estudiante (alimenta panel proctor)
  anomaliasVivo: EventoSesion[];
  scorePropio: number;
  revisionSeleccionada: SesionRevision | null;

  // ---------------------------------------------------------------------------
  // Enrollment biométrico del perfil — C-22
  // ---------------------------------------------------------------------------
  /**
   * Estado de enrollment cacheado en el store para evitar re-fetch innecesario.
   * Fuente de verdad: api.getEnrollment(). El store refleja el último estado leído.
   * `isProfileComplete` es el derivado que usan las pantallas.
   */
  enrollmentStatus: EstadoEnrollment | null;

  /** Derivado: true si el perfil está completo y el alumno puede rendir. */
  isProfileComplete: boolean;

  // ---------------------------------------------------------------------------
  // Sesión activa de proctoring — C-46
  // ---------------------------------------------------------------------------
  /**
   * ID de la sesión de proctoring activa en el backend slim (C-45).
   * Null cuando no hay sesión activa (modo mock / sin grabar / sin examen).
   * Se usa para acoplamiento entre Biometria.tsx (envío biométrico) y el harness.
   * D6 del design.md: Zustand evita prop drilling entre componentes no relacionados.
   */
  proctoringSessionId: string | null;

  setPrincipal: (p: Principal | null, rol: Rol | null) => void;
  setExamenActivo: (e: Examen | null) => void;
  setRevisionSeleccionada: (s: SesionRevision | null) => void;
  pushAnomalia: (e: EventoSesion) => void;
  addScore: (delta: number) => void;
  resetSesion: () => void;
  /** Actualiza el estado de enrollment en el store (llamar tras cada api.getEnrollment()). */
  setEnrollmentStatus: (e: EstadoEnrollment) => void;
  /**
   * Actualiza la foto de perfil del principal en el store (C-37).
   * Sin error si principal es null.
   */
  setFotoPerfil: (dataUrl: string) => void;
  /** C-46: setea el ID de la sesión de proctoring activa (o null para limpiarla). */
  setProctoringSessionId: (id: string | null) => void;
}

export const useApp = create<AppState>((set) => ({
  principal: null,
  rol: null,
  examenActivo: null,
  anomaliasVivo: [],
  scorePropio: 0,
  revisionSeleccionada: null,
  enrollmentStatus: null,
  isProfileComplete: false,
  proctoringSessionId: null,

  setPrincipal: (principal, rol) => set({ principal, rol }),
  setExamenActivo: (examenActivo) => set({ examenActivo }),
  setRevisionSeleccionada: (revisionSeleccionada) => set({ revisionSeleccionada }),
  pushAnomalia: (e) => set((s) => ({ anomaliasVivo: [e, ...s.anomaliasVivo].slice(0, 50) })),
  addScore: (delta) => set((s) => ({ scorePropio: Math.min(100, s.scorePropio + delta) })),
  resetSesion: () => set({ anomaliasVivo: [], scorePropio: 0, examenActivo: null }),
  setEnrollmentStatus: (e) => set({ enrollmentStatus: e, isProfileComplete: e.perfil_completo }),
  setFotoPerfil: (dataUrl) => set((s) => ({
    principal: s.principal ? { ...s.principal, foto_perfil: dataUrl } : s.principal,
  })),
  setProctoringSessionId: (id) => set({ proctoringSessionId: id }),
}));
