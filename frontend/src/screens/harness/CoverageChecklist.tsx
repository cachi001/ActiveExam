/**
 * CoverageChecklist — referencia ÚNICA de eventos vigilados + checklist de cobertura.
 *
 * Combina:
 *  - Qué eventos vigila el sistema, con severidad/peso/descripción.
 *  - Estado pendiente/cubierto por sesión (qué ya probaste en este harness).
 *
 * Modo what-if (Test Detección): si recibe ``onOverrideChange``, cada card activa
 * muestra un input editable de 1–100 pts. La severidad se DERIVA del peso (a más
 * peso, más severidad) y se muestra en el badge — el admin no tiene que pensar
 * "qué rango toca", pone el número y el badge cambia solo. Los cambios son
 * LOCALES (no persisten).
 *
 * Los datos de severidad/peso vienen de la config viva del sistema (legendRows);
 * la estructura de categoría/descripción viene del SUSPICIOUS_ACTIVITY_CATALOG.
 * Si legendRows está vacío, se usa la severidad del catálogo como fallback.
 */

import { Icon, Card, SectionTitle, Button } from '../../ui/components';
import { SUSPICIOUS_ACTIVITY_CATALOG, EVENTOS_CON_IMAGEN } from '../../proctoring/suspiciousActivityCatalog';
import { SEVERITY_BADGE_COLORS } from './helpers';
import {
  RANGOS_SEVERIDAD,
  SEV_LABEL,
  severidadParaPeso,
  rangoDeSeveridad,
  type SeveridadEditable,
} from '../../config/severityRanges';
import type { LegendRow } from './buildLegendModel';
import type { CoverageEntry, MonitorPermission } from './types';
import type { Severidad } from '../../lib/types';

const SEV_ORDER: Record<string, number> = { critica: 0, alta: 1, media: 2, baja: 3 };

/** Color de la línea-acento superior por severidad (card blanca). */
const SEV_LINEA: Record<SeveridadEditable, string> = {
  baja: 'bg-blue-400',
  media: 'bg-amber-400',
  alta: 'bg-red-500',
  critica: 'bg-red-700',
};

interface CoverageChecklistProps {
  coverage: Partial<Record<string, CoverageEntry>>;
  monitorPermission: MonitorPermission;
  sessionStart: number;
  /** Filas derivadas de la config viva (buildLegendModel). */
  legendRows: LegendRow[];
  /** true si no se pudo cargar la config de scoring. */
  legendError?: boolean;
  /**
   * Modo what-if: overrides locales de peso por evento. Si se pasa con
   * onOverrideChange, las filas activas muestran un input editable.
   * Los cambios son LOCALES (no persisten).
   */
  scoringOverrides?: Record<string, number>;
  onOverrideChange?: (tipoEvento: string, peso: number) => void;
  onResetOverrides?: () => void;
}

export default function CoverageChecklist({
  coverage,
  monitorPermission,
  sessionStart,
  legendRows,
  legendError = false,
  scoringOverrides,
  onOverrideChange,
  onResetOverrides,
}: CoverageChecklistProps) {
  const editable = !!onOverrideChange;
  const hayOverrides = editable && scoringOverrides && Object.keys(scoringOverrides).length > 0;

  // Construir un mapa rápido tipo → legendRow para lookups O(1)
  const legendByTipo = new Map(legendRows.map((r) => [r.tipoEvento, r]));

  const testableCatalog = SUSPICIOUS_ACTIVITY_CATALOG.filter(
    (e) => !(e.requiereApiOpcional && monitorPermission === 'unsupported'),
  );
  const captured = testableCatalog.filter((e) => coverage[e.tipo]);
  const allDone = testableCatalog.length > 0 && captured.length === testableCatalog.length;

  // Catálogo ordenado por severidad (crítica primero) usando la config viva o fallback al catálogo.
  const sortedCatalog = [...SUSPICIOUS_ACTIVITY_CATALOG].sort((a, b) => {
    const sevA = (legendByTipo.get(a.tipo)?.severidad ?? a.severidad) as string;
    const sevB = (legendByTipo.get(b.tipo)?.severidad ?? b.severidad) as string;
    return (SEV_ORDER[sevA] ?? 4) - (SEV_ORDER[sevB] ?? 4);
  });

  return (
    <Card className="space-y-md">
      <div className="flex items-start justify-between gap-md flex-wrap">
        <SectionTitle sub="Severidad, impacto en el score y si ya lo probaste en esta sesión.">
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

      {/* Leyenda de rangos — informativa, una sola vez. La severidad se ajusta sola
          al peso, así el admin solo elige el número y la severidad sigue. */}
      {editable && (
        <div className="flex items-center gap-sm flex-wrap text-[12px] text-on-surface-variant border-b border-outline-variant/40 pb-sm">
          <span className="font-semibold text-on-surface">Escala de severidad:</span>
          {RANGOS_SEVERIDAD.map((r) => (
            <span
              key={r.sev}
              className={`inline-flex items-baseline gap-1.5 px-2 py-0.5 rounded-full font-semibold leading-none ${SEVERITY_BADGE_COLORS[r.sev]}`}
            >
              <span>{SEV_LABEL[r.sev]}</span>
              <span className="tabular-nums font-normal opacity-80">{r.min}–{r.max}</span>
            </span>
          ))}
        </div>
      )}

      {legendError && (
        <div
          className="flex items-start gap-sm p-sm rounded-xl bg-warning-container/50 text-warning border border-warning-200"
          role="alert"
        >
          <Icon name="warning" className="text-[14px] shrink-0 mt-px" />
          <span className="text-label-sm">
            No se pudo cargar la configuración de scoring. Los pesos pueden no reflejar los actuales.
          </span>
        </div>
      )}

      {/* Bento grid: 1 col en mobile, 2 en sm, 3 en xl. Sin scroll vertical eterno. */}
      <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-md">
        {sortedCatalog.map((entry) => {
          const cap = coverage[entry.tipo];
          const isUntestable = entry.requiereApiOpcional && monitorPermission === 'unsupported';
          const liveRow = legendByTipo.get(entry.tipo);
          const pesoSistema = liveRow?.peso;
          const pesoOverride = scoringOverrides?.[entry.tipo];
          const pesoVivo = pesoOverride ?? pesoSistema;
          // Severidad VISIBLE: derivada del peso vivo. Así al subir el peso a 70,
          // el badge pasa de "media" a "alta" sin que el admin elija severidad.
          const sevSistema = (liveRow?.severidad ?? entry.severidad) as Severidad;
          const sevVisible: SeveridadEditable =
            pesoVivo != null && editable
              ? severidadParaPeso(pesoVivo)
              : (sevSistema === 'baseline' ? 'media' : sevSistema as SeveridadEditable);
          const editableEsteEvento = editable && !!liveRow && !isUntestable;
          return (
            <div
              key={entry.tipo}
              className={`relative overflow-hidden flex flex-col gap-sm p-md rounded-xl border text-label-sm h-full ${
                isUntestable
                  ? 'bg-surface-50 border-outline-variant/40 opacity-70'
                  : 'bg-white border-outline-variant/50 shadow-sm'
              }`}
            >
              {/* Línea de color arriba por severidad (card blanca moderna, sin fondo de color). */}
              {!isUntestable && (
                <div className={`absolute top-0 left-0 right-0 h-1 ${SEV_LINEA[sevVisible]}`} aria-hidden />
              )}
              {/* Header: ícono de cobertura + nombre + estado */}
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
                <div className="flex-1 min-w-0">
                  <p className={`font-semibold leading-tight ${cap ? 'text-on-surface' : 'text-on-surface-variant'}`}>
                    {entry.label}
                  </p>
                  <p className="text-[11px] text-on-surface-variant leading-snug mt-0.5">{entry.descripcion}</p>
                </div>
              </div>

              {/* Badges: severidad (derivada del peso si editable) + estado */}
              <div className="flex items-center gap-1.5 flex-wrap">
                <span
                  className={`inline-flex items-baseline gap-1.5 text-[11px] px-2 py-0.5 rounded-full font-semibold leading-none ${SEVERITY_BADGE_COLORS[sevVisible]}`}
                >
                  <span>{SEV_LABEL[sevVisible]}</span>
                  {!editableEsteEvento && pesoVivo != null && (
                    <span className="tabular-nums font-normal opacity-80">+{pesoVivo}</span>
                  )}
                </span>
                {/* ¿Adjunta screenshot al dispararse? (no es lo mismo para todos) */}
                <span
                  className={`inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded font-medium leading-none ${
                    EVENTOS_CON_IMAGEN.has(entry.tipo)
                      ? 'bg-blue-50 text-blue-700'
                      : 'bg-surface-container text-on-surface-variant'
                  }`}
                >
                  <Icon
                    name={EVENTOS_CON_IMAGEN.has(entry.tipo) ? 'photo_camera' : 'no_photography'}
                    className="text-[12px]"
                  />
                  {EVENTOS_CON_IMAGEN.has(entry.tipo) ? 'Captura imagen' : 'Sin imagen'}
                </span>
                {liveRow && !liveRow.activo && (
                  <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200">
                    <Icon name="pause_circle" className="text-[11px]" />
                    Desactivado
                  </span>
                )}
                {isUntestable ? (
                  <span className="text-[10px] text-on-surface-variant italic ml-auto">No testeable</span>
                ) : cap ? (
                  <span className="text-[10px] text-success font-semibold font-mono ml-auto">
                    Probado +{((cap.capturedAt - sessionStart) / 1000).toFixed(1)}s
                  </span>
                ) : (
                  <span className="text-[10px] text-on-surface-variant font-semibold ml-auto">Sin probar</span>
                )}
              </div>

              {/* Input de peso editable (modo what-if). Rango libre 1-100. */}
              {editableEsteEvento && pesoVivo != null && (
                <div className="flex items-center gap-1.5 mt-auto pt-sm border-t border-outline-variant/30">
                  <span className="text-[11px] text-on-surface-variant">Suma al score:</span>
                  {/* Select acotado al rango de SU severidad (no cualquier valor libre). */}
                  <select
                    value={String(pesoVivo)}
                    onChange={(e) => onOverrideChange?.(entry.tipo, parseInt(e.target.value, 10))}
                    className="px-1.5 py-0.5 text-[12px] rounded-md border border-outline-variant bg-white font-mono focus:outline-none focus:border-surface-500 transition-colors"
                    aria-label={`Peso de ${entry.label} (rango ${rangoDeSeveridad(sevVisible).min}–${rangoDeSeveridad(sevVisible).max}, severidad ${SEV_LABEL[sevVisible]})`}
                  >
                    {Array.from(
                      { length: rangoDeSeveridad(sevVisible).max - rangoDeSeveridad(sevVisible).min + 1 },
                      (_, k) => rangoDeSeveridad(sevVisible).min + k,
                    ).map((n) => (
                      <option key={n} value={n}>{n}</option>
                    ))}
                  </select>
                  <span className="text-[11px] text-on-surface-variant">pts</span>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {editable && hayOverrides && onResetOverrides && (
        <div className="flex items-center justify-end gap-sm pt-sm border-t border-outline-variant/40">
          <Button variant="outline" icon="restart_alt" onClick={onResetOverrides}>
            Volver a los pesos del sistema
          </Button>
        </div>
      )}
    </Card>
  );
}
