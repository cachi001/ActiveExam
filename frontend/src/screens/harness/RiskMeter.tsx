/**
 * RiskMeter — medidor de riesgo diagnóstico (C-33).
 * Estado local, no modifica store.scorePropio. Semántica L2.5: prioriza, no sanciona.
 *
 * Presentacional: recibe score, umbral y callbacks por props.
 */

import { Icon, Card, Button, SectionTitle } from '../../ui/components';
import { gaugeColor, gaugeTextColor } from './helpers';

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
  return (
    <Card className="space-y-md">
      <SectionTitle sub="Score acumulado de esta sesión de diagnóstico">
        Medidor de riesgo
      </SectionTitle>

      {/* Gauge — barra de progreso */}
      <div className="space-y-sm">
        <div className="flex items-center justify-between gap-sm">
          <span className="text-label-sm text-on-surface-variant">Score acumulado</span>
          <span className={`font-headline text-headline-sm font-bold ${gaugeTextColor(harnessScore, riskThreshold)}`}>
            {harnessScore}%
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

      {/* Input de umbral configurable */}
      <div className="space-y-base">
        <label>
          <span className="text-label-sm font-semibold text-on-surface block">
            Umbral de riesgo (%)
          </span>
          <span className="text-[11px] text-on-surface-variant">
            Cuando el score supera este valor, la sesión priorizaría revisión humana.
          </span>
        </label>
        <input
          type="number"
          min={1}
          max={100}
          value={riskThreshold}
          onChange={(e) => {
            const raw = parseInt(e.target.value, 10);
            const clamped = isNaN(raw) ? 1 : Math.max(1, Math.min(100, raw));
            onThresholdChange(clamped);
          }}
          className="w-full px-sm py-base text-label-md rounded-xl border border-outline-variant bg-surface-container-lowest outline-none font-mono focus:border-primary-container"
        />
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
