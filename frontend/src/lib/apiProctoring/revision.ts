// Revision humana y administracion de sesiones.
// Parte de `proctoringApi`, partido por dominio (mismo criterio que el refactor
// c-76 que saco estos metodos de `api.ts`). Se compone en `../apiProctoring.ts`
// por spread; ningun metodo usa `this`.
import { realFetch, API_BASE } from '../apiCore';
import { authProvider } from '../authProvider';
import type {
  DecisionSesion, SesionProctoringDetalle,
} from '../types';

export const revisionApi = {
  /**
   * Registra la decisión TERMINAL sobre una sesión, en un solo acto (capacidad
   * `revisar_sesion`). Real: POST /review/session/{id}/decide → 200; 409 si ya
   * había decisión (inmutable). `motivo` obligatorio no vacío y `evidenciaIds`
   * (al menos un event_id) obligatorio cuando `decision === 'anulado'` (D11).
   * No hay una segunda instancia de resolución: quien revisa decide.
   */
  async decidirSesion(
    sessionId: string,
    decision: DecisionSesion,
    motivo: string,
    evidenciaIds: string[] = [],
  ): Promise<{
    session_id: string; previous: string; new: string; actor: string;
    decision_at: string; nota_anulada: boolean; nota_anulada_en_moodle: boolean | null;
  }> {
    return await realFetch(
      `/review/session/${sessionId}/decide`,
      {
        method: 'POST',
        body: JSON.stringify({ decision, motivo, evidencia_ids: evidenciaIds }),
      },
    );
  },

  /**
   * Obtiene el detalle completo de una sesión de proctoring (C-46).
   * Real: GET /proctoring/sessions/{id}
   *
   * DATO SENSIBLE (Ley 25.326): screenshot_base64 en los eventos — no loguear.
   */
  async getSesionProctoring(id: string): Promise<SesionProctoringDetalle> {
    return await realFetch<SesionProctoringDetalle>(
      `/proctoring/sessions/${id}`,
      { method: 'GET' },
      'demo',
    );
  },

  /**
   * Elimina una sesión de proctoring (C-46). Real: DELETE /proctoring/sessions/{id} (204).
   * Fallo de red: retorna { ok:false } sin romper.
   */
  async eliminarSesionProctoring(id: string): Promise<{ ok: boolean }> {
    try {
      const token = authProvider.getToken();
      const res = await fetch(`${API_BASE}/proctoring/sessions/${id}`, {
        method: 'DELETE',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      return { ok: res.ok };
    } catch {
      return { ok: false };
    }
  },
};
