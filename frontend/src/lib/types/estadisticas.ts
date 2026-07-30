/**
 * Estadisticas institucionales agregadas (C-20).
 *
 * Se re-exporta desde `lib/types.ts`: importa siempre desde ahi.
 */

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

export interface ComisionStat {
  comision_id: string;
  nombre: string;
  sesiones: number;
  en_riesgo: number;
}

export interface EventoStat {
  tipo: string;
  cantidad: number;
}

/** Padrón de inscriptos y su habilitación para PODER RENDIR (consentimiento + biometría). */
export interface ElegibilidadStats {
  total_inscriptos: number;
  con_consentimiento: number;
  sin_consentimiento: number;
  con_biometria: number;
  sin_biometria: number;
  pueden_rendir: number;
  no_pueden_rendir: number;
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
  por_comision?: ComisionStat[];
  top_eventos?: EventoStat[];
  por_dia?: DiaStat[];
  decisiones?: Record<string, number>;
  elegibilidad?: ElegibilidadStats;
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
  accion: string;          // detalle dot-notation (user.create, materia.delete…)
  tipo_accion: string | null; // CREAR / EDITAR / ELIMINAR / CAMBIO_ESTADO
  modulo: string | null;      // USUARIOS / MATERIAS / EXAMENES / …
  entidad: string | null;     // USUARIO / EXAMEN / SESION / …
  entidad_id: string | null;  // UUID de la entidad afectada
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
  modulo?: string;
  tipo_accion?: string;
  accion?: string;  // búsqueda libre en el detalle dot-notation
  desde?: string;   // ISO
  hasta?: string;   // ISO
}
