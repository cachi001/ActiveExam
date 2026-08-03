/**
 * Eventos de proctoring, sesiones y scoring. Es el nucleo del dominio.
 *
 * Se re-exporta desde `lib/types.ts`: importa siempre desde ahi.
 */

// Tipos de dominio del MVP ActiveExam. Calcados de los schemas del backend
// (app/presentation/api/v1/*). Nombres y enums en español, igual que la API real.

// Roles del sistema. ESPEJA EXACTAMENTE el enum `Rol` del backend
// (app/domain/auth/roles.py) — es la MISMA lista, no un subconjunto.
//
// Antes esto declaraba un "modelo MVP de 3 roles" mientras el backend ya tenía 7.
// La consecuencia no era cosmética: el backend reserva `revisar_sesion` (decidir
// en un solo paso, incluida la anulación) al rol `revisor`, pero el frontend ni
// siquiera conocía ese rol, así que la ruta /revisor lo rechazaba con "Sin
// permisos" — nadie podía anular un examen por fraude. Si el backend agrega un
// rol, va acá también.
export type Rol =
  | 'estudiante'
  | 'proctor'
  | 'revisor'
  | 'coordinador'
  | 'docente'
  | 'admin_examenes'
  | 'admin_sistema'
  | 'auditor';

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
  /** C-71 slice 2 (D11b/D12): veredicto de la decisión, visto por PULL. */
  session_id?: string;
  /** true si la nota fue anulada (efecto derivado del último acto). */
  nota_anulada?: boolean;
  /** 'anulado' cuando la nota fue anulada; si no, null. */
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

