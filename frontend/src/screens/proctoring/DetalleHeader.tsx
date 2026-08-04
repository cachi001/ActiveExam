/**
 * DetalleHeader — Encabezado del detalle de sesión: metadata + stat-cards.
 *
 * Layout moderno: metadata en la parte superior (etiqueta + modo + fecha),
 * seguido de tres stat-cards con gradiente (score, eventos, discrepancias).
 * El score incluye una barra de progreso inline — sin sección de gauge redundante.
 */
import { Icon, Card, Badge } from '../../ui/components';
import type { SesionProctoringDetalle } from '../../lib/types';
import {
  formatFecha,
  scoreTextColor,
  gaugeFill,
  nivelRiesgo,
  modoBadgeTone,
  modoLabel,
} from './helpers';

const NIVEL_LABEL = { bajo: 'Riesgo bajo', medio: 'Riesgo medio', alto: 'Riesgo alto' } as const;

const TONO_BG: Record<'error' | 'warning' | 'success', string> = {
  error: 'bg-gradient-to-br from-error-500 to-error-600',
  warning: 'bg-gradient-to-br from-warning-500 to-warning-600',
  success: 'bg-gradient-to-br from-success-500 to-success-600',
};

export function DetalleHeader({ detalle }: { detalle: SesionProctoringDetalle }) {
  const nivel = nivelRiesgo(detalle.score);
  const totalEventos = detalle.eventos?.length ?? detalle.total_eventos ?? 0;
  const totalDiscrepancias =
    detalle.eventos?.filter((e) => e.veredicto_reinferencia === 'discrepancia').length ??
    detalle.total_discrepancias ??
    0;

  const scoreTono: 'error' | 'warning' | 'success' =
    nivel === 'alto' ? 'error' : nivel === 'medio' ? 'warning' : 'success';

  return (
    <Card className="space-y-lg">
      {/* Metadata */}
      <div className="flex items-start justify-between gap-md flex-wrap">
        <div className="space-y-xs min-w-0">
          <div className="flex items-center gap-sm flex-wrap">
            <h1 className="font-headline text-headline-md text-on-surface tracking-tight truncate">
              {detalle.etiqueta?.trim() || 'Sesión sin etiqueta'}
            </h1>
            <Badge tone={modoBadgeTone(detalle.modo)}>{modoLabel(detalle.modo)}</Badge>
          </div>
          <div className="flex items-center gap-md flex-wrap text-label-sm text-on-surface-variant">
            <span className="inline-flex items-center gap-base">
              <Icon name="schedule" className="text-[14px]" />
              {formatFecha(detalle.creada_en, true)}
            </span>
            <span className="text-outline-variant" aria-hidden>·</span>
            <span className="inline-flex items-center gap-base font-mono text-[11px]" title={detalle.id}>
              <Icon name="fingerprint" className="text-[14px]" />
              {detalle.id.slice(0, 20)}…
            </span>
          </div>
        </div>
        {/* Score badge compacto visible desde arriba */}
        <div className={`shrink-0 px-md py-sm rounded-xl text-white text-center min-w-[80px] ${TONO_BG[scoreTono]}`}>
          <p className="text-[11px] font-medium text-white/80 uppercase tracking-wide">Score</p>
          <p className="text-2xl font-bold leading-tight">{detalle.score}</p>
          <p className="text-[10px] text-white/80">{NIVEL_LABEL[nivel]}</p>
        </div>
      </div>

      {/* Barra de score */}
      <div className="space-y-xs">
        <div className="flex items-center justify-between text-label-sm">
          <span className="text-on-surface-variant">Score de priorización</span>
          <span className={`font-semibold ${scoreTextColor(detalle.score)}`}>{detalle.score} / 100 pts</span>
        </div>
        <div className="bg-surface-container-high rounded-full h-2 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${gaugeFill(detalle.score)}`}
            style={{ width: `${Math.min(100, Math.max(0, detalle.score))}%` }}
            role="progressbar"
            aria-valuenow={detalle.score}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Score de riesgo"
          />
        </div>
      </div>

      {/* Stats: eventos y discrepancias */}
      <div className="grid grid-cols-2 gap-md">
        {/* Eventos */}
        <div className="rounded-xl border border-info/20 bg-info/5 px-md py-sm flex items-center gap-sm">
          <div className="w-9 h-9 rounded-lg bg-info/15 flex items-center justify-center shrink-0">
            <Icon name="notifications" className="text-[18px] text-info" fill />
          </div>
          <div className="min-w-0">
            <p className="text-2xl font-bold text-on-surface leading-tight tabular-nums">{totalEventos}</p>
            <p className="text-[11px] text-on-surface-variant">Eventos</p>
          </div>
        </div>
        {/* Discrepancias */}
        <div className={`rounded-xl border px-md py-sm flex items-center gap-sm ${
          totalDiscrepancias > 0
            ? 'border-warning/30 bg-warning/5'
            : 'border-outline-variant/40 bg-surface-container-lowest'
        }`}>
          <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${
            totalDiscrepancias > 0 ? 'bg-warning/15' : 'bg-surface-container'
          }`}>
            <Icon name="rule" className={`text-[18px] ${totalDiscrepancias > 0 ? 'text-warning' : 'text-on-surface-variant'}`} fill />
          </div>
          <div className="min-w-0">
            <p className={`text-2xl font-bold leading-tight tabular-nums ${totalDiscrepancias > 0 ? 'text-warning' : 'text-on-surface'}`}>
              {totalDiscrepancias}
            </p>
            <p className="text-[11px] text-on-surface-variant">Discrepancias</p>
          </div>
        </div>
      </div>

      <p className="text-label-sm text-on-surface-variant/70">
        El score prioriza la revisión humana; nunca emite veredicto disciplinario.
      </p>
    </Card>
  );
}

export default DetalleHeader;
