/**
 * LeyendaSeveridad — referencia VIVA de los tipos de evento configurados.
 *
 * c-68 task 5.3: REFLEJA lo que el admin configura en Configuración → Scoring
 * (severidad, peso y estado activo POR TIPO DE EVENTO), en vez de mostrar 5
 * niveles de severidad con pesos hardcodeados que nadie puede editar.
 *
 * READ-ONLY: para cambiar pesos/severidad/estado, el usuario va a
 * Configuración → Scoring (se indica con un enlace abajo).
 *
 * Pensado para un NO-técnico: cada fila explica qué es el evento y que el
 * "peso" es cuánto suma al score acumulado (0–100) que prioriza la revisión
 * humana.
 */

import { useNavigate } from '../../lib/router';
import { Card, SectionTitle } from '../../ui/components';
import { SEVERIDAD_LABEL } from '../../lib/api';
import { SEVERITY_BADGE_COLORS, SEVERITY_CARD_COLORS } from './helpers';
import type { LegendRow } from './buildLegendModel';
import type { Severidad } from '../../lib/types';

interface LeyendaSeveridadProps {
  /** Filas derivadas de la config viva (buildLegendModel). */
  rows: LegendRow[];
  /** true si no se pudo cargar la config; mostramos un aviso. */
  error?: boolean;
}

export default function LeyendaSeveridad({ rows, error = false }: LeyendaSeveridadProps) {
  const navigate = useNavigate();
  return (
    <Card className="space-y-md">
      <SectionTitle sub="Los eventos que el sistema vigila y cuánto suma cada uno al riesgo acumulado (0–100)">
        Eventos y su peso
      </SectionTitle>

      {error && (
        <div
          className="flex items-start gap-sm p-sm rounded-xl bg-warning-container/50 text-warning border border-warning/30"
          role="alert"
        >
          <span className="text-label-sm">
            No se pudo cargar la configuración de scoring. Puede que estos valores no reflejen los actuales.
          </span>
        </div>
      )}

      {!error && rows.length === 0 && (
        <p className="text-[13px] text-on-surface-variant">
          No hay tipos de evento configurados todavía.
        </p>
      )}

      <ul className="space-y-base">
        {rows.map((row) => {
          const sevLabel = SEVERIDAD_LABEL[row.severidad as Severidad] ?? row.severidad;
          const badgeColor = SEVERITY_BADGE_COLORS[row.severidad as Severidad] ?? SEVERITY_BADGE_COLORS.baja;
          const cardColor = SEVERITY_CARD_COLORS[row.severidad as Severidad] ?? SEVERITY_CARD_COLORS.baja;
          return (
            <li
              key={row.tipoEvento}
              className={`flex items-start gap-sm px-sm py-base rounded-lg ${cardColor} ${
                !row.activo ? 'opacity-60' : ''
              }`}
            >
              <span
                className={`inline-flex items-center justify-center min-w-[64px] px-sm py-base rounded-full text-label-sm font-bold ${badgeColor}`}
                title={`Severidad: ${sevLabel}`}
              >
                {sevLabel}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-sm flex-wrap">
                  <p className="text-[13px] font-semibold text-on-surface leading-tight">{row.label}</p>
                  {!row.activo && (
                    <span className="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-surface-container-high text-on-surface-variant">
                      Inactivo
                    </span>
                  )}
                </div>
                {row.descripcion && (
                  <p className="text-[12px] text-on-surface-variant leading-tight mt-0.5">{row.descripcion}</p>
                )}
                <p className="text-[11px] text-on-surface-variant mt-1">
                  Suma <span className="font-mono font-bold">+{row.peso}</span> al score acumulado cuando ocurre.
                </p>
              </div>
            </li>
          );
        })}
      </ul>

      <p className="text-[11px] text-on-surface-variant border-t border-outline-variant/40 pt-sm">
        El score se acumula con tope en 100 y sirve para <strong>priorizar</strong> qué sesiones revisa una persona — el sistema nunca sanciona solo.
        Para cambiar el peso, la severidad o activar/desactivar un evento, andá a{' '}
        <button
          type="button"
          onClick={() => navigate('/admin/configuracion')}
          className="text-on-surface underline font-medium hover:text-on-surface-variant"
        >
          Configuración → Scoring
        </button>.
      </p>
    </Card>
  );
}
