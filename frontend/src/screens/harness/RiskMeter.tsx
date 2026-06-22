/**
 * RiskMeter — medidor de riesgo diagnóstico (C-33).
 * Estado local, no modifica store.scorePropio. Semántica L2.5: prioriza, no sanciona.
 *
 * Presentacional: recibe score, umbral y callbacks por props.
 */

import { Icon, Card, Button, SectionTitle } from '../../ui/components';
import { gaugeColor, gaugeTextColor } from './helpers';

const UMBRAL_MIN = 1;
const UMBRAL_MAX = 100;

interface RiskMeterProps {
  harnessScore: number;
  riskThreshold: number;
  onThresholdChange: (value: number) => void;
  onResetScore: () => void;
}

export default function RiskMeter({
  harnessScore,
  riskThreshold,
  onThresholdChange,
  onResetScore,
}: RiskMeterProps) {
  const umbralPct = ((riskThreshold - UMBRAL_MIN) / (UMBRAL_MAX - UMBRAL_MIN)) * 100;

  return (
    <Card className="space-y-md">
      <SectionTitle sub="Score acumulado de esta sesión de diagnóstico">
        Medidor de riesgo
      </SectionTitle>

      {/* Gauge — barra de progreso con color semántico */}
      <div className="space-y-sm">
        <div className="flex items-center justify-between gap-sm">
          <span className="text-label-sm text-on-surface-variant">Score acumulado</span>
          <span className={`font-headline text-headline-sm font-bold ${gaugeTextColor(harnessScore, riskThreshold)}`}>
            {harnessScore} <span className="text-label-sm font-semibold text-on-surface-variant">pts</span>
          </span>
        </div>
        <div className="bg-surface-container-high rounded-full h-3 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-300 ${gaugeColor(harnessScore, riskThreshold)}`}
            style={{ width: `${harnessScore}%` }}
            role="progressbar"
            aria-valuenow={harnessScore}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Score de riesgo acumulado"
          />
        </div>
      </div>

      {/* Banner de umbral superado — semántica L2.5 explícita */}
      {harnessScore >= riskThreshold && (
        <div className="flex items-start gap-sm p-sm rounded-xl bg-error-container text-on-error-container border border-error/30" role="alert">
          <Icon name="flag" className="text-[18px] shrink-0 mt-px text-error" fill />
          <span className="text-label-sm font-semibold">
            Superaría el umbral — priorizaría para revisión humana
          </span>
        </div>
      )}

      {/* Slider de umbral — igual que el de Configuración → Parámetros generales */}
      <div className="space-y-base">
        <div>
          <span className="text-label-sm font-semibold text-on-surface block">
            Umbral del sistema (de Configuración)
          </span>
          <span className="text-[11px] text-on-surface-variant">
            Cuando el score supera este valor, la sesión priorizaría revisión humana.
          </span>
        </div>

        <div className="flex items-baseline gap-2">
          <span className="text-[36px] leading-none font-headline font-bold text-on-surface tabular-nums">
            {riskThreshold}
          </span>
          <span className="text-title-md font-semibold text-on-surface-variant">puntos</span>
        </div>

        <div className="relative pt-1">
          <input
            type="range"
            min={UMBRAL_MIN}
            max={UMBRAL_MAX}
            value={riskThreshold}
            onChange={(e) => {
              const raw = parseInt(e.target.value, 10);
              const clamped = isNaN(raw) ? UMBRAL_MIN : Math.max(UMBRAL_MIN, Math.min(UMBRAL_MAX, raw));
              onThresholdChange(clamped);
            }}
            aria-label="Umbral de riesgo para revisión"
            aria-valuetext={`score mayor o igual a ${riskThreshold} puntos prioriza revisión`}
            className="ae-slider w-full appearance-none bg-transparent cursor-pointer"
            style={{
              background: `linear-gradient(to right, #2563eb 0%, #2563eb ${umbralPct}%, #cbd5e1 ${umbralPct}%, #cbd5e1 100%)`,
            }}
          />
          <div className="flex justify-between text-[11px] text-on-surface-variant mt-1 tabular-nums">
            <span>{UMBRAL_MIN}</span>
            <span>{UMBRAL_MAX}</span>
          </div>
          <p className="text-[12px] text-on-surface-variant mt-2">
            Las sesiones que alcancen <strong>{riskThreshold} puntos o más</strong> entran a la cola de revisión humana.
            Bajar el umbral manda más sesiones a revisar; subirlo, solo las más riesgosas.
          </p>
        </div>
      </div>

      {/* Botón Resetear riesgo — independiente del pipeline */}
      <div className="pt-sm border-t border-outline-variant/40">
        <Button
          variant="outline"
          icon="restart_alt"
          onClick={onResetScore}
          className="w-full"
        >
          Resetear riesgo
        </Button>
      </div>
    </Card>
  );
}
