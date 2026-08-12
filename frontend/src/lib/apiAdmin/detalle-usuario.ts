// Parte de `adminApi`, partido por dominio (mismo criterio que el refactor c-76
// que saco estos metodos de `api.ts`). Se compone en `../apiAdmin.ts` por spread;
// ningun metodo usa `this`.
import { realFetch } from '../apiCore';
import type {
  UsuarioAdmin,
} from '../types';

export const detalleUsuarioApi = {
  // -------------------------------------------------------------------------
  // Detalle de usuario (admin) — C-68
  // -------------------------------------------------------------------------

  /**
   * Detalle completo de un usuario (admin_sistema) — C-68.
   * Real: GET /users/{id}
   * Mock: busca en el listado demo.
   */
  async obtenerDetalleUsuario(id: string): Promise<UsuarioAdmin & { eliminado_en?: string | null }> {
    return await realFetch<UsuarioAdmin & { eliminado_en?: string | null }>(
      `/users/${id}`,
      { method: 'GET' },
    );
  },

  /**
   * Habilita al alumno a rehacer su referencia biométrica UNA vez (admin_sistema).
   * El alumno no puede rehacerla mientras esté vigente; esto lo destraba. El flag
   * se consume automáticamente cuando el alumno guarda la nueva referencia.
   * Real: POST /users/{id}/habilitar-rehacer-biometria
   */
  async habilitarRehacerBiometria(id: string): Promise<void> {
    await realFetch<{ biometria_rehacer_habilitada: boolean }>(
      `/users/${id}/habilitar-rehacer-biometria`,
      { method: 'POST' },
    );
  },

  /**
   * Consentimiento de perfil de un usuario específico (admin_sistema) — C-68.
   * Real: GET /users/{id}/consent-profile
   * Mock: estado simulado con datos plausibles.
   */
  async obtenerConsentimientoDeUsuario(id: string): Promise<{
    estado: 'otorgado' | 'revocado' | null;
    version_texto: string | null;
    hash_texto: string | null;
    timestamp: string | null;
  }> {
    return await realFetch<{
      estado: 'otorgado' | 'revocado' | null;
      version_texto: string | null;
      hash_texto: string | null;
      timestamp: string | null;
    }>(`/users/${id}/consent-profile`, { method: 'GET' });
  },

  /**
   * Estado de la referencia biométrica de un usuario específico (admin_sistema) — C-68.
   * Real: GET /users/{id}/biometria/referencia/estado
   * Mock: estado simulado.
   */
  async obtenerEstadoBiometriaDeUsuario(id: string): Promise<{
    tiene_referencia_vigente: boolean;
    algoritmo: string | null;
    fecha_expiracion: string | null;
    created_at: string | null;
    tiene_foto: boolean;
    foto_hash: string | null;
    foto_created_at: string | null;
  }> {
    return await realFetch<{
      tiene_referencia_vigente: boolean;
      algoritmo: string | null;
      fecha_expiracion: string | null;
      created_at: string | null;
      tiene_foto: boolean;
      foto_hash: string | null;
      foto_created_at: string | null;
    }>(`/users/${id}/biometria/referencia/estado`, { method: 'GET' });
  },
};
