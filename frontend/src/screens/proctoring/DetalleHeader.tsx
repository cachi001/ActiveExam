/**
 * DetalleHeader — Encabezado del detalle de sesión: metadata + stat-cards + gauge.
 *
 * Presenta etiqueta, modo y fecha, y arriba las métricas prominentes (score,
 * eventos, discrepancias) como stat-cards. El gauge de score usa el color por
 * nivel de riesgo. Sobrio, sin gradientes.
 */
import { Icon, Card, Badge } from '../../ui/components';
import type { SesionProctoringDetalle } from '../../lib/types';
import { StatCard } from './StatCard';
import {
  formatFecha,
  scoreTextColor,
  gaugeFill,
  nivelRiesgo,
  modoBadgeTone,
  modoLabel,
} from './helpers';

const NIVEL_LABEL = { bajo: 'Riesgo bajo', medio: 'Riesgo medio', alto: 'Riesgo alto' } as const;

export function DetalleHeader({ detalle }: { detalle: SesionProctoringDetalle }) {
  const nivel = nivelRiesgo(detalle.score);
  // El backend de detalle (GET /proctoring/sessions/{id}) NO devuelve los
  // contadores agregados; los derivamos a partir de los eventos cargados.
  // Fallback: usa los del resumen si vinieron (mock o respuestas antiguas).
  const totalEventos = detalle.eventos?.length ?? detalle.total_eventos ?? 0;
  const totalDiscrepancias =
    detalle.eventos?.filter((e) => e.veredicto_reinferencia === 'discrepancia').length ??
    detalle.total_discrepancias ??
    0;

  return (
    <Card className="space-y-lg">
      {/* Metadata */}
      <div className="space-y-sm">
        <div className="flex items-center gap-sm flex-wrap">
          <h1 className="font-headline text-headline-md text-on-surface tracking-tight">
            {detalle.etiqueta?.trim() || 'Sesión sin etiqueta'}
          </h1>
          <Badge tone={modoBadgeTone(detalle.modo)}>{modoLabel(detalle.modo)}</Badge>
        </div>
        <div className="flex items-center gap-md flex-wrap text-label-sm text-on-surface-variant">
          <span className="inline-flex items-center gap-base">
            <Icon name="schedule" className="text-[15px]" />
            {formatFecha(detalle.creada_en, true)}
          </span>
          <span className="text-outline-variant" aria-hidden>·</span>
          <span className="inline-flex items-center gap-base font-mono" title={detalle.id}>
            <Icon name="fingerprint" className="text-[15px]" />
            {detalle.id.slice(0, 24)}…
          </span>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-md">
        <StatCard
          icon="speed"
          label="Score"
          value={`${detalle.score}`}
          sub={NIVEL_LABEL[nivel]}
          tono={nivel === 'alto' ? 'error' : nivel === 'medio' ? 'warning' : 'success'}
        />
        <StatCard icon="notifications" label="Eventos" value={totalEventos} tono="neutral" />
        <StatCard
          icon="rule"
          label="Discrepancias"
          value={totalDiscrepancias}
          tono={totalDiscrepancias > 0 ? 'error' : 'success'}
        />
      </div>

      {/* Gauge de score */}
      <div className="space-y-sm pt-sm border-t border-outline-variant/40">
        <div className="flex items-center justify-between">
          <span className="text-label-sm text-on-surface-variant">Score acumulado de priorización</span>
          <span className={`font-headline text-title-lg font-bold ${scoreTextColor(detalle.score)}`}>
            {detalle.score}%
          </span>
        </div>
        <div className="bg-surface-container-high rounded-full h-2.5 overflow-hidden">
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
        <p className="text-label-sm text-on-surface-variant">
          El score prioriza la revisión humana; nunca emite veredicto disciplinario.
        </p>
      </div>
    </Card>
  );
}

export default DetalleHeader;
