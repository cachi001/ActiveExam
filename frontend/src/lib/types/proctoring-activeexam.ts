/**
 * Contrato del backend slim de proctoring (C-46). Calcado del OpenAPI de C-45.
 *
 * Se re-exporta desde `lib/types.ts`: importa siempre desde ahi.
 */

import type { EstadoInscripcion } from './alumno';

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
 * Modelo de decisión de UN SOLO PASO (C-71 slice 2, colapsado) — espeja el
 * backend. El modelo de dos fases (con `caso_abierto` como derivación a una
 * segunda instancia de resolución) fue rechazado explícitamente por el owner
 * del proyecto: quien revisa decide, en el mismo acto, sin segunda instancia.
 *
 * El sistema nunca sanciona automáticamente: el score solo prioriza para revisión.
 * La decisión es siempre humana; la plataforma la registra de forma inmutable.
 */

/** Decisión terminal (capacidad `revisar_sesion`), un solo acto. */
export type DecisionSesion =
  | 'aprobado'  // falso positivo o no amerita sanción; valida la nota
  | 'anulado';  // fraude determinado en el mismo acto; anula la nota (evidencia obligatoria)

/** Unión con el estado inicial. */
export type DecisionRevisor = DecisionSesion | 'pendiente';

/** Etiquetas legibles derivadas de los valores del backend. */
export const DECISION_SESION_LABEL: Record<DecisionSesion, string> = {
  aprobado: 'Aprobar (valida la nota)',
  anulado: 'Anular la nota por fraude',
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
  /** De qué señal salió la captura (código del evento; se muestra traducido). */
  tipo_evento?: string | null;
  severidad?: string | null;
  /** Momento del evento, para ubicar la captura en la línea de tiempo. */
  ocurrio_en?: string | null;
}

export interface InformeDevolucion {
  session_id: string;
  decision: string;
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
  // Conteos para ocultar "Eliminar" si la materia NO está vacía (staff). Opcionales
  // por compat; ausentes = 0 (no bloquea).
  total_inscriptos?: number;
  total_examenes?: number;
  // C-73 §9: docente a cargo. Es quien devuelve las notas de esta comisión al campus
  // con SU cuenta. Sin docente asignado las notas quedan retenidas.
  docente_id?: string | null;
  docente_nombre?: string | null;
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
  // C-72 §17: false = comisión desactivada (baja lógica). No admite inscripciones
  // nuevas ni iniciar sus exámenes; los ya inscriptos conservan su acceso.
  activa?: boolean;
  // Conteos para ocultar "Eliminar" si la comisión NO está vacía (staff). Opcionales
  // por compat; ausentes = 0 (no bloquea).
  total_inscriptos?: number;
  total_examenes?: number;
  // C-73 §9: docente a cargo. Es quien devuelve las notas de esta comisión al campus
  // con SU cuenta. Sin docente asignado las notas quedan retenidas.
  docente_id?: string | null;
  docente_nombre?: string | null;
}

/** Comisión + su materia embebida (GET /exam-content/comisiones, todas). Para un
 * selector combinado único ("CÓDIGO - Materia") que no requiere elegir materia
 * primero — reemplaza el patrón de dos selects encadenados. */
export interface ComisionConMateria {
  id: string;
  codigo: string;
  nombre: string;
  periodo?: string | null;
  anio?: number | null;
  materia_id: string;
  materia_nombre: string;
  materia_codigo: string;
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

