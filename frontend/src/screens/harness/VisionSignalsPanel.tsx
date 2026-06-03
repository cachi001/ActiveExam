/**
 * VisionSignalsPanel — interpretación de señales de visión en lenguaje claro
 * (rostros, mirada, cuerpo) + accordion de datos técnicos crudos.
 *
 * Presentacional: recibe rawSignals, engineMode y harnessState por props.
 */

import { Icon, Card, SectionTitle } from '../../ui/components';
import { Term } from '../../ui/Term';
import type { EngineMode, HarnessState, RawSignals } from './types';

interface VisionSignalsPanelProps {
  rawSignals: RawSignals;
  engineMode: EngineMode;
  harnessState: HarnessState;
}

export default function VisionSignalsPanel({
  rawSignals,
  engineMode,
  harnessState,
}: VisionSignalsPanelProps) {
  return (
    <Card className="space-y-md">
      <div className="flex items-start justify-between gap-sm flex-wrap">
        <SectionTitle sub={engineMode === 'real-active' ? 'Valores reales del motor MediaPipe' : 'Iniciá la cámara para ver valores reales'}>
          Señales de visión
        </SectionTitle>
        {/* C-30: badge REAL / SIM */}
        {engineMode === 'real-active' ? (
          <span className="inline-flex items-center gap-base px-sm py-base rounded-full bg-success-container text-success text-label-sm font-bold border border-success/30 shrink-0">
            <Icon name="sensors" className="text-[14px]" />
            REAL
          </span>
        ) : (
          <span className="inline-flex items-center gap-base px-sm py-base rounded-full bg-surface-container text-on-surface-variant text-label-sm font-bold border border-outline-variant/40 shrink-0">
            <Icon name="videocam_off" className="text-[14px]" />
            EN ESPERA
          </span>
        )}
      </div>

      {rawSignals.faceDetection === null ? (
        <div className="text-center py-md text-on-surface-variant space-y-base">
          <Icon name="face" className="text-[32px]" />
          <p className="text-label-sm">Sin datos — inicia la cámara para ver señales.</p>
        </div>
      ) : (
        <div className="space-y-sm">
          {/* ---- Tarjetas de interpretación en lenguaje claro (tasks 5.2–5.4) ---- */}
          {/* Tarjeta: Rostros */}
          <div className={`flex items-center gap-sm p-sm rounded-xl border ${
            rawSignals.faceDetection.face_count === 0
              ? 'bg-warning-container/40 border-warning/30'
              : rawSignals.faceDetection.face_count >= 2
              ? 'bg-error-container/40 border-error/30'
              : 'bg-success-container/40 border-success/30'
          }`}>
            <Icon
              name={rawSignals.faceDetection.face_count === 1 ? 'person' : rawSignals.faceDetection.face_count === 0 ? 'person_off' : 'group'}
              className={`text-[20px] shrink-0 ${
                rawSignals.faceDetection.face_count === 1 ? 'text-success'
                : rawSignals.faceDetection.face_count === 0 ? 'text-warning'
                : 'text-error'
              }`}
              fill
            />
            <span className="text-label-md font-semibold text-on-surface">
              {rawSignals.faceDetection.face_count === 1
                ? 'Se detectó 1 persona frente a la cámara'
                : rawSignals.faceDetection.face_count === 0
                ? 'No se detectó ninguna persona'
                : `Se detectaron ${rawSignals.faceDetection.face_count} personas`}
            </span>
            <span className={`ml-auto text-[10px] uppercase font-bold opacity-80 ${engineMode === 'real-active' ? 'text-success' : 'text-warning'}`}>{engineMode === 'real-active' ? '[REAL]' : '[SIM]'}</span>
          </div>

          {/* Tarjeta: Mirada (task 5.3) */}
          {rawSignals.faceMesh ? (() => {
            const gazeOk = Math.abs(rawSignals.faceMesh.gaze.x) < 0.15 && Math.abs(rawSignals.faceMesh.gaze.y) < 0.15;
            return (
              <div className={`flex items-center gap-sm p-sm rounded-xl border ${
                gazeOk ? 'bg-success-container/40 border-success/30' : 'bg-warning-container/40 border-warning/30'
              }`}>
                <Icon name={gazeOk ? 'visibility' : 'remove_red_eye'} className={`text-[20px] shrink-0 ${gazeOk ? 'text-success' : 'text-warning'}`} fill />
                <span className="text-label-md font-semibold text-on-surface">
                  {gazeOk ? 'Mirando hacia el frente' : 'Mirando hacia un lado'}
                </span>
                <span className={`ml-auto text-[10px] uppercase font-bold opacity-80 ${engineMode === 'real-active' ? 'text-success' : 'text-warning'}`}>{engineMode === 'real-active' ? '[REAL]' : '[SIM]'}</span>
              </div>
            );
          })() : rawSignals.faceDetection.face_count === 0 ? (
            <div className="flex items-center gap-sm p-sm rounded-xl border bg-surface-container-low border-outline-variant/40">
              <Icon name="visibility_off" className="text-[20px] text-on-surface-variant shrink-0" />
              <span className="text-label-sm text-on-surface-variant">Mirada: sin rostro detectado</span>
            </div>
          ) : null}

          {/* Tarjeta: Cuerpo (task 5.4) */}
          <div className={`flex items-center gap-sm p-sm rounded-xl border ${
            rawSignals.poseAvailable ? 'bg-success-container/40 border-success/30' : 'bg-surface-container-low border-outline-variant/40'
          }`}>
            <Icon
              name={rawSignals.poseAvailable ? 'accessibility_new' : 'do_not_disturb'}
              className={`text-[20px] shrink-0 ${rawSignals.poseAvailable ? 'text-success' : 'text-on-surface-variant'}`}
              fill={rawSignals.poseAvailable}
            />
            <span className="text-label-md font-semibold text-on-surface">
              {rawSignals.poseAvailable ? 'Cuerpo presente' : 'Cuerpo no detectado'}
            </span>
            <span className={`ml-auto text-[10px] uppercase font-bold opacity-80 ${engineMode === 'real-active' ? 'text-success' : 'text-warning'}`}>{engineMode === 'real-active' ? '[REAL]' : '[SIM]'}</span>
          </div>

          {/* ---- Accordion de datos técnicos crudos (DD-29-02, tasks 5.5–5.7) ---- */}
          <details open={harnessState === 'running' && rawSignals.faceDetection.face_count !== 1 ? true : undefined}>
            <summary className="cursor-pointer select-none text-label-sm text-on-surface-variant hover:text-primary flex items-center gap-base py-base">
              <Icon name="expand_more" className="text-[16px]" />
              Ver detalle técnico (coordenadas)
            </summary>
            <div className="space-y-sm mt-sm">
              {/* Bounding boxes */}
              {rawSignals.faceDetection.faces.length > 0 ? (
                <div>
                  <p className="text-label-sm text-on-surface-variant mb-base font-semibold uppercase tracking-wide">
                    <Term termKey="bounding_box">Bounding boxes</Term>
                  </p>
                  <div className="space-y-base">
                    {rawSignals.faceDetection.faces.map((face, i) => (
                      <div key={i} className={`p-sm rounded-lg bg-surface-container-low border text-label-sm font-mono space-y-base ${
                        rawSignals.faceDetection!.face_count >= 2 ? 'border-error/40' : 'border-outline-variant/40'
                      }`}>
                        <div className="flex items-center justify-between">
                          <span className="text-on-surface-variant text-[10px] uppercase">Rostro {i + 1}</span>
                          <span className="text-success font-semibold">{(face.confidence * 100).toFixed(1)}% conf.</span>
                        </div>
                        <div className="grid grid-cols-2 gap-base">
                          <span><span className="text-on-surface-variant">x:</span> {face.x.toFixed(3)}</span>
                          <span><span className="text-on-surface-variant">y:</span> {face.y.toFixed(3)}</span>
                          <span><span className="text-on-surface-variant">w:</span> {face.width.toFixed(3)}</span>
                          <span><span className="text-on-surface-variant">h:</span> {face.height.toFixed(3)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {/* Gaze numérico */}
              {rawSignals.faceMesh ? (
                <div className="p-sm rounded-lg bg-surface-container-low border border-outline-variant/40 text-label-sm font-mono space-y-base">
                  <p className="text-on-surface-variant text-[10px] uppercase font-semibold tracking-wide">
                    <Term termKey="gaze_vector">Vector gaze</Term>
                  </p>
                  <div className="grid grid-cols-2 gap-base">
                    <span><span className="text-on-surface-variant">x:</span> {rawSignals.faceMesh.gaze.x.toFixed(4)}</span>
                    <span><span className="text-on-surface-variant">y:</span> {rawSignals.faceMesh.gaze.y.toFixed(4)}</span>
                  </div>
                </div>
              ) : rawSignals.faceDetection.face_count === 0 ? (
                <div className="p-sm rounded-lg bg-surface-container-low border border-outline-variant/40 text-label-sm text-on-surface-variant">
                  Gaze: sin rostro detectado
                </div>
              ) : null}

              {/* Pose keypoints */}
              <div className="p-sm rounded-lg bg-surface-container-low border border-outline-variant/40 text-label-sm flex items-center gap-sm">
                <Icon name={rawSignals.poseAvailable ? 'accessibility_new' : 'do_not_disturb'} className={`text-[18px] ${rawSignals.poseAvailable ? 'text-success' : 'text-on-surface-variant'}`} />
                <span className="text-on-surface">
                  <Term termKey="pose_keypoints">Pose keypoints</Term>: {rawSignals.poseAvailable ? 'disponibles' : engineMode === 'real-active' ? 'no detectados en este frame' : 'no disponibles (iniciá la cámara)'}
                </span>
              </div>
            </div>
          </details>
        </div>
      )}
    </Card>
  );
}
