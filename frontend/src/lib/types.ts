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
  | 'corte_conectividad_prolongado'
  // C-72: reapertura de la rendición (emitidos server-side al reanudar).
  | 'recarga_pagina'
  | 'reanudacion_tardia';

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
  /**
   * C-69: ID del ExamenContenido (preguntas/opciones importadas de Moodle XML).
   * Null cuando el examen de proctoring no tiene contenido asociado todavía.
   * El frontend usa este ID para llamar a GET /api/v1/exam-content/{examen_contenido_id}.
   */
  examen_contenido_id?: string | null;
}

/**
 * C-69: Resumen de un examen de contenido para el catálogo del alumno.
 * Read-model liviano: solo metadatos (id, titulo, cantidad_preguntas).
 * D3: es_correcta NUNCA presente — aplica al detalle y al listado.
 */
export interface ExamenContenidoResumen {
  id: string;
  titulo: string;
  cantidad_preguntas: number;
  /** Comisión/materia asociadas (D11, NULLABLE): null si el examen no tiene comisión. */
  comision_id?: string | null;
  comision_nombre?: string | null;
  materia_nombre?: string | null;
  /** Config aplicada por la plataforma: ventana de rendición (ISO 8601, nullable). */
  apertura?: string | null;
  cierre?: string | null;
  /** Minutos de tiempo límite. null = sin límite. */
  tiempo_limite_min?: number | null;
  /** Intentos permitidos por alumno. */
  intentos_permitidos?: number | null;
}

/**
 * C-69: nota académica de un examen rendido por el alumno, con estado de la cola
 * de revisión por eventos de proctoring. La fuente de verdad es el backend
 * (GET /api/v1/exam-content/mis-notas); el cliente solo la muestra.
 */
export interface NotaExamen {
  examen_id: string;
  examen_titulo: string;
  /** Nota académica calculada server-side. null si aún no se computó. */
  nota: number | null;
  /** Estado del write-back a Moodle (ej. 'pendiente' | 'sincronizada' | 'error'). */
  estado_moodle: string | null;
  /** true si el score de proctoring superó el umbral → en cola de revisión humana. */
  en_cola_revision: boolean;
  /** Score de prioridad de proctoring. */
  score: number | null;
  /** Umbral de cola de revisión vigente. */
  umbral_revision: number | null;
  /** Cantidad de eventos registrados durante la supervisión. */
  eventos: number | null;
  /** ISO 8601: momento de finalización de la rendición. */
  finalizada_en: string | null;
  /** Nota máxima de la escala configurada (ej. 10 o 100). Para mostrar "X / max". */
  nota_maxima?: number | null;
  /** true si la nota alcanza la nota de aprobación (decidido server-side). */
  aprobado?: boolean | null;
  /** C-69: si la nota ya se puede mostrar. Si false, `nota` viene null y se muestra
   *  "disponible al cerrar el examen (cierre)". */
  nota_visible?: boolean;
  /** C-69: si la revisión (respuestas correctas) está disponible ahora. */
  revision_disponible?: boolean;
  /** C-69: ISO de la fecha de cierre del examen (para el mensaje de disponibilidad). */
  cierre?: string | null;
  /** C-71 slice 2 (D11b/D12): veredicto de resolución, visto por PULL. */
  session_id?: string;
  /** true si la nota fue anulada por fraude (efecto derivado del último acto). */
  nota_anulada?: boolean;
  /** 'anulado_por_fraude' cuando la nota fue anulada; si no, null. */
  veredicto?: string | null;
  /** true SOLO si la nota fue anulada por fraude → habilita el informe de devolución. */
  informe_disponible?: boolean;
}

/** C-69: respuesta paginada del endpoint de notas del alumno. */
export interface MisNotasResponse {
  items: NotaExamen[];
  total: number;
}

/**
 * C-69: revisión post-examen. A DIFERENCIA de la rendición, acá SÍ viaja
 * `es_correcta` (excepción a D3: solo el dueño, solo con el intento finalizado —
 * como las "Review options" de Moodle). Read-only, para que el alumno vea su
 * corrección.
 */
export interface OpcionRevision {
  id: string;
  texto: string;
  orden: number;
  es_correcta: boolean;
  /** true si el alumno eligió esta opción. */
  elegida: boolean;
}

export interface PreguntaRevision {
  id: string;
  enunciado: string;
  orden: number;
  opciones: OpcionRevision[];
  /** true si el alumno respondió (eligió alguna opción). */
  respondida: boolean;
  /** true si eligió la correcta. */
  acertada: boolean;
}

export interface RevisionExamen {
  examen_id: string;
  titulo: string;
  nota: number | null;
  nota_maxima: number | null;
  aprobado: boolean;
  total_preguntas: number;
  correctas: number;
  incorrectas: number;
  sin_responder: number;
  finalizada_en: string | null;
  preguntas: PreguntaRevision[];
  /** C-69: si false, la NOTA aún no es visible (sin resultados hasta el cierre). */
  disponible?: boolean;
  /** C-69: si false, van los contadores pero NO el detalle pregunta-por-pregunta. */
  revision_disponible?: boolean;
  /** C-69: ISO de la fecha de cierre del examen (para el mensaje de disponibilidad). */
  cierre?: string | null;
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
  /** null = activo; ISO string = dado de baja (soft-delete). */
  eliminado_en?: string | null;
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
  // C-71 slice 2: modelo de decisión unificado (dos fases, sin `escalada`).
  decision: DecisionRevisor;
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
  /**
   * true si el evento ocurrió durante una pausa autorizada (C-15). Estos eventos
   * NO suman al score (el backend ya los excluye del cálculo); la UI los marca con
   * un badge informativo para que el revisor sepa que están contextualizados.
   */
  en_pausa_autorizada?: boolean;
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
  /**
   * Timestamp del último evento (ISO 8601). En ausencia de eventos = creada_en.
   * La UI lo usa para distinguir actividad reciente de calma/abandono.
   */
  ultimo_evento_en?: string | null;
  total_eventos: number;
  total_discrepancias: number;
  score: number;
  /**
   * ID del examen del catálogo académico al que pertenece la sesión (opcional).
   * Permite joinear materia/comisión/docente desde el catálogo local.
   * Aditivo: las sesiones de harness sin examen real lo dejan null/undefined.
   */
  exam_id?: string | null;
  /**
   * Contexto académico resuelto SERVER-SIDE (examen_contenido → comisión → materia).
   * Se prefiere sobre el catálogo mock del frontend: un examen importado real vive en
   * la base, no en los arrays de api.ts. NULL si la sesión no tiene contenido vinculado
   * o el examen no está asociado a comisión/materia.
   */
  examen_contenido_id?: string | null;
  examen_titulo?: string | null;
  comision_nombre?: string | null;
  materia_nombre?: string | null;
}

/**
 * Modelo de decisión de DOS FASES (C-71 slice 2, D6/D7) — espeja el backend.
 * `escalada` fue DROPEADA (sin downstream); "escalar a otra autoridad" se cubre
 * por la separación de capacidad (resolver_caso).
 *
 * El sistema nunca sanciona automáticamente: el score solo prioriza para revisión.
 * La decisión es siempre humana; la plataforma la registra de forma inmutable.
 */

/** Fase 1 — Revisión (capacidad `revisar_sesion`). Terminal de la revisión. */
export type DecisionRevision =
  | 'sin_hallazgos'   // falso positivo; valida la nota
  | 'aprobado'        // revisado, legítimo; valida la nota
  | 'caso_abierto';   // derivación: hay algo que resolver (habilita la fase 2)

/** Fase 2 — Resolución (capacidad `resolver_caso`). Solo si el caso está abierto. */
export type DecisionResolucion =
  | 'anulado_por_fraude'  // anula la nota (reversible por acto compensatorio)
  | 'caso_descartado';    // cierra el caso validando la nota

/**
 * Unión de todas las decisiones humanas posibles (dos fases) + estado inicial.
 * Reemplaza el modelo plano anterior (aprobado/flaggeado_para_sumario/…), cerrando
 * el gap con el backend.
 */
export type DecisionRevisor = DecisionRevision | DecisionResolucion | 'pendiente';

/** Etiquetas legibles derivadas de los valores del backend (fase 1). */
export const DECISION_REVISION_LABEL: Record<DecisionRevision, string> = {
  sin_hallazgos: 'Sin observaciones',
  aprobado: 'Aprobada con nota',
  caso_abierto: 'Abrir caso (derivar)',
};

/** Etiquetas legibles derivadas de los valores del backend (fase 2). */
export const DECISION_RESOLUCION_LABEL: Record<DecisionResolucion, string> = {
  anulado_por_fraude: 'Anular la nota por fraude',
  caso_descartado: 'Descartar el caso',
};

/**
 * Informe de devolución del alumno (C-71 slice 2, D12). Solo existe cuando la
 * nota fue anulada por fraude (minimización, Ley 25.326).
 */
export interface SenalAnalisis {
  tipo: string;
  severidad: string;
  ocurrencias: number;
  face_count_servidor?: number | null;
  veredicto_reinferencia: string;
}

export interface CapturaFirmada {
  object_key: string;
  url: string;
  expires_in: number;
}

export interface InformeDevolucion {
  session_id: string;
  decision: string;
  resolucion: string;
  motivo?: string | null;
  senales: SenalAnalisis[];
  capturas: CapturaFirmada[];
}

/**
 * Detalle completo de una sesión de proctoring (para la vista de revisión).
 * Extiende SesionProctoringResumen con la lista de eventos y biometría.
 */
export interface SesionProctoringDetalle extends SesionProctoringResumen {
  eventos: EventoProctoringDetalle[];
  biometria: BiometriaDetalle | null;
  // C-15 (3.3): cierre forzado (operativo, NO disciplinario). NULL si la sesión no
  // fue cerrada de forma forzada. Permite reflejar el estado al recargar el detalle.
  cierre_forzado_en?: string | null;
  cierre_forzado_motivo?: string | null;
}

// ── Chat bidireccional proctor↔alumno (C-15) ──────────────────────────────

/** Autor de un mensaje de chat de la sesión. */
export type AutorChat = 'alumno' | 'proctor';

/** Un mensaje del canal de chat de una sesión de proctoring. */
export interface MensajeChat {
  id: string;
  autor: AutorChat;
  texto: string;
  creado_en: string; // ISO 8601
}

// ── Pausa autorizada (C-15) ───────────────────────────────────────────────

/**
 * Estado del ciclo de vida de una solicitud de pausa.
 * `expirada`: el sistema la cerró por timeout o al finalizar la sesión sin que el
 * proctor la respondiera (C-72 sección 12). NO es aprobación ni rechazo (L2.5).
 */
export type EstadoPausa = 'solicitada' | 'aprobada' | 'rechazada' | 'finalizada' | 'expirada';

/** Acción del proctor al resolver una pausa solicitada. */
export type AccionPausa = 'aprobar' | 'rechazar';

/** Una pausa autorizada de una sesión (vista del alumno / detalle). */
export interface Pausa {
  id: string;
  motivo: string;
  estado: EstadoPausa;
  solicitada_en: string; // ISO 8601
  resuelta_en?: string | null;
  proctor_actor?: string | null;
  /** Motivo que el proctor da al RECHAZAR la pausa; se muestra al alumno. */
  motivo_rechazo?: string | null;
  inicio_en?: string | null;
  fin_en?: string | null;
}

/** Entrada de la cola de pausas pendientes (poll del proctor a nivel panel). */
export interface PausaPendiente {
  id: string;
  session_id: string;
  etiqueta?: string | null;
  motivo: string;
  solicitada_en: string; // ISO 8601
}

/**
 * Observación libre del proctor sobre una sesión (C-15 3.2). Múltiples por sesión,
 * append-only. Insumo de la revisión humana (C-16). NO sanciona ni exime (L2.5).
 */
export interface ObservacionProctor {
  id: string;
  texto: string;
  proctor_actor?: string | null;
  creada_en: string; // ISO 8601
}

/**
 * Resultado del cierre FORZADO de una sesión por el proctor (C-15 3.3).
 * Operativo, NO disciplinario (L2.5). El audit trail vive en la propia fila.
 */
export interface CierreForzado {
  id: string;
  finalizada_en: string;
  cierre_forzado_en: string;
  cierre_forzado_por?: string | null;
  cierre_forzado_motivo?: string | null;
}

/** Materia/asignatura de la currícula.
 *
 * `descripcion` es opcional: el backend real (C-69) sólo expone id/codigo/nombre;
 * los datos demo la incluyen. */
export interface Materia {
  id: string;
  nombre: string;
  codigo: string;
  descripcion?: string;
  // C-72 §17: estado de la materia (true = activa; false = congelada). Opcional
  // por compat con respuestas viejas; se asume activa si no viene.
  activa?: boolean;
}

/** Comisión: instancia de cursado de una Materia.
 *
 * `docente`/`horario` son del modelo demo (C-21). El backend real (C-69) expone
 * `codigo`/`periodo`/`anio`; todos opcionales para soportar ambas fuentes. */
export interface Comision {
  id: string;
  materia_id: string;
  nombre: string;
  docente?: string;
  horario?: string;
  codigo?: string;
  periodo?: string | null;
  anio?: number | null;
  // C-70: código de matriculación (enrolment key) que el alumno usa para unirse.
  codigo_matriculacion?: string;
}

/** Alumno inscripto a una comisión, con su estado de elegibilidad para rendir
 *  (C-69). Espeja el item de GET /exam-content/comisiones/{id}/alumnos del
 *  backend: el `puede_rendir` lo decide el servidor combinando consentimiento +
 *  biometría vigentes; `razon` explica el motivo cuando no puede rendir. */
export interface AlumnoInscripto {
  usuario_id: string;
  id_institucional: string;
  nombre: string | null;
  apellido: string | null;
  email: string;
  consentimiento_vigente: boolean;
  biometria_vigente: boolean;
  puede_rendir: boolean;
  razon: string | null;
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

// ---------------------------------------------------------------------------
// Estadísticas institucionales agregadas — C-20 (GET /stats/resumen)
// ---------------------------------------------------------------------------

/**
 * Sumario institucional agregado (sin PII). Espeja `ResumenStatsResponse` del
 * backend (app/presentation/api/v1/stats/router.py). L2.5: `sesiones_en_riesgo`
 * es una SEÑAL DE PRIORIZACIÓN para la revisión humana, NUNCA un veredicto.
 * `distribucion_scores` mapea el label del bucket → cantidad de sesiones.
 */
export interface MateriaStat {
  materia_id: string;
  nombre: string;
  sesiones: number;
  en_riesgo: number;
}

export interface EventoStat {
  tipo: string;
  cantidad: number;
}

export interface DiaStat {
  fecha: string; // YYYY-MM-DD
  sesiones: number;
}

export interface ResumenStats {
  total_examenes: number;
  total_materias: number;
  total_comisiones: number;
  total_sesiones: number;
  sesiones_finalizadas: number;
  sesiones_en_riesgo: number;
  umbral_riesgo: number;
  distribucion_scores: Record<string, number>;
  // Desgloses (C-20 ampliado). Opcionales por compat con el contrato de carga
  // resiliente y los tests que arman ResumenStats a mano; el backend real siempre
  // los envía. La UI degrada a lista/mapa vacío si faltan.
  por_materia?: MateriaStat[];
  top_eventos?: EventoStat[];
  por_dia?: DiaStat[];
  decisiones?: Record<string, number>;
}

/** Filtros de la vista de estadísticas (query params del backend). */
export interface FiltrosStats {
  materia_id?: string;
  comision_id?: string;
  examen_id?: string;
  desde?: string; // ISO
  hasta?: string; // ISO
}

// Auditoría (C-20) — registro de actividad (GET /admin/audit-log)
export interface AuditEvento {
  id: string;
  actor: string;
  /** "Nombre Apellido" resuelto del usuario (null si no se pudo resolver). */
  actor_nombre: string | null;
  accion: string;
  timestamp: string;
  ip: string | null;
  user_agent: string | null;
  proposito: string | null;
}

export interface AuditLogResponse {
  items: AuditEvento[];
  total: number;
  limit: number;
  offset: number;
  /** La cadena de custodia (hash encadenado) sigue íntegra. */
  cadena_valida: boolean;
}

export interface AuditFiltros {
  actor?: string;
  accion?: string;
  desde?: string; // ISO
  hasta?: string; // ISO
}
