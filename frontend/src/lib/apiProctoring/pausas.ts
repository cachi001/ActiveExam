// Pausas autorizadas: solicitud, resolucion y cierre.
// Parte de `proctoringApi`, partido por dominio (mismo criterio que el refactor
// c-76 que saco estos metodos de `api.ts`). Se compone en `../apiProctoring.ts`
// por spread; ningun metodo usa `this`.
import { realFetch } from '../apiCore';
import type {
  Pausa, AccionPausa, PausaPendiente,
} from '../types';

export const pausasApi = {
  /**
   * El alumno solicita una pausa (C-15).
   * Real: POST /proctoring/sessions/{id}/pausas → 201 pausa 'solicitada'
   * Mock o fallo: crea la pausa en memoria.
   */
  async solicitarPausa(sessionId: string, motivo: string): Promise<Pausa> {
    return await realFetch<Pausa>(
      `/proctoring/sessions/${sessionId}/pausas`,
      { method: 'POST', body: JSON.stringify({ motivo }) },
      'demo',
    );
  },

  /**
   * Lista las pausas de una sesión, desc por solicitada_en (C-15).
   * La más reciente queda primera (lo que el poll del alumno necesita).
   * Real: GET /proctoring/sessions/{id}/pausas
   * Mock o fallo: lista en memoria ordenada desc.
   */
  async listarPausas(sessionId: string): Promise<Pausa[]> {
    try {
      return await realFetch<Pausa[]>(
        `/proctoring/sessions/${sessionId}/pausas`,
        { method: 'GET' },
        'demo',
      );
    } catch {
      return [];
    }
  },

  /**
   * Lista las pausas pendientes de TODAS las sesiones (C-15) — poll del proctor.
   * Solo estado 'solicitada', asc por solicitada_en.
   * Real: GET /proctoring/pausas/pendientes
   * Mock o fallo: arma la cola desde el estado en memoria.
   */
  async listarPausasPendientes(): Promise<PausaPendiente[]> {
    try {
      return await realFetch<PausaPendiente[]>(
        '/proctoring/pausas/pendientes',
        { method: 'GET' },
        'demo',
      );
    } catch {
      return [];
    }
  },

  /**
   * El proctor resuelve una pausa solicitada: aprobar o rechazar (C-15).
   * Real: PATCH /proctoring/pausas/{id} → 200 pausa actualizada; 409 si ya no
   *       está 'solicitada' (otra resolución ganó la carrera).
   * Mock o fallo: muta la pausa en memoria; lanza Error con .status=409 si ya
   *       no estaba 'solicitada' para que la UI maneje el caso igual que en real.
   */
  async resolverPausa(
    pausaId: string,
    accion: AccionPausa,
    proctorActor?: string | null,
    motivoRechazo?: string | null,
  ): Promise<Pausa> {
    // El motivo solo viaja al rechazar (al aprobar el backend lo ignora/None).
    const body: Record<string, unknown> = {
      accion,
      proctor_actor: proctorActor ?? null,
    };
    if (accion === 'rechazar') body.motivo_rechazo = motivoRechazo ?? null;
    return await realFetch<Pausa>(
      `/proctoring/pausas/${pausaId}`,
      { method: 'PATCH', body: JSON.stringify(body) },
      'demo',
    );
  },

  /**
   * Finaliza una pausa aprobada (el alumno reanuda el examen) (C-15).
   * Real: PATCH /proctoring/pausas/{id}/finalizar → 200 pausa 'finalizada';
   *       409 si no estaba 'aprobada'.
   * Mock o fallo: muta la pausa en memoria.
   */
  async finalizarPausa(pausaId: string): Promise<Pausa> {
    return await realFetch<Pausa>(
      `/proctoring/pausas/${pausaId}/finalizar`,
      { method: 'PATCH' },
      'demo',
    );
  },

  // ─────────────────────────────────────────────────────────────────────────
  // C-15 (3.2 / 3.3) — Acciones del proctor: observaciones + cierre forzado
  // ─────────────────────────────────────────────────────────────────────────,
};
