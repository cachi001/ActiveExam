/**
 * Tests del cache de pesos de scoring por tipo de evento.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadScoringWeights, pesoEvento, resetScoringWeightsCache, snapshotPesos } from './scoringWeights';
import { api } from '../lib/api';

describe('scoringWeights', () => {
  beforeEach(() => {
    resetScoringWeightsCache();
    vi.restoreAllMocks();
  });

  it('antes de cargar usa el fallback por severidad', () => {
    expect(pesoEvento('cualquiera', 'media')).toBe(20);
    expect(pesoEvento('cualquiera', 'alta')).toBe(50);
    expect(pesoEvento('cualquiera', 'critica')).toBe(100);
    expect(snapshotPesos()).toBeNull();
  });

  it('usa el mapa de la BD cuando se cargaron los pesos', async () => {
    const stub = vi.spyOn(api, 'obtenerScoringWeights').mockResolvedValue({
      weights: { copiar_pegar: 35, monitor_adicional: 70 },
    });
    await loadScoringWeights();
    expect(stub).toHaveBeenCalledOnce();
    expect(pesoEvento('copiar_pegar', 'media')).toBe(35);
    expect(pesoEvento('monitor_adicional', 'alta')).toBe(70);
    // Un tipo que no esta en el mapa (inactivo) suma 0 — NO recurre al fallback por severidad.
    expect(pesoEvento('rostro_ausente', 'media')).toBe(0);
    expect(snapshotPesos()).toEqual({ copiar_pegar: 35, monitor_adicional: 70 });
  });

  it('deduplica llamadas concurrentes', async () => {
    let resolve!: (v: { weights: Record<string, number> }) => void;
    const stub = vi.spyOn(api, 'obtenerScoringWeights').mockReturnValue(
      new Promise((r) => { resolve = r; }),
    );
    const p1 = loadScoringWeights();
    const p2 = loadScoringWeights();
    const p3 = loadScoringWeights();
    resolve({ weights: { copiar_pegar: 11 } });
    await Promise.all([p1, p2, p3]);
    expect(stub).toHaveBeenCalledOnce();
    expect(pesoEvento('copiar_pegar', 'media')).toBe(11);
  });

  it('si la API falla mantiene el fallback por severidad', async () => {
    vi.spyOn(api, 'obtenerScoringWeights').mockRejectedValue(new Error('500'));
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    await loadScoringWeights();
    expect(snapshotPesos()).toBeNull();
    expect(pesoEvento('copiar_pegar', 'media')).toBe(20);
  });

  it('resetScoringWeightsCache fuerza una nueva carga', async () => {
    const stub = vi.spyOn(api, 'obtenerScoringWeights')
      .mockResolvedValueOnce({ weights: { copiar_pegar: 35 } })
      .mockResolvedValueOnce({ weights: { copiar_pegar: 99 } });
    await loadScoringWeights();
    expect(pesoEvento('copiar_pegar', 'media')).toBe(35);
    resetScoringWeightsCache();
    await loadScoringWeights();
    expect(pesoEvento('copiar_pegar', 'media')).toBe(99);
    expect(stub).toHaveBeenCalledTimes(2);
  });
});
