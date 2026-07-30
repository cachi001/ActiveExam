// Parte de `adminApi`, partido por dominio (mismo criterio que el refactor c-76
// que saco estos metodos de `api.ts`). Se compone en `../apiAdmin.ts` por spread;
// ningun metodo usa `this`.
import { realFetch } from '../apiCore';

export const moodleApi = {
  // -------------------------------------------------------------------------
  // Credencial de servicio de Moodle (token cifrado en la base)
  // -------------------------------------------------------------------------

  /**
   * Estado de la credencial de Moodle. El token NUNCA viaja: solo si está
   * configurado y sus últimos 4 caracteres, para reconocer cuál se cargó.
   * Real: GET /api/v1/config/moodle  (solo admin_sistema)
   */
  async obtenerCredencialMoodle(): Promise<CredencialMoodle> {
    return await realFetch('/config/moodle', { method: 'GET' });
  },

  /**
   * Guarda la credencial. Omitir `token` deja el guardado intacto (permite
   * corregir el curso o la actividad sin volver a tipear el secreto).
   * Real: PUT /api/v1/config/moodle
   */
  async guardarCredencialMoodle(body: {
    service_shortname?: string;
    base_url?: string;
    token?: string;
    component?: 'mod_assign' | 'mod_quiz';
  }): Promise<CredencialMoodle> {
    return await realFetch('/config/moodle', { method: 'PUT', body: JSON.stringify(body) });
  },

  /** Borra el token guardado. Real: DELETE /api/v1/config/moodle/token */
  async borrarTokenMoodle(): Promise<CredencialMoodle> {
    return await realFetch('/config/moodle/token', { method: 'DELETE' });
  },

  // --- Cuenta del campus del DOCENTE (C-73 §10.3) -------------------------
  // Cada uno gestiona SOLO la suya: el backend toma el usuario del token, no de
  // la URL. No existe endpoint para tocar la de otro.

  /** Estado de MI cuenta del campus. Real: GET /config/moodle/mi-credencial */
  async obtenerMiCuentaCampus(): Promise<MiCuentaCampus> {
    return await realFetch('/config/moodle/mi-credencial', { method: 'GET' });
  },

  /**
   * Conecta MI cuenta del campus. Real: PUT /config/moodle/mi-credencial
   *
   * Se manda la contraseña (que el backend canjea por un token y descarta) O un
   * token ya emitido por el admin del campus. Nunca las dos.
   * `base_url` es la URL del campus que eligió el docente; si se omite el backend
   * usa la institucional como fallback.
   */
  async guardarMiCuentaCampus(body: {
    moodle_username: string;
    password?: string;
    token?: string;
    base_url?: string;
  }): Promise<MiCuentaCampus> {
    return await realFetch('/config/moodle/mi-credencial', {
      method: 'PUT',
      body: JSON.stringify(body),
    });
  },

  /** Desconecta MI cuenta. Real: DELETE /config/moodle/mi-credencial */
  async desconectarMiCuentaCampus(): Promise<MiCuentaCampus> {
    return await realFetch('/config/moodle/mi-credencial', { method: 'DELETE' });
  },

  /** Asigna (o quita, con null) el docente a cargo de una comisión. C-73 §9.5 */
  async asignarDocenteComision(
    comisionId: string,
    docenteId: string | null,
  ): Promise<{ docente_id: string | null; docente_nombre: string | null }> {
    return await realFetch(`/exam-content/comisiones/${comisionId}/docente`, {
      method: 'PUT',
      body: JSON.stringify({ docente_id: docenteId }),
    });
  },
};

/** Estado de MI cuenta del campus (el token NUNCA viaja). */
export interface MiCuentaCampus {
  configurada: boolean;
  moodle_username: string | null;
  /** Últimos 4 caracteres, para reconocer cuál cargué. */
  token_pista: string | null;
  /** 'activa' | 'caida'. `caida` = el campus rechazó el token: hay que recargarlo. */
  estado: string | null;
  actualizado_en: string | null;
  ultimo_uso_en: string | null;
  /** URL del campus (per-docente desde 0051; fallback institucional si aún no configuró). */
  base_url: string;
}

/** Estado de la credencial de Moodle tal como lo expone la API (SIN el token). */
export interface CredencialMoodle {
  base_url: string;
  /** Tipo de actividad por defecto. El DESTINO (curso + actividad) es de cada examen. */
  component: 'mod_assign' | 'mod_quiz';
  /** True si hay un token utilizable (guardado en la base o heredado del entorno). */
  token_configurado: boolean;
  /** Últimos 4 caracteres del token guardado. null si viene del entorno. */
  token_pista: string | null;
  /** 'db' | 'env' | 'sin_configurar'. */
  origen: string;
  actualizado_en: string | null;
  actualizado_por: string | null;
  /** Nombre del servicio externo del campus. Sin esto ningún docente puede conectarse. */
  service_shortname: string;
}
