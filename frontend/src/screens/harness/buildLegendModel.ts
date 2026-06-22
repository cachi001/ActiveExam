/**
 * buildLegendModel — helper PURO que arma el modelo de la "Leyenda" de la
 * pantalla Test Detección a partir de la config VIVA del sistema (c-68 task 5.3).
 *
 * READ-ONLY: refleja lo que el admin configuró en Configuración → Scoring.
 * NO inventa pesos ni severidades hardcodeadas — todo viene de los datos.
 *
 * Fuentes:
 *  - items: api.listarScoringConfig().items → severidad/peso/descripcion/activo por tipo.
 *  - detectoresActivos: getEffectiveConfig().detectores_activos → qué detectores
 *    están encendidos a nivel sistema.
 *
 * Un evento se considera ACTIVO solo si su `activo` es true Y su tipo está en
 * `detectoresActivos`. Se ordena por peso descendente (desempate por severidad).
 */

import type { EventoScoreConfig, Severidad } from '../../lib/types';
import { TIPO_EVENTO_LABEL } from '../../lib/api';
import { SEVERITY_ORDER } from './helpers';

export interface LegendRow {
  tipoEvento: string;
  label: string;
  severidad: Severidad;
  peso: number;
  descripcion: string;
  activo: boolean;
}

/** Índice de severidad para ordenar/desempatar (mayor = más severo). */
function severityRank(sev: string): number {
  const idx = SEVERITY_ORDER.indexOf(sev as Severidad);
  return idx === -1 ? 0 : idx;
}

/** Label amigable; cae al tipo crudo si no hay uno conocido. */
function labelFor(tipoEvento: string): string {
  return (TIPO_EVENTO_LABEL as Record<string, string>)[tipoEvento] ?? tipoEvento;
}

export function buildLegendModel(
  items: EventoScoreConfig[],
  detectoresActivos: string[] | undefined,
): LegendRow[] {
  const activos = new Set(detectoresActivos ?? []);

  // baseline NO es un evento: es el piso 0 del score. No se muestra en la leyenda.
  const eventos = items.filter((item) => item.severidad !== 'baseline');

  const rows: LegendRow[] = eventos.map((item) => ({
    tipoEvento: item.tipo_evento,
    label: labelFor(item.tipo_evento),
    severidad: item.severidad as Severidad,
    peso: item.peso,
    descripcion: item.descripcion ?? '',
    activo: item.activo && activos.has(item.tipo_evento),
  }));

  // Orden por peso desc; a igual peso, por severidad desc.
  rows.sort((a, b) => {
    if (b.peso !== a.peso) return b.peso - a.peso;
    return severityRank(b.severidad) - severityRank(a.severidad);
  });

  return rows;
}
