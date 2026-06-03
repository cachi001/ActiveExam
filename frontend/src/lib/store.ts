// Estado de sesión de la demo, compartido entre pantallas (rol activo, examen
// seleccionado, anomalías generadas durante el examen que el panel del proctor refleja).
import { create } from 'zustand';
import type { Principal, Rol, EventoSesion, Examen, SesionRevision, EstadoEnrollment, DecisionRevisor } from './types';

/** Clave de localStorage para la referencia biométrica 128-d (demo). */
const BIO_REF_KEY = 'activeexam_bio_ref';

/** Lee la referencia biométrica persistida (demo). Robusto ante JSON inválido. */
function leerReferenciaBiometrica(): number[] | null {
  try {
    const raw = localStorage.getItem(BIO_REF_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) && parsed.every((n) => typeof n === 'number') ? parsed : null;
  } catch {
    return null;
  }
}

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

  // ---------------------------------------------------------------------------
  // Decisiones humanas del revisor sobre la cola de revisión — C-47
  // ---------------------------------------------------------------------------
  /**
   * Mapa sessionId → decisión humana del revisor. El sistema nunca sanciona:
   * el score solo prioriza; la decisión disciplinaria es siempre humana.
   *
   * Registro local de la demo (el backend slim no tiene tabla de decisiones).
   * Valor inicial: {} (sin decisiones registradas).
   */
  decisionesRevisor: Record<string, DecisionRevisor>;

  // ---------------------------------------------------------------------------
  // Referencia biométrica REAL para verificación 1:1 — face-api 128-d
  // ---------------------------------------------------------------------------
  /**
   * Descriptor facial de 128 dimensiones capturado en el enrollment, usado como
   * REFERENCIA en la verificación 1:1 (Biometria.tsx lo compara contra el
   * descriptor "vivo" via api.verificarBiometria).
   *
   * Fuente de verdad efímera de la demo: store + localStorage (clave
   * `activeexam_bio_ref`). Null si el alumno aún no capturó referencia.
   *
   * DATO SENSIBLE (Ley 25.326): es dato biométrico. En producción vive cifrado
   * at-rest server-side; acá se mantiene solo para la comparación 1:1 de la demo.
   * NUNCA loguear este vector.
   */
  biometriaReferencia: number[] | null;

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
  /** C-47: registra la decisión humana del revisor sobre una sesión de la cola. */
  setDecisionRevisor: (id: string, decision: DecisionRevisor) => void;
  /** Setea el descriptor 128-d de referencia para la verificación 1:1 (face-api). */
  setBiometriaReferencia: (embedding: number[] | null) => void;
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
  decisionesRevisor: {},
  biometriaReferencia: leerReferenciaBiometrica(),

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
  setDecisionRevisor: (id, decision) =>
    set((s) => ({ decisionesRevisor: { ...s.decisionesRevisor, [id]: decision } })),
  setBiometriaReferencia: (embedding) => {
    try {
      if (embedding && embedding.length > 0) {
        localStorage.setItem(BIO_REF_KEY, JSON.stringify(embedding));
      } else {
        localStorage.removeItem(BIO_REF_KEY);
      }
    } catch {
      // localStorage no disponible (modo privado / cuota) → solo en memoria.
    }
    set({ biometriaReferencia: embedding });
  },
}));
