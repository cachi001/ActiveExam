// Observaciones del proctor y cierre forzado.
// Parte de `proctoringApi`, partido por dominio (mismo criterio que el refactor
// c-76 que saco estos metodos de `api.ts`). Se compone en `../apiProctoring.ts`
// por spread; ningun metodo usa `this`.
import { realFetch } from '../apiCore';
import type {
  ObservacionProctor, CierreForzado,
} from '../types';

export const observacionesApi = {
  /**
   * El proctor registra una observación sobre la sesión (C-15 3.2) — insumo de C-16.
   * Real: POST /proctoring/sessions/{id}/observaciones → 201
   * Mock o fallo: agrega la observación en memoria.
   */
  async crearObservacionProctor(
    sessionId: string,
    texto: string,
    proctorActor?: string | null,
  ): Promise<ObservacionProctor> {
    return await realFetch<ObservacionProctor>(
      `/proctoring/sessions/${sessionId}/observaciones`,
      { method: 'POST', body: JSON.stringify({ texto, proctor_actor: proctorActor ?? null }) },
      'demo',
    );
  },

  /**
   * Lista las observaciones del proctor de una sesión, asc por creada_en (C-15 3.2).
   * Real: GET /proctoring/sessions/{id}/observaciones
   * Mock o fallo: lista en memoria.
   */
  async listarObservacionesProctor(sessionId: string): Promise<ObservacionProctor[]> {
    try {
      return await realFetch<ObservacionProctor[]>(
        `/proctoring/sessions/${sessionId}/observaciones`,
        { method: 'GET' },
        'demo',
      );
    } catch {
      return [];
    }
  },

  /**
   * Cierre FORZADO de una sesión por el proctor (C-15 3.3). Operativo, NO
   * disciplinario (L2.5). Idempotente: preserva el audit del primer cierre.
   * Real: PATCH /proctoring/sessions/{id}/cerrar-forzado → 200
   * Mock o fallo: simula el cierre.
   */
  async cerrarSesionForzado(
    sessionId: string,
    motivo: string,
    proctorActor?: string | null,
  ): Promise<CierreForzado> {
    return await realFetch<CierreForzado>(
      `/proctoring/sessions/${sessionId}/cerrar-forzado`,
      { method: 'PATCH', body: JSON.stringify({ motivo, proctor_actor: proctorActor ?? null }) },
      'demo',
    );
  },

  // ─────────────────────────────────────────────────────────────────────────
  // C-71 slice 2 — Decisión del revisor (dos fases). El sistema NUNCA sanciona
  // automáticamente (L2.5, regla #5): estos endpoints registran el juicio humano
  // de forma INMUTABLE (RN-RV-07). Un segundo intento devuelve 409.
  // ─────────────────────────────────────────────────────────────────────────,
};
