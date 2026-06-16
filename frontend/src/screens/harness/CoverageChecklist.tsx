/**
 * CoverageChecklist — referencia ÚNICA de eventos vigilados + checklist de cobertura.
 *
 * Reemplaza a LeyendaSeveridad (eliminada). Combina ambos propósitos:
 *  - Qué eventos vigila el sistema, con severidad/peso/descripción y si se detecta
 *    a nivel VISIÓN o NAVEGADOR.
 *  - Estado pendiente/cubierto por sesión (qué ya probaste en este harness).
 *
 * Los datos de severidad/peso vienen de la config viva del sistema (legendRows);
 * la estructura de categoría/descripción viene del SUSPICIOUS_ACTIVITY_CATALOG.
 * Si legendRows está vacío (carga pendiente o falla), se usa la severidad del catálogo
 * como fallback para los colores.
 *
 * Presentacional: recibe todo por props.
 */

import { useNavigate } from '../../lib/router';
import { Icon, Card, SectionTitle } from '../../ui/components';
import { SUSPICIOUS_ACTIVITY_CATALOG } from '../../proctoring/suspiciousActivityCatalog';
import { SEVERITY_BADGE_COLORS, SEVERITY_CARD_COLORS } from './helpers';
import type { LegendRow } from './buildLegendModel';
import type { CoverageEntry, MonitorPermission } from './types';
import type { Severidad } from '../../lib/types';

interface CoverageChecklistProps {
  coverage: Partial<Record<string, CoverageEntry>>;
  monitorPermission: MonitorPermission;
  sessionStart: number;
  /** Filas derivadas de la config viva (buildLegendModel). */
  legendRows: LegendRow[];
  /** true si no se pudo cargar la config de scoring. */
  legendError?: boolean;
}

export default function CoverageChecklist({
  coverage,
  monitorPermission,
  sessionStart,
  legendRows,
  legendError = false,
}: CoverageChecklistProps) {
  const navigate = useNavigate();

  // Construir un mapa rápido tipo → legendRow para lookups O(1)
  const legendByTipo = new Map(legendRows.map((r) => [r.tipoEvento, r]));

  const testableCatalog = SUSPICIOUS_ACTIVITY_CATALOG.filter(
    (e) => !(e.requiereApiOpcional && monitorPermission === 'unsupported'),
  );
  const captured = testableCatalog.filter((e) => coverage[e.tipo]);
  const allDone = testableCatalog.length > 0 && captured.length === testableCatalog.length;

  return (
    <Card className="space-y-md">
      <div className="flex items-start justify-between gap-md flex-wrap">
        <SectionTitle sub="Severidad, impacto en el score y si ya lo probaste en esta sesión. «Sin probar» significa que el evento aún no ocurrió en esta sesión de prueba.">
          Eventos que vigila el sistema
        </SectionTitle>
        {allDone ? (
          <span className="inline-flex items-center gap-base px-md py-sm rounded-xl bg-success-container text-success font-bold text-label-md border border-success/30">
            <Icon name="verified" className="text-[18px]" fill />
            Cobertura completa
          </span>
        ) : (
          <span className="text-label-sm text-on-surface-variant font-mono">
            {captured.length}/{testableCatalog.length} tipos cubiertos
          </span>
        )}
      </div>

      {legendError && (
        <div
          className="flex items-start gap-sm p-sm rounded-xl bg-warning-container/50 text-warning border border-warning/30"
          role="alert"
        >
          <Icon name="warning" className="text-[14px] shrink-0 mt-px" />
          <span className="text-label-sm">
            No se pudo cargar la configuración de scoring. Los pesos pueden no reflejar los actuales.
          </span>
        </div>
      )}

      <div className="space-y-md">
        {SUSPICIOUS_ACTIVITY_CATALOG.map((entry) => {
          const cap = coverage[entry.tipo];
          const isUntestable = entry.requiereApiOpcional && monitorPermission === 'unsupported';
          const liveRow = legendByTipo.get(entry.tipo);
          // Usar severidad de la config viva si disponible; fallback al catálogo
          const sev: Severidad = (liveRow?.severidad ?? entry.severidad) as Severidad;
          const peso = liveRow?.peso;
          const cardColor = isUntestable
            ? 'bg-surface-container border-outline-variant/40 opacity-60'
            : `${SEVERITY_CARD_COLORS[sev]}`;

          return (
            <div
              key={entry.tipo}
              className={`flex items-start justify-between gap-sm p-md rounded-xl border text-label-sm ${cardColor}`}
            >
              <div className="flex items-start gap-sm">
                <Icon
                  name={isUntestable ? 'info' : cap ? 'check_circle' : 'radio_button_unchecked'}
                  className={`text-[18px] shrink-0 mt-px ${
                    isUntestable
                      ? 'text-on-surface-variant'
                      : cap
                      ? 'text-success'
                      : 'text-on-surface-variant'
                  }`}
                  fill={!isUntestable && !!cap}
                />
                <div className="space-y-px">
                  <div className="flex items-center gap-sm flex-wrap">
                    <span className={`font-semibold ${cap ? 'text-on-surface' : 'text-on-surface-variant'}`}>
                      {entry.label}
                    </span>
                    {/* Badge severidad + impacto (peso) */}
                    <span className={`inline-flex items-center gap-base text-[10px] uppercase tracking-wide px-base py-px rounded-full font-bold ${SEVERITY_BADGE_COLORS[sev]}`}>
                      {sev}
                      {peso != null && (
                        <span className="font-mono normal-case">+{peso}</span>
                      )}
                    </span>
                    {/* Badge "Inactivo" si la config viva lo tiene desactivado */}
                    {liveRow && !liveRow.activo && (
                      <span className="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-surface-container-high text-on-surface-variant">
                        Inactivo
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-on-surface-variant">{entry.descripcion}</p>
                </div>
              </div>
              <div className="shrink-0 text-right space-y-px">
                {isUntestable ? (
                  <span className="text-[10px] text-on-surface-variant italic">No testeable en este navegador</span>
                ) : cap ? (
                  <>
                    <span className="block text-[10px] text-success font-semibold">Probado ✓</span>
                    <span className="block text-[10px] text-success font-mono">
                      +{((cap.capturedAt - sessionStart) / 1000).toFixed(1)}s
                    </span>
                  </>
                ) : (
                  <span className="text-[10px] text-on-surface-variant font-semibold">Sin probar</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <p className="text-[11px] text-on-surface-variant border-t border-outline-variant/40 pt-sm">
        Para cambiar peso o severidad, andá a{' '}
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
