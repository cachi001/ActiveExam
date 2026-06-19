/**
 * ThresholdsConfig — panel de configuración de umbrales del pipeline.
 *
 * Presentacional: recibe el draft de config, los errores y los callbacks
 * (cambio de campo, reset de reglas, restaurar defaults) por props.
 *
 * C-68 UX: agrupado en sub-secciones (Rostro en cámara / Mirada) con controles
 * amigables idénticos a SeccionDeteccion: segundos para tiempos, segmented
 * Alta/Media/Baja para sensibilidades. Convierte a/desde unidades internas vía
 * configScale. Este panel es SANDBOX — no persiste; onConfigChange emite el
 * valor INTERNO (ms / 0..1) para que el hook lo aplique al pipeline en vivo.
 */

import { Card, Button, SectionTitle } from '../../ui/components';
import {
  SENSIBILIDAD_OPTIONS,
  msToSeg,
  segToMs,
  gazeDeviationToLabel,
  gazeFixationToLabel,
  labelToGazeDeviation,
  labelToGazeFixation,
} from '../../config/configScale';
import type { SensibilidadLabel } from '../../config/configScale';
import type { TransitionConfig } from '../../proctoring/stateTransitionRules';
import type { ConfigErrors, HarnessState } from './types';

interface ThresholdsConfigProps {
  configDraft: TransitionConfig;
  configErrors: ConfigErrors;
  harnessState: HarnessState;
  onConfigChange: (field: keyof TransitionConfig, rawValue: string) => void;
  onRestoreSystem: () => void;
}

/** Clase base de los inputs de número — igual que SeccionDeteccion. */
const INPUT_CLASS =
  'w-full px-sm py-base text-label-md rounded-xl border border-outline-variant bg-white font-mono focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors';

export default function ThresholdsConfig({
  configDraft,
  configErrors,
  harnessState: _harnessState,
  onConfigChange,
  onRestoreSystem,
}: ThresholdsConfigProps) {
  // Valores amigables derivados del draft interno
  const faceAbsentSeg = msToSeg(configDraft.face_absent_ms);
  const gazeDeviationLabel = gazeDeviationToLabel(configDraft.gaze_deviation_threshold);
  const gazeSustainedSeg = msToSeg(configDraft.gaze_sustained_ms);
  const gazeFixationLabel = gazeFixationToLabel(configDraft.gaze_fixation_tolerance);

  function handleFaceAbsentSeg(val: string) {
    const seg = parseFloat(val);
    if (!isNaN(seg)) onConfigChange('face_absent_ms', String(segToMs(seg)));
  }

  function handleMultipleFacesFrames(val: string) {
    const frames = parseInt(val, 10);
    if (!isNaN(frames)) onConfigChange('multiple_faces_frames', String(frames));
  }

  function handleGazeDeviationLabel(label: SensibilidadLabel) {
    onConfigChange('gaze_deviation_threshold', String(labelToGazeDeviation(label)));
  }

  function handleGazeSustainedSeg(val: string) {
    const seg = parseFloat(val);
    if (!isNaN(seg)) onConfigChange('gaze_sustained_ms', String(segToMs(seg)));
  }

  function handleGazeFixationLabel(label: SensibilidadLabel) {
    onConfigChange('gaze_fixation_tolerance', String(labelToGazeFixation(label)));
  }

  return (
    <Card className="space-y-md">
      <SectionTitle sub="Arrancan desde la Configuración del sistema. Cambialos para probar cómo reacciona la detección en vivo — se aplican al instante.">
        Umbrales de prueba
      </SectionTitle>

      {/* Sub-sección: Rostro en cámara */}
      <Card className="space-y-md">
        <SectionTitle sub="Cuándo el sistema alerta por ausencia o exceso de personas en cámara">
          Rostro en cámara
        </SectionTitle>

        <div className="grid sm:grid-cols-2 gap-md">
          {/* face_absent_ms → segundos */}
          <div className="space-y-base min-w-0">
            <label className="block">
              <span className="text-label-sm font-semibold text-on-surface">
                Tiempo sin rostro para alertar <span className="text-on-surface-variant font-normal">(segundos)</span>
              </span>
            </label>
            <p className="text-[11px] text-on-surface-variant">
              Cuánto tiempo puede no verse un rostro antes de marcar el evento. Ej.: 3 segundos.
            </p>
            <input
              type="number"
              step={0.1}
              min={0.5}
              max={30}
              inputMode="decimal"
              value={faceAbsentSeg}
              onChange={(e) => handleFaceAbsentSeg(e.target.value)}
              className={`${INPUT_CLASS}${configErrors.face_absent_ms ? ' border-error' : ''}`}
            />
            {configErrors.face_absent_ms && (
              <p className="text-label-sm text-error">{configErrors.face_absent_ms}</p>
            )}
          </div>

          {/* multiple_faces_frames — número entero */}
          <div className="space-y-base min-w-0">
            <label className="block">
              <span className="text-label-sm font-semibold text-on-surface">
                Detecciones seguidas con varios rostros
              </span>
            </label>
            <p className="text-[11px] text-on-surface-variant">
              Cuántas veces seguidas se ve más de un rostro antes de marcar el evento. Ej.: 5 veces.
            </p>
            <input
              type="number"
              step={1}
              min={1}
              max={100}
              value={configDraft.multiple_faces_frames}
              onChange={(e) => handleMultipleFacesFrames(e.target.value)}
              className={`${INPUT_CLASS}${configErrors.multiple_faces_frames ? ' border-error' : ''}`}
            />
            {configErrors.multiple_faces_frames && (
              <p className="text-label-sm text-error">{configErrors.multiple_faces_frames}</p>
            )}
          </div>
        </div>
      </Card>

      {/* Sub-sección: Mirada */}
      <Card className="space-y-md">
        <SectionTitle sub="Tolerancia y tiempo antes de alertar por mirada fuera de pantalla">
          Mirada
        </SectionTitle>

        <div className="grid sm:grid-cols-2 gap-md">
          {/* gaze_deviation_threshold → segmented Alta/Media/Baja */}
          <div className="space-y-base min-w-0">
            <label className="block">
              <span className="text-label-sm font-semibold text-on-surface">
                Sensibilidad de detección de mirada desviada
              </span>
            </label>
            <p className="text-[11px] text-on-surface-variant">
              Alta = más alertas (mayor precisión); Baja = menos alertas (más tolerancia).
            </p>
            <div className="flex gap-sm">
              {SENSIBILIDAD_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => handleGazeDeviationLabel(opt.value as SensibilidadLabel)}
                  className={`flex-1 py-sm px-base rounded-xl border text-label-sm font-medium transition-colors ${
                    gazeDeviationLabel === opt.value
                      ? 'bg-primary text-on-primary border-primary'
                      : 'bg-white text-on-surface border-outline-variant hover:border-primary/50'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <p className="text-[10px] text-on-surface-variant/70">
              {SENSIBILIDAD_OPTIONS.find((o) => o.value === gazeDeviationLabel)?.desc}
            </p>
          </div>

          {/* gaze_sustained_ms → segundos */}
          <div className="space-y-base min-w-0">
            <label className="block">
              <span className="text-label-sm font-semibold text-on-surface">
                Tiempo de mirada desviada para alertar <span className="text-on-surface-variant font-normal">(segundos)</span>
              </span>
            </label>
            <p className="text-[11px] text-on-surface-variant">
              Cuánto tiempo seguido puede mirar hacia un lado antes de marcar el evento. Ej.: 2,5 segundos.
            </p>
            <input
              type="number"
              step={0.1}
              min={0.5}
              max={30}
              inputMode="decimal"
              value={gazeSustainedSeg}
              onChange={(e) => handleGazeSustainedSeg(e.target.value)}
              className={`${INPUT_CLASS}${configErrors.gaze_sustained_ms ? ' border-error' : ''}`}
            />
            {configErrors.gaze_sustained_ms && (
              <p className="text-label-sm text-error">{configErrors.gaze_sustained_ms}</p>
            )}
          </div>

          {/* gaze_fixation_tolerance → segmented Alta/Media/Baja */}
          <div className="space-y-base min-w-0 sm:col-span-2">
            <label className="block">
              <span className="text-label-sm font-semibold text-on-surface">
                Tolerancia de fijación de mirada
              </span>
            </label>
            <p className="text-[11px] text-on-surface-variant">
              Alta = más alertas (exige que la mirada no se mueva); Baja = permite más variación natural.
            </p>
            <div className="flex gap-sm max-w-sm">
              {SENSIBILIDAD_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => handleGazeFixationLabel(opt.value as SensibilidadLabel)}
                  className={`flex-1 py-sm px-base rounded-xl border text-label-sm font-medium transition-colors ${
                    gazeFixationLabel === opt.value
                      ? 'bg-primary text-on-primary border-primary'
                      : 'bg-white text-on-surface border-outline-variant hover:border-primary/50'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <p className="text-[10px] text-on-surface-variant/70">
              {SENSIBILIDAD_OPTIONS.find((o) => o.value === gazeFixationLabel)?.desc}
            </p>
          </div>
        </div>
      </Card>

      {/* Footer */}
      <div className="flex justify-end pt-sm border-t border-outline-variant/40">
        <Button
          variant="outline"
          icon="settings_backup_restore"
          onClick={onRestoreSystem}
          title="Descartar los cambios de prueba y volver a la Configuración del sistema"
        >
          Volver a la config del sistema
        </Button>
      </div>
    </Card>
  );
}
