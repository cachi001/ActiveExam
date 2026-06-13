// Tipos de dominio del MVP ActiveExam. Calcados de los schemas del backend
// (app/presentation/api/v1/*). Nombres y enums en español, igual que la API real.

// Modelo de roles MVP (3 roles). admin_sistema es el rol administrativo único:
// configura exámenes, ve reportes/auditoría Y resuelve la cola de revisión
// (antes 'revisor'). Alineado con el realm de Keycloak (C-52).
export type Rol =
  | 'estudiante'
  | 'proctor'
  | 'admin_sistema';

export type Severidad = 'baseline' | 'baja' | 'media' | 'alta' | 'critica';

// tipos de evento discreto emitidos por el pipeline de visión (stateTransitionRules.ts)
// C-25: agregados cambio_pestana, salida_pantalla_completa, copiar_pegar (compatibles con C-10)
export type TipoEvento =
  | 'rostro_ausente'
  | 'multiples_rostros'
  | 'mirada_desviada_sostenida'
  | 'perdida_de_foco'
  | 'cambio_pestana'
  | 'monitor_adicional'
  | 'salida_pantalla_completa'
  | 'copiar_pegar'
  | 'corte_conectividad_prolongado';

export interface Principal {
  id_institucional: string;
  nombre: string;
  apellido?: string;
  email: string;
  roles: Rol[];
  mfa_satisfecho: boolean;
  jurisdiccion: string;
  /**
   * dataURL JPEG de la foto de perfil (dato personal, Ley 25.326).
   * Finalidad acotada: avatar en la UI. Eliminado al egreso.
   * Demo: en memoria de la sesión. Server-side: cifrado AES-256-GCM.
   */
  foto_perfil?: string;
}

/** Nombre completo "Nombre Apellido" (omite el apellido si no está). */
export function nombreCompleto(p: Principal | null | undefined): string {
  if (!p) return '';
  return [p.nombre, p.apellido].filter(Boolean).join(' ');
}

export interface BloqueConsentimiento {
  titulo: string;
  cuerpo: string;
  icono: string; // material symbol
}

export interface ConsentTextResponse {
  version: string;
  bloques: BloqueConsentimiento[];
  hash_texto: string;
}

export interface ConsentResponse {
  id: string;
  user_id: string;
  exam_id: string;
  version_texto: string;
  timestamp: string;
  hash: string;
}

export interface Examen {
  id: string;
  nombre: string;
  catedra: string;
  estado: 'borrador' | 'programado' | 'en_curso' | 'finalizado';
  inicio: string; // ISO
  duracion_min: number;
  umbral_score: number; // umbral de cola de revisión
  detectores: TipoEvento[];
  retencion_dias: number;
  inscriptos: number;
  rindiendo: number;
}

export interface DesafioActivo {
  /** Legacy ids (C-09) + catálogo secuencial C-54 (`girar_cabeza`, `sonreír`). */
  id: 'girar_izquierda' | 'girar_derecha' | 'parpadear' | 'acercarse' | 'sonreir' | 'girar_cabeza' | 'sonreír';
  label: string;
}

export interface VerifyIdentityResponse {
  veredicto: 'verificado' | 'reintento' | 'escalado';
  distancia: number;
  reintentos_restantes: number;
  clave_sesion_emitida: boolean;
  escalado_a_proctor: boolean;
}

export interface EventoSesion {
  id: string;
  tipo: TipoEvento;
  severidad: Severidad;
  ts_backend: string; // ISO
  descripcion: string;
  tiene_evidencia: boolean;
  evidencia_object_key?: string;
}

// ---------------------------------------------------------------------------
// Gestión de usuarios — C-61
// ---------------------------------------------------------------------------

/** Usuario devuelto por GET/POST/PUT /api/v1/users/. Espeja UsuarioResponse del backend. */
export interface UsuarioAdmin {
  id: string;
  id_institucional: string;
  email: string;
  nombre: string | null;
  apellido: string | null;
  roles: string[];
  auth_provider: string;
}

/** Respuesta paginada de GET /api/v1/users/. */
export interface ListarUsuariosResponse {
  items: UsuarioAdmin[];
  total: number;
  limit: number;
  offset: number;
}

/** Configuracion del peso de score por tipo de evento (#10).
 *  Espeja EventoScoreConfigResponse del backend (presentation/api/v1/scoring). */
export interface EventoScoreConfig {
  tipo_evento: string;
  severidad: string;
  peso: number;
  descripcion: string | null;
  activo: boolean;
  updated_at: string;
}

export interface SesionEnVivo {
  id: string;
  estudiante: string;
  legajo: string;
  estado: 'rindiendo' | 'verificando' | 'escalado' | 'desconectado' | 'finalizado';
  score: number;
  anomalias: number;
  ultima_senal: string;
  foto: string;
  es_propia?: boolean;
}

export interface SesionRevision {
  id: string;
  estudiante: string;
  legajo: string;
  examen: string;
  catedra: string;
  score: number;
  fecha: string;
  duracion: string;
  foto: string;
  decision: 'pendiente' | 'descartada' | 'escalada' | 'derivada';
  eventos: EventoSesion[];
  cadena_custodia: {
    hash_cliente: string;
    rehash_backend: string;
    coincide: boolean;
    firma_maestra: string;
    algoritmo_firma: string;
  };
}

export interface ResumenReportes {
  examenes_totales: number;
  sesiones_totales: number;
  tasa_flag: number; // %
  falsos_positivos: number; // %
  tiempo_medio_revision: string;
  distribucion_severidad: { severidad: Severidad; cantidad: number }[];
  tendencia_semanal: { semana: string; flaggeadas: number; revisadas: number }[];
}

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

// ---------------------------------------------------------------------------
// Acuse por-examen — C-26
// ---------------------------------------------------------------------------

/**
 * Acuse LIVIANO y ESPECÍFICO por (estudiante, examen).
 * Da finalidad/propósito concreto a la instancia de tratamiento (Ley 25.326).
 * NO captura ni re-procesa biometría: referencia el acuse de perfil vigente (C-22).
 *
 * Demo: hash simulado.
 * Server-side: SHA-256 sobre (estudiante, examen, version, alcance_monitoreo, timestamp),
 * firmado por clave maestra (C-12). El cliente es SENSOR NO CONFIABLE.
 */
export interface AcuseExamen {
  /** ID del examen para el que se otorga el acuse. */
  examen_id: string;
  /** Versión del texto de acuse por-examen al momento de la acción afirmativa. */
  version: string;
  /** ISO 8601: momento de la acción afirmativa. */
  timestamp: string;
  /**
   * Hash del acuse (demo: simulado sobre examen_id + version + timestamp).
   * Server-side: SHA-256 firmado por clave maestra (C-12). El sellado definitivo
   * es siempre server-side; el cliente solo genera un placeholder de demo.
   */
  hash: string;
  /** true si el alumno confirmó afirmativamente ESA instancia de tratamiento. */
  afirmativo: boolean;
}

// ---------------------------------------------------------------------------
// Proctoring backend slim — C-46
// Tipos calcados del contrato del backend C-45 (OpenAPI).
// ---------------------------------------------------------------------------

/**
 * Veredicto de re-inferencia del servidor sobre un evento con screenshot.
 * El servidor es la fuente de verdad (cliente = sensor no confiable, L2.5).
 */
export type VeredictoReinferencia = 'coincide' | 'discrepancia' | 'sin_referencia' | 'error';

/**
 * Detalle completo de un evento de proctoring enviado al backend slim.
 * Incluye el veredicto de re-inferencia server-side y face_count del servidor.
 *
 * DATO SENSIBLE (Ley 25.326): screenshot_base64 es dato biométrico/personal;
 * no se loguea en consola ni se persiste en localStorage.
 */
export interface EventoProctoringDetalle {
  evento_id: string;
  tipo: string;
  severidad: string;
  ts_cliente: string; // ISO 8601
  payload?: Record<string, unknown>;
  /** Base64 JPEG del frame capturado en el momento del evento. DATO SENSIBLE. */
  screenshot_base64?: string | null;
  screenshot_sha256?: string | null;
  face_count_cliente?: number | null;
  veredicto_reinferencia?: VeredictoReinferencia | null;
  face_count_servidor?: number | null;
}

/** Resultado de la verificación biométrica de liveness híbrido. */
export interface BiometriaDetalle {
  liveness_ok: boolean;
  retos_resueltos: string[];
  resultado: string;
}

/** Resumen de una sesión de proctoring (para la lista). */
export interface SesionProctoringResumen {
  id: string;
  modo: string; // 'diagnostico' | 'examen' | ...
  etiqueta?: string | null;
  creada_en: string; // ISO 8601
  /**
   * Timestamp de finalización (ISO 8601) o null si la sesión sigue en vivo.
   * Permite a la supervisión en vivo filtrar las cerradas y a "Sesiones
   * grabadas" listarlas todas.
   */
  finalizada_en?: string | null;
  total_eventos: number;
  total_discrepancias: number;
  score: number;
  /**
   * ID del examen del catálogo académico al que pertenece la sesión (opcional).
   * Permite joinear materia/comisión/docente desde el catálogo local.
   * Aditivo: las sesiones de harness sin examen real lo dejan null/undefined.
   */
  exam_id?: string | null;
}

/**
 * Decisión humana de un revisor sobre una sesión de la cola de revisión.
 *
 * El sistema nunca sanciona automáticamente: el score solo prioriza para revisión.
 * La decisión disciplinaria es siempre del revisor humano; la plataforma la registra.
 */
export type DecisionRevisor =
  | 'aprobado'
  | 'flaggeado_para_sumario'
  | 'sin_hallazgos'
  | 'pendiente';

/**
 * Detalle completo de una sesión de proctoring (para la vista de revisión).
 * Extiende SesionProctoringResumen con la lista de eventos y biometría.
 */
export interface SesionProctoringDetalle extends SesionProctoringResumen {
  eventos: EventoProctoringDetalle[];
  biometria: BiometriaDetalle | null;
}

/** Materia/asignatura de la currícula. */
export interface Materia {
  id: string;
  nombre: string;
  codigo: string;
  descripcion: string;
}

/** Comisión: instancia de cursado de una Materia con docente y horario. */
export interface Comision {
  id: string;
  materia_id: string;
  nombre: string;
  docente: string;
  horario: string;
}

/** Inscripción de un alumno a un examen puntual. */
export interface Inscripcion {
  id: string;
  examen_id: string;
  comision_id: string;
  materia_id: string;
  nombre_examen: string;
  nombre_materia: string;
  fecha: string;
  estado: EstadoInscripcion;
}
