// Estado de sesión de la demo, compartido entre pantallas (rol activo, examen
// seleccionado, anomalías generadas durante el examen que el panel del proctor refleja).
import { create } from 'zustand';
import type { Principal, Rol, EventoSesion, Examen, SesionRevision, EstadoEnrollment, DecisionRevisor } from './types';

// C-56: la clave `activeexam_bio_ref` (embedding crudo en localStorage) queda eliminada.
// El embedding ya no se persiste en el cliente: el backend devuelve un `referencia_id`
// opaco que es lo único que el store persiste. Si quedó algún valor antiguo, lo limpiamos
// al inicializar para garantizar que no haya datos biométricos en localStorage.
const _LEGACY_BIO_REF_KEY = 'activeexam_bio_ref';
try {
  if (typeof localStorage !== 'undefined') {
    localStorage.removeItem(_LEGACY_BIO_REF_KEY);
  }
} catch {
  // localStorage no disponible (SSR / modo privado) → ignorar silenciosamente.
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

  /**
   * ID del examen seleccionado en supervisión en vivo para ver el grid de personas
   * que lo están rindiendo (drill-down examen → personas → detalle). Null si no hay
   * examen seleccionado. El router es hash sin params dinámicos, por eso vive en el store.
   */
  proctoringExamId: string | null;

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
  // Referencia biométrica persistida en backend — C-56
  // ---------------------------------------------------------------------------
  /**
   * C-56: ID opaco (UUID) de la referencia biométrica persistida en el backend.
   * Se obtiene tras un enrollment exitoso (POST /enrollment/embedding-referencia).
   * Null si el alumno aún no completó el enrollment biométrico.
   *
   * El embedding crudo 128-d YA NO se persiste en el cliente ni en localStorage.
   * El backend lo cifra at-rest (Fernet). Solo el `referencia_id` viaja al cliente.
   */
  biometrico_referencia_id: string | null;

  /**
   * Descriptor facial de 128 dimensiones para la verificación 1:1 en la demo
   * (solo en modo demo, NO en modo real). En modo real el embedding queda en el
   * backend cifrado at-rest; el cliente no lo almacena.
   *
   * DATO SENSIBLE (Ley 25.326): NUNCA loguear. Solo para la comparación 1:1 demo.
   * En producción (USE_REAL_BACKEND=1): siempre null.
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
  /** Setea el examen seleccionado para ver su grid de personas en vivo. */
  setProctoringExamId: (id: string | null) => void;
  /** C-47: registra la decisión humana del revisor sobre una sesión de la cola. */
  setDecisionRevisor: (id: string, decision: DecisionRevisor) => void;
  /**
   * C-56: persiste el referencia_id opaco del backend (no el embedding crudo).
   * Llamar tras un enrollment exitoso con el UUID retornado por el backend.
   */
  setBiometricoReferenciaId: (id: string | null) => void;
  /**
   * Setea el descriptor 128-d de referencia para la verificación 1:1 (demo).
   * Solo en modo demo. En modo real, usar setBiometricoReferenciaId.
   */
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
  proctoringExamId: null,
  decisionesRevisor: {},
  // C-56: el ID de referencia se inicializa en null (no viene de localStorage).
  // El embedding crudo ya no se lee de localStorage (la clave `activeexam_bio_ref`
  // fue eliminada al inicializar el módulo — ver bloque de limpieza arriba).
  biometrico_referencia_id: null,
  biometriaReferencia: null,

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
  setProctoringExamId: (id) => set({ proctoringExamId: id }),
  setDecisionRevisor: (id, decision) =>
    set((s) => ({ decisionesRevisor: { ...s.decisionesRevisor, [id]: decision } })),
  // C-56: persiste el referencia_id opaco del backend (no el embedding crudo).
  setBiometricoReferenciaId: (id) => set({ biometrico_referencia_id: id }),
  // Solo en modo demo: persiste el descriptor 128-d en memoria (sin localStorage).
  // En modo real (USE_REAL_BACKEND=1) el embedding queda en el backend cifrado at-rest.
  setBiometriaReferencia: (embedding) => {
    // C-56: NO persiste el embedding en localStorage. Solo en memoria de la sesión.
    // La clave `activeexam_bio_ref` fue eliminada (ver bloque de limpieza arriba).
    set({ biometriaReferencia: embedding });
  },
}));
