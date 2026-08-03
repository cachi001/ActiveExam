// Parte de `adminApi`, partido por dominio (mismo criterio que el refactor c-76
// que saco estos metodos de `api.ts`). Se compone en `../apiAdmin.ts` por spread;
// ningun metodo usa `this`.
import { realFetch } from '../apiCore';
import type {
  EventoScoreConfig,
} from '../types';

export const scoringApi = {
  // -------------------------------------------------------------------------
  // Configuracion de scoring (admin_sistema) — #9 / #10
  // -------------------------------------------------------------------------

  /**
   * Lista los pesos configurados por tipo de evento (admin_sistema).
   * Real: GET /scoring/config
   * Mock: defaults del catalogo.
   */
  /**
   * Devuelve el mapa { tipo_evento: peso } de tipos activos (cualquier usuario
   * autenticado). Lo usa scoringWeights.ts para el calculo de score en vivo.
   * Real: GET /scoring/weights
   * Mock: defaults del catalogo.
   */
  async obtenerScoringWeights(): Promise<{ weights: Record<string, number> }> {
    return await realFetch<{ weights: Record<string, number> }>('/scoring/weights', { method: 'GET' });
  },

  async listarScoringConfig(): Promise<{ items: EventoScoreConfig[] }> {
    return await realFetch<{ items: EventoScoreConfig[] }>('/scoring/config', { method: 'GET' });
  },

  /**
   * Actualiza peso / severidad / descripcion / activo de un tipo (admin_sistema).
   * Real: PATCH /scoring/config/{tipo}
   * Mock: echo con campos sobrescritos.
   */
  async editarScoringConfig(
    tipoEvento: string,
    body: { severidad?: string; peso?: number; descripcion?: string | null; activo?: boolean },
  ): Promise<EventoScoreConfig> {
    return await realFetch<EventoScoreConfig>(
      `/scoring/config/${encodeURIComponent(tipoEvento)}`,
      { method: 'PATCH', body: JSON.stringify(body) },
    );
  },
};
