/**
 * ThresholdsConfig — panel de configuración de umbrales del pipeline.
 *
 * Presentacional: recibe el draft de config, los errores y los callbacks
 * (cambio de campo, reset de reglas, restaurar defaults) por props.
 */

import { Card, Button, SectionTitle } from '../../ui/components';
import type { TransitionConfig } from '../../proctoring/stateTransitionRules';
import type { ConfigErrors, HarnessState } from './types';

interface ThresholdsConfigProps {
  configDraft: TransitionConfig;
  configErrors: ConfigErrors;
  harnessState: HarnessState;
  onConfigChange: (field: keyof TransitionConfig, rawValue: string) => void;
  onResetRules: () => void;
  onRestoreDefaults: () => void;
}

export default function ThresholdsConfig({
  configDraft,
  configErrors,
  harnessState,
  onConfigChange,
  onResetRules,
  onRestoreDefaults,
}: ThresholdsConfigProps) {
  return (
    <Card className="space-y-md">
      <SectionTitle sub="Cambios aplican al siguiente frame sin reiniciar el motor">
        Configuración de umbrales
      </SectionTitle>

      {/* C-32 Tasks 4.1–4.3: clearLabel como etiqueta principal; clave técnica como texto secundario.
          Los campos en ms ahora se muestran/editan en segundos para que un revisor tecnico no
          tenga que convertir mentalmente. La conversion es 1:1 (mostrar value/1000, persistir value*1000). */}
      {(
        [
          {
            field: 'face_absent_ms' as const,
            clearLabel: 'Tiempo sin rostro para alertar',
            label: 'face_absent_ms',
            unit: 's',
            scaleToSeconds: true,
            step: 0.1,
            hint: 'Tiempo sin detectar un rostro antes de emitir una alerta (en segundos)',
          },
          {
            field: 'multiple_faces_frames' as const,
            clearLabel: 'Fotogramas con varios rostros para alertar',
            label: 'multiple_faces_frames',
            unit: 'frames',
            scaleToSeconds: false,
            step: 1,
            hint: 'Cantidad de fotogramas consecutivos con más de un rostro para emitir una alerta',
          },
          {
            field: 'gaze_deviation_threshold' as const,
            clearLabel: 'Sensibilidad de mirada desviada',
            label: 'gaze_deviation_threshold',
            unit: '0..1',
            scaleToSeconds: false,
            step: 0.01,
            hint: 'Cuán lejos del centro puede mirar el alumno antes de que se considere desviado (0 = muy sensible, 1 = tolerante)',
          },
          {
            field: 'gaze_sustained_ms' as const,
            clearLabel: 'Tiempo de mirada desviada para alertar',
            label: 'gaze_sustained_ms',
            unit: 's',
            scaleToSeconds: true,
            step: 0.1,
            hint: 'Tiempo continuo mirando hacia un lado antes de emitir una alerta (en segundos)',
          },
          {
            field: 'gaze_fixation_tolerance' as const,
            clearLabel: 'Tolerancia de fijación de mirada',
            label: 'gaze_fixation_tolerance',
            unit: '0..1',
            scaleToSeconds: false,
            step: 0.01,
            hint: 'Variación permitida en la dirección de la mirada para considerarla sostenida en el mismo punto',
          },
        ] as { field: keyof TransitionConfig; clearLabel: string; label: string; unit: string; scaleToSeconds: boolean; step: number; hint: string }[]
      ).map(({ field, clearLabel, unit, scaleToSeconds, step, hint }) => {
        const displayValue = scaleToSeconds ? configDraft[field] / 1000 : configDraft[field];
        return (
          <div key={field} className="space-y-base">
            <label>
              <span className="text-label-sm font-semibold text-on-surface block">
                {clearLabel} <span className="text-on-surface-variant font-normal">({unit})</span>
              </span>
            </label>
            <p className="text-[11px] text-on-surface-variant">{hint}</p>
            <input
              type="number"
              step={step}
              inputMode="decimal"
              value={displayValue}
              onChange={(e) => {
                const raw = parseFloat(e.target.value);
                if (isNaN(raw)) {
                  onConfigChange(field, e.target.value);
                  return;
                }
                const ms = scaleToSeconds ? Math.round(raw * 1000) : raw;
                onConfigChange(field, String(ms));
              }}
              className={`w-full px-sm py-base text-label-md rounded-xl border bg-surface-container-lowest outline-none font-mono
                ${configErrors[field] ? 'border-error focus:border-error' : 'border-outline-variant focus:border-primary-container'}`}
            />
            {configErrors[field] && (
              <p className="text-label-sm text-error">{configErrors[field]}</p>
            )}
          </div>
        );
      })}

      <div className="flex gap-sm pt-sm border-t border-outline-variant/40">
        <Button
          variant="outline"
          icon="restart_alt"
          onClick={onResetRules}
          className="flex-1"
          disabled={harnessState !== 'running'}
        >
          Resetear estado
        </Button>
        <Button
          variant="ghost"
          icon="undo"
          onClick={onRestoreDefaults}
          title="Restaurar valores por defecto"
        >
          Default
        </Button>
      </div>
    </Card>
  );
}
