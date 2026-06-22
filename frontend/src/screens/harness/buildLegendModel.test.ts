/**
 * Tests del helper puro buildLegendModel (c-68 task 5.3).
 *
 * Construye el modelo de la "Leyenda" de Test Detección a partir de la config
 * VIVA de scoring (api.listarScoringConfig) + los detectores activos a nivel
 * sistema (getEffectiveConfig().detectores_activos).
 */

import { describe, it, expect } from 'vitest';
import { buildLegendModel } from './buildLegendModel';
import type { EventoScoreConfig } from '../../lib/types';

function evento(over: Partial<EventoScoreConfig> & { tipo_evento: string }): EventoScoreConfig {
  return {
    severidad: 'media',
    peso: 20,
    descripcion: 'desc',
    activo: true,
    updated_at: '',
    ...over,
  };
}

describe('buildLegendModel', () => {
  // ---- Orden por peso descendente ----
  it('ordena por peso descendente', () => {
    const items: EventoScoreConfig[] = [
      evento({ tipo_evento: 'perdida_de_foco', peso: 5 }),
      evento({ tipo_evento: 'monitor_adicional', peso: 50 }),
      evento({ tipo_evento: 'cambio_pestana', peso: 20 }),
    ];
    const model = buildLegendModel(items, ['perdida_de_foco', 'monitor_adicional', 'cambio_pestana']);
    expect(model.map((m) => m.peso)).toEqual([50, 20, 5]);
    expect(model.map((m) => m.tipoEvento)).toEqual(['monitor_adicional', 'cambio_pestana', 'perdida_de_foco']);
  });

  it('a igual peso, desempata por severidad descendente', () => {
    const items: EventoScoreConfig[] = [
      evento({ tipo_evento: 'cambio_pestana', peso: 20, severidad: 'baja' }),
      evento({ tipo_evento: 'rostro_ausente', peso: 20, severidad: 'critica' }),
    ];
    const model = buildLegendModel(items, ['cambio_pestana', 'rostro_ausente']);
    expect(model.map((m) => m.tipoEvento)).toEqual(['rostro_ausente', 'cambio_pestana']);
  });

  // ---- Activo depende de activo del item Y de detectores_activos ----
  it('marca inactivo si el detector no está en detectores_activos del sistema', () => {
    const items: EventoScoreConfig[] = [
      evento({ tipo_evento: 'copiar_pegar', activo: true }),
    ];
    const model = buildLegendModel(items, []); // no activo a nivel sistema
    expect(model[0].activo).toBe(false);
  });

  it('marca inactivo si el item está activo=false aunque el sistema lo tenga activo', () => {
    const items: EventoScoreConfig[] = [
      evento({ tipo_evento: 'copiar_pegar', activo: false }),
    ];
    const model = buildLegendModel(items, ['copiar_pegar']);
    expect(model[0].activo).toBe(false);
  });

  it('marca activo solo si item.activo Y está en detectores_activos', () => {
    const items: EventoScoreConfig[] = [
      evento({ tipo_evento: 'copiar_pegar', activo: true }),
    ];
    const model = buildLegendModel(items, ['copiar_pegar']);
    expect(model[0].activo).toBe(true);
  });

  // ---- Peso vivo (no default) ----
  it('respeta el peso vivo distinto del default', () => {
    const items: EventoScoreConfig[] = [
      evento({ tipo_evento: 'copiar_pegar', peso: 80, severidad: 'alta' }),
    ];
    const model = buildLegendModel(items, ['copiar_pegar']);
    expect(model[0].peso).toBe(80);
    expect(model[0].severidad).toBe('alta');
  });

  // ---- Label amigable + fallback ----
  it('usa el label amigable de TIPO_EVENTO_LABEL', () => {
    const items: EventoScoreConfig[] = [
      evento({ tipo_evento: 'copiar_pegar' }),
    ];
    const model = buildLegendModel(items, ['copiar_pegar']);
    expect(model[0].label).toBe('Copiar / Pegar');
  });

  it('cae al tipo_evento crudo si no hay label conocido', () => {
    const items: EventoScoreConfig[] = [
      evento({ tipo_evento: 'tipo_desconocido_xyz' }),
    ];
    const model = buildLegendModel(items, ['tipo_desconocido_xyz']);
    expect(model[0].label).toBe('tipo_desconocido_xyz');
  });

  // ---- descripcion null → string vacío ----
  it('normaliza descripcion null a string vacío', () => {
    const items: EventoScoreConfig[] = [
      evento({ tipo_evento: 'copiar_pegar', descripcion: null }),
    ];
    const model = buildLegendModel(items, ['copiar_pegar']);
    expect(model[0].descripcion).toBe('');
  });

  // ---- Lista vacía ----
  it('maneja lista vacía sin romper', () => {
    expect(buildLegendModel([], [])).toEqual([]);
    expect(buildLegendModel([], ['copiar_pegar'])).toEqual([]);
  });

  it('tolera detectores_activos undefined (fallback a vacío → todo inactivo)', () => {
    const items: EventoScoreConfig[] = [
      evento({ tipo_evento: 'copiar_pegar', activo: true }),
    ];
    const model = buildLegendModel(items, undefined);
    expect(model[0].activo).toBe(false);
  });

  // ---- baseline excluido (no es un evento, es el piso 0 del score) ----
  it('excluye los eventos con severidad baseline de la leyenda', () => {
    const items: EventoScoreConfig[] = [
      evento({ tipo_evento: 'estado_base', severidad: 'baseline', peso: 0 }),
      evento({ tipo_evento: 'copiar_pegar', severidad: 'alta', peso: 30 }),
    ];
    const model = buildLegendModel(items, ['estado_base', 'copiar_pegar']);
    expect(model.map((m) => m.tipoEvento)).toEqual(['copiar_pegar']);
    expect(model.some((m) => m.severidad === 'baseline')).toBe(false);
  });

  // ---- evento critica (corte_conectividad_prolongado) ordenado primero ----
  it('ordena el evento critica de mayor peso primero', () => {
    const items: EventoScoreConfig[] = [
      evento({ tipo_evento: 'copiar_pegar', severidad: 'alta', peso: 30 }),
      evento({ tipo_evento: 'corte_conectividad_prolongado', severidad: 'critica', peso: 100 }),
      evento({ tipo_evento: 'perdida_de_foco', severidad: 'baja', peso: 5 }),
    ];
    const model = buildLegendModel(
      items,
      ['copiar_pegar', 'corte_conectividad_prolongado', 'perdida_de_foco'],
    );
    expect(model[0].tipoEvento).toBe('corte_conectividad_prolongado');
    expect(model[0].severidad).toBe('critica');
    expect(model[0].peso).toBe(100);
  });
});
