/**
 * Gestion de usuarios (C-61).
 *
 * Se re-exporta desde `lib/types.ts`: importa siempre desde ahi.
 */

import type { DecisionRevisor } from './proctoring-slim';
import type { EventoSesion, Severidad } from './proctoring-eventos';

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
  /** Solo presente en POST cuando el admin no proveyó contraseña: la temporal generada. */
  password_generada?: string | null;
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
  // C-71 slice 2: modelo de decisión de UN SOLO PASO (aprobado | anulado | pendiente).
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

