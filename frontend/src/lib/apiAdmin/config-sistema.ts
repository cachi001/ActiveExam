// Parte de `adminApi`, partido por dominio (mismo criterio que el refactor c-76
// que saco estos metodos de `api.ts`). Se compone en `../apiAdmin.ts` por spread;
// ningun metodo usa `this`.
import { realFetch } from '../apiCore';

export const configSistemaApi = {
  // -------------------------------------------------------------------------
  // Config efectiva del sistema — configuracion-sistema-funcional (ola 2)
  // -------------------------------------------------------------------------

  /**
   * Config efectiva autoritativa (pesos + umbrales + version/ETag).
   * Accesible a cualquier usuario autenticado.
   * Real: GET /api/v1/config/effective
   * Mock: DEFAULT_CONFIG + pesos hardcodeados demo.
   */
  async obtenerConfigEfectiva(): Promise<{
    version: number;
    face_absent_ms: number;
    multiple_faces_frames: number;
    gaze_deviation_threshold: number;
    gaze_sustained_ms: number;
    gaze_fixation_tolerance: number;
    umbral_cola_revision: number;
    retencion_dias_default: number;
    consent_version_vigente: string;
    detectores_activos: string[];
    scoring_weights: Record<string, number>;
    scoring_severidades: Record<string, string>;
    // C-69 admin-sync: el backend puede no enviarlos aún (en construcción). Opcionales
    // acá; el cache normaliza a `true` (degradación segura) si vienen ausentes.
    chat_habilitado?: boolean;
    pausas_habilitadas?: boolean;
    pausa_max_min?: number;
    // C-76 bloque 4: cantidad máxima de pausas (aprobada+finalizada) por sesión.
    pausas_max_por_sesion?: number;
  }> {
    return await realFetch('/config/effective', { method: 'GET' });
  },

  /**
   * Edita los defaults globales de la config del sistema.
   * SOLO admin_sistema con MFA. Invalida el cache del backend.
   * Real: PATCH /api/v1/config
   * Mock: devuelve la config demo sin cambios reales.
   */
  async editarConfigSistema(body: {
    face_absent_ms?: number;
    multiple_faces_frames?: number;
    gaze_deviation_threshold?: number;
    gaze_sustained_ms?: number;
    gaze_fixation_tolerance?: number;
    umbral_cola_revision?: number;
    detectores_activos?: string[];
    retencion_dias_default?: number;
    consent_version_vigente?: string;
    // C-69 admin-sync: habilitar/deshabilitar el chat proctor↔alumno y las pausas
    // solicitadas por el alumno desde la Configuración del sistema.
    chat_habilitado?: boolean;
    pausas_habilitadas?: boolean;
    pausa_max_min?: number;
    // C-76 bloque 4: cantidad máxima de pausas (aprobada+finalizada) por sesión.
    pausas_max_por_sesion?: number;
  }): Promise<{
    version: number;
    face_absent_ms: number;
    multiple_faces_frames: number;
    gaze_deviation_threshold: number;
    gaze_sustained_ms: number;
    gaze_fixation_tolerance: number;
    umbral_cola_revision: number;
    retencion_dias_default: number;
    consent_version_vigente: string;
    detectores_activos: string[];
    scoring_weights: Record<string, number>;
    chat_habilitado?: boolean;
    pausas_habilitadas?: boolean;
  }> {
    return await realFetch('/config', { method: 'PATCH', body: JSON.stringify(body) });
  },
};
