// Parte de `adminApi`, partido por dominio. Allowlist LTI: los campus Moodle
// habilitados a mandar alumnos a ActiveExam (c-78 §10.1-10.3).
//
// Cada fila es la RAÍZ DE CONFIANZA de un campus: mientras esté inactiva, ningún
// launch de ese Moodle entra. Por eso el registro dinámico crea la fila apagada y
// habilitarla es siempre un acto humano — esta API es lo que la pantalla usa para
// hacerlo sin tener que armar requests a mano.
import { realFetch } from '../apiCore';

/** Un campus registrado en la allowlist LTI. */
export interface DeploymentLti {
  id: string;
  /** URL del Moodle (claim `iss` del LTI). */
  iss: string;
  deployment_id: string;
  client_id: string;
  jwks_uri: string;
  context_id: string | null;
  comision_id: string | null;
  /** false = registrado pero NO habilitado: sus launches se rechazan. */
  activo: boolean;
  creado_en: string;
}

/** Estado general de la integración, en lenguaje entendible. */
export interface SaludLti {
  deployments_activos: number;
  deployments_totales: number;
  allowlist_vacia: boolean;
  mensaje: string;
}

export const ltiApi = {
  /**
   * Estado de la allowlist: cuántos campus hay y cuántos habilitados.
   * Real: GET /api/v1/admin/lti/salud
   */
  async saludLti(): Promise<SaludLti> {
    return await realFetch('/admin/lti/salud', { method: 'GET' });
  },

  /**
   * Lista los campus registrados (habilitados y no).
   * Real: GET /api/v1/admin/lti/deployments
   */
  async listarDeploymentsLti(): Promise<DeploymentLti[]> {
    return await realFetch('/admin/lti/deployments', { method: 'GET' });
  },

  /**
   * Habilita o deshabilita un campus. Deshabilitar corta el acceso de TODOS sus
   * alumnos de inmediato, así que la pantalla lo pide confirmado.
   * Real: PATCH /api/v1/admin/lti/deployments/{id}
   */
  async setActivoDeploymentLti(id: string, activo: boolean): Promise<DeploymentLti> {
    return await realFetch(`/admin/lti/deployments/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify({ activo }),
    });
  },

  /**
   * Asocia (o desasocia con null) un campus a una comisión: los alumnos que
   * entren desde ahí quedan matriculados en esa comisión automáticamente.
   * Real: PATCH /api/v1/admin/lti/deployments/{id}
   */
  async setComisionDeploymentLti(
    id: string,
    comisionId: string | null,
  ): Promise<DeploymentLti> {
    return await realFetch(`/admin/lti/deployments/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify({ comision_id: comisionId }),
    });
  },

  /**
   * Borra un registro de la allowlist.
   * Real: DELETE /api/v1/admin/lti/deployments/{id}
   */
  async borrarDeploymentLti(id: string): Promise<void> {
    await realFetch(`/admin/lti/deployments/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    });
  },
};
