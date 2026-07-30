// Revision humana y administracion de sesiones.
// Parte de `proctoringApi`, partido por dominio (mismo criterio que el refactor
// c-76 que saco estos metodos de `api.ts`). Se compone en `../apiProctoring.ts`
// por spread; ningun metodo usa `this`.
import { realFetch, API_BASE } from '../apiCore';
import { authProvider } from '../authProvider';
import type {
  DecisionRevision, DecisionResolucion, SesionProctoringDetalle,
} from '../types';

export const revisionApi = {
  /**
   * Registra la decisión de REVISIÓN (fase 1) sobre una sesión (capacidad `revisar_sesion`).
   * Real: POST /review/session/{id}/decide → 200; 409 si ya había decisión (inmutable).
   * El `motivo` viaja como `observaciones`: el fundamento queda en el audit inmutable.
   * `caso_abierto` deriva a la fase 2 (no valida ni anula la nota).
   */
  async decidirRevision(
    sessionId: string,
    decision: DecisionRevision,
    motivo: string,
  ): Promise<{ session_id: string; previous: string; new: string; actor: string; decision_at: string }> {
    return await realFetch(
      `/review/session/${sessionId}/decide`,
      { method: 'POST', body: JSON.stringify({ decision, observaciones: motivo }) },
    );
  },

  /**
   * Registra el VEREDICTO de resolución (fase 2) de un caso abierto (capacidad `resolver_caso`).
   * Real: POST /review/session/{id}/resolve → 200; 409 si ya resuelto o el caso no está abierto.
   * `motivo` obligatorio; `evidenciaRef` obligatorio si `anulado_por_fraude` (D11).
   */
  async resolverCaso(
    sessionId: string,
    resolucion: DecisionResolucion,
    motivo: string,
    evidenciaRef?: string,
  ): Promise<{ session_id: string; resolucion: string; actor: string; resolucion_at: string; nota_anulada: boolean }> {
    return await realFetch(
      `/review/session/${sessionId}/resolve`,
      {
        method: 'POST',
        body: JSON.stringify({ resolucion, motivo, evidencia_ref: evidenciaRef ?? null }),
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
