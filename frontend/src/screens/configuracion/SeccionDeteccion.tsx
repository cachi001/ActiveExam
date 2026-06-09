/**
 * SeccionDeteccion — umbrales del motor de detección (default del sistema).
 *
 * Mismos parámetros que el harness diagnóstico, pero como configuración global:
 * cuánto tolera el motor antes de emitir cada evento. Los campos en ms se
 * muestran/editan en segundos (1:1). En demo el guardado es local (toast).
 */
import { useState } from 'react';
import { Card, SectionTitle, Button } from '../../ui/components';
import { useToast } from '../../ui/toast';
import { DEFAULT_CONFIG } from '../../proctoring/stateTransitionRules';
import type { TransitionConfig } from '../../proctoring/stateTransitionRules';

interface Campo {
  field: keyof TransitionConfig;
  label: string;
  unit: string;
  scaleToSeconds: boolean;
  step: number;
  hint: string;
}

const CAMPOS: Campo[] = [
  { field: 'face_absent_ms', label: 'Tiempo sin rostro para alertar', unit: 's', scaleToSeconds: true, step: 0.1, hint: 'Tiempo sin detectar un rostro antes de emitir una alerta.' },
  { field: 'multiple_faces_frames', label: 'Fotogramas con varios rostros', unit: 'frames', scaleToSeconds: false, step: 1, hint: 'Fotogramas consecutivos con más de un rostro para alertar.' },
  { field: 'gaze_deviation_threshold', label: 'Sensibilidad de mirada desviada', unit: '0–1', scaleToSeconds: false, step: 0.01, hint: 'Cuán lejos del centro puede mirar (0 = muy sensible, 1 = tolerante).' },
  { field: 'gaze_sustained_ms', label: 'Tiempo de mirada desviada para alertar', unit: 's', scaleToSeconds: true, step: 0.1, hint: 'Tiempo continuo mirando hacia un lado antes de alertar.' },
  { field: 'gaze_fixation_tolerance', label: 'Tolerancia de fijación de mirada', unit: '0–1', scaleToSeconds: false, step: 0.01, hint: 'Variación permitida para considerar la mirada sostenida en un punto.' },
];

export default function SeccionDeteccion() {
  const toast = useToast();
  const [cfg, setCfg] = useState<TransitionConfig>({ ...DEFAULT_CONFIG });
  const [guardando, setGuardando] = useState(false);

  function setCampo(campo: Campo, raw: string) {
    const num = parseFloat(raw);
    if (isNaN(num)) return;
    const value = campo.scaleToSeconds ? Math.round(num * 1000) : num;
    setCfg((prev) => ({ ...prev, [campo.field]: value }));
  }

  async function guardar() {
    setGuardando(true);
    await new Promise((r) => setTimeout(r, 300));
    setGuardando(false);
    toast.success('Umbrales de detección guardados');
  }

  return (
    <Card className="space-y-md max-w-4xl">
      <SectionTitle sub="Defaults conservadores — minimizan falsos positivos">Umbrales de detección</SectionTitle>
      <div className="grid sm:grid-cols-2 gap-md">
        {CAMPOS.map((campo) => {
          const display = campo.scaleToSeconds ? cfg[campo.field] / 1000 : cfg[campo.field];
          return (
            <div key={campo.field} className="space-y-base">
              <label className="block">
                <span className="text-label-sm font-semibold text-on-surface">
                  {campo.label} <span className="text-on-surface-variant font-normal">({campo.unit})</span>
                </span>
              </label>
              <p className="text-[11px] text-on-surface-variant">{campo.hint}</p>
              <input
                type="number"
                step={campo.step}
                inputMode="decimal"
                value={display}
                onChange={(e) => setCampo(campo, e.target.value)}
                className="w-full px-sm py-base text-label-md rounded-xl border border-outline-variant bg-white font-mono focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              />
            </div>
          );
        })}
      </div>
      <div className="flex justify-end gap-sm pt-sm border-t border-outline-variant/40">
        <Button variant="ghost" icon="undo" onClick={() => setCfg({ ...DEFAULT_CONFIG })}>Restaurar defaults</Button>
        <Button icon="save" onClick={guardar} disabled={guardando}>{guardando ? 'Guardando…' : 'Guardar umbrales'}</Button>
      </div>
    </Card>
  );
}
