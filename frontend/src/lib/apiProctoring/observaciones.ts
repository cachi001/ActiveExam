// Observaciones del tutor y cierre forzado.
// Parte de `proctoringApi`, partido por dominio (mismo criterio que el refactor
// c-76 que saco estos metodos de `api.ts`). Se compone en `../apiProctoring.ts`
// por spread; ningun metodo usa `this`.
import { realFetch } from '../apiCore';
import type {
  ObservacionTutor, CierreForzado,
} from '../types';

export const observacionesApi = {
  /**
   * El tutor registra una observación sobre la sesión (C-15 3.2) — insumo de C-16.
   * Real: POST /proctoring/sessions/{id}/observaciones → 201
   * Mock o fallo: agrega la observación en memoria.
   */
  async crearObservacionTutor(
    sessionId: string,
    texto: string,
    tutorActor?: string | null,
  ): Promise<ObservacionTutor> {
    return await realFetch<ObservacionTutor>(
      `/proctoring/sessions/${sessionId}/observaciones`,
      { method: 'POST', body: JSON.stringify({ texto, tutor_actor: tutorActor ?? null }) },
      'demo',
    );
  },

  /**
   * Lista las observaciones del tutor de una sesión, asc por creada_en (C-15 3.2).
   * Real: GET /proctoring/sessions/{id}/observaciones
   * Mock o fallo: lista en memoria.
   */
  async listarObservacionesTutor(sessionId: string): Promise<ObservacionTutor[]> {
    try {
      return await realFetch<ObservacionTutor[]>(
        `/proctoring/sessions/${sessionId}/observaciones`,
        { method: 'GET' },
        'demo',
      );
    } catch {
      return [];
    }
  },

  /**
   * Cierre FORZADO de una sesión por el tutor/coordinador (C-15 3.3). Operativo, NO
   * disciplinario (L2.5). Idempotente: preserva el audit del primer cierre.
   * Real: PATCH /proctoring/sessions/{id}/cerrar-forzado → 200
   * Mock o fallo: simula el cierre.
   */
  async cerrarSesionForzado(
    sessionId: string,
    motivo: string,
    tutorActor?: string | null,
  ): Promise<CierreForzado> {
    return await realFetch<CierreForzado>(
      `/proctoring/sessions/${sessionId}/cerrar-forzado`,
      { method: 'PATCH', body: JSON.stringify({ motivo, tutor_actor: tutorActor ?? null }) },
      'demo',
    );
  },

  // ─────────────────────────────────────────────────────────────────────────
  // C-71 slice 2 — Decisión del revisor (dos fases). El sistema NUNCA sanciona
  // automáticamente (L2.5, regla #5): estos endpoints registran el juicio humano
  // de forma INMUTABLE (RN-RV-07). Un segundo intento devuelve 409.
  // ─────────────────────────────────────────────────────────────────────────,
};
