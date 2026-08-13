/**
 * Portal del alumno (C-21) y enrollment biometrico del perfil (C-22).
 *
 * Se re-exporta desde `lib/types.ts`: importa siempre desde ahi.
 */

// ---------------------------------------------------------------------------
// Portal del alumno — C-21
// ---------------------------------------------------------------------------

/** Estado de inscripción de un alumno a un examen. */
export type EstadoInscripcion = 'inscripto' | 'pendiente' | 'habilitado' | 'rendido';

// ---------------------------------------------------------------------------
// Enrollment biométrico del perfil — C-22
// ---------------------------------------------------------------------------

/**
 * Acuse de consentimiento inmutable asociado al perfil del alumno.
 * version + timestamp + hash forman la traza legal del acuse (RN-CO-01).
 * Servidor: se re-hashea y firma server-side; aquí es el mock de demo.
 */
export interface AcuseConsentimiento {
  /** Versión del texto de consentimiento al momento de consentir. */
  version: string;
  /** ISO 8601: momento de la acción afirmativa. */
  timestamp: string;
  /**
   * Hash del acuse (demo: simulado).
   * Server-side: SHA-256 del contenido firmado por la clave maestra (C-12).
   */
  hash: string;
  /** true si el alumno eligió la vía alternativa sin biometría (RN-CO-05). */
  via_alternativa: boolean;
}

/**
 * Estado de vigencia de la referencia biométrica.
 * Se usa tanto para el embedding como para la imagen de referencia.
 */
export type VigenciaReferencia = 'vigente' | 'por_vencer' | 'caducada' | 'renovacion_requerida';

/**
 * Referencia biométrica capturada en el enrollment del perfil.
 *
 * DATOS SENSIBLES (Ley 25.326):
 * - embedding: cifrado at-rest server-side (AES-256-GCM); en demo se guarda el
 *   vector simulado y se documenta el tratamiento en comentario.
 * - imagen: cifrada at-rest; finalidad acotada a verificación de identidad y
 *   revisión humana; eliminada al egreso del estudiante; holds legales difieren.
 * El cliente es SENSOR NO CONFIABLE: en producción el backend re-infiere y firma
 * (C-12). Lo que se guarda aquí en demo es la señal del cliente, no el veredicto.
 */
export interface ReferenciasBiometrica {
  /** true cuando la captura fue completada exitosamente. */
  captura_completada: boolean;
  /**
   * dataURL/base64 de la imagen de referencia (demo).
   * Server-side: cifrada AES-256-GCM, finalidad acotada, eliminada al egreso,
   * holds legales difieren la eliminación (RN-BIO-07, Ley 25.326).
   */
  imagen: string | null;
  /**
   * Embedding facial derivado de Face Mesh (demo: array de números simulados).
   * Server-side: cifrado at-rest, finalidad acotada a verificación de identidad,
   * marcado para eliminación al egreso, holds difieren (RN-BIO-08, Ley 25.326).
   */
  embedding: number[] | null;
  /** ISO 8601: momento de la captura. */
  fecha_captura: string;
  /** ISO 8601: fecha de expiración (fecha_captura + vigencia_meses). */
  fecha_expiracion: string;
  /** Meses de vigencia aplicados (configurable, default BIOMETRIC_VALIDITY_MONTHS). */
  vigencia_meses: number;
  /** Versión del motor de visión usado para calcular el embedding. */
  version_motor: string;
  /** Estado de vigencia calculado. */
  vigencia: VigenciaReferencia;
  /**
   * true si la verificación silenciosa continua detectó deriva sostenida del
   * embedding y marcó la referencia para renovación anticipada (C-22, decisión 4).
   * La deriva NO sanciona ni invalida la rendición en curso (L2.5).
   */
  renovacion_anticipada_requerida: boolean;
  /**
   * true si un admin habilitó al alumno a rehacer su referencia vigente (override
   * de un solo uso). Mientras la referencia esté vigente, el botón "Rehacer" solo
   * aparece si esto es true; si venció, aparece igual (renovación normal).
   */
  rehacer_habilitado?: boolean;
  /**
   * C-56: UUID opaco del registro en `embedding_referencia` (backend).
   * Presente solo en modo real (USE_REAL_BACKEND=1) tras un enrollment exitoso.
   * El cliente persiste este ID en el store (no el embedding crudo).
   * Undefined en modo demo.
   */
  referencia_id?: string;
}

/**
 * Escaneo de DNI del perfil (opcional, detrás de feature flag ENABLE_DNI_SCAN).
 *
 * DATO SENSIBLE (Ley 25.326):
 * Server-side: cifrado AES-256-GCM, finalidad acotada a verificación de identidad,
 * eliminado al egreso, holds legales difieren la eliminación.
 * En demo: se guarda el dataURL simulado con los metadatos de custodia.
 */
export interface EscaneDNI {
  /** true cuando el escaneo fue completado. */
  captura_completada: boolean;
  /**
   * dataURL/base64 del FRENTE del DNI (demo). DATO SENSIBLE (Ley 25.326):
   * server-side cifrado AES-256-GCM, finalidad acotada, eliminado al egreso.
   */
  imagen_frente: string | null;
  /** dataURL/base64 del DORSO del DNI (demo). Mismo tratamiento sensible que el frente. */
  imagen_dorso: string | null;
  /** ISO 8601: momento de la captura. */
  fecha_captura: string;
}

/**
 * Estado de enrollment completo del perfil del alumno (C-22).
 * "Perfil completo" = (consentimiento válido OR via_alternativa) AND referencia vigente.
 * El DNI es OPCIONAL y NO bloquea el perfil completo.
 */
export interface EstadoEnrollment {
  /** Acuse de consentimiento, null si aún no consintió. */
  consentimiento: AcuseConsentimiento | null;
  /** Referencia biométrica, null si aún no capturó. */
  biometria: ReferenciasBiometrica | null;
  /** Escaneo de DNI, null si no aplica o no completó. */
  dni: EscaneDNI | null;
  /**
   * Derivado: true si el perfil está completo y el alumno puede rendir.
   * = (consentimiento != null OR via_alternativa) AND biometria vigente (no caducada).
   */
  perfil_completo: boolean;
}

