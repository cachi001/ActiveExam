/**
 * CameraPanel — video + VisionOverlay + estados idle/initializing + toggles de overlay.
 *
 * Presentacional: recibe el videoRef, las señales y los toggles por props.
 */

import type { RefObject } from 'react';
import { Icon, Card } from '../../ui/components';
import VisionOverlay from '../../ui/VisionOverlay';
import type { EngineMode, HarnessState, RawSignals } from './types';

interface CameraPanelProps {
  videoRef: RefObject<HTMLVideoElement>;
  engineMode: EngineMode;
  harnessState: HarnessState;
  rawSignals: RawSignals;
  showPose: boolean;
  setShowPose: (v: boolean) => void;
  showFullMesh: boolean;
  setShowFullMesh: (v: boolean) => void;
}

export default function CameraPanel({
  videoRef,
  engineMode,
  harnessState,
  rawSignals,
  showPose,
  setShowPose,
  showFullMesh,
  setShowFullMesh,
}: CameraPanelProps) {
  return (
    <>
      {/* Cámara + VisionOverlay (C-30: canvas superpuesto) */}
      <Card padded={false} className="overflow-hidden">
        <div className="relative aspect-video bg-inverse-surface" style={{ position: 'relative' }}>
          <video ref={videoRef} muted playsInline className="w-full h-full object-cover" />
          {/* C-30: canvas overlay — solo visible cuando el motor real está activo */}
          {engineMode === 'real-active' && (
            <VisionOverlay
              rawSignals={rawSignals.faceDetection ? rawSignals : null}
              videoRef={videoRef}
              showFullMesh={showFullMesh}
              showPose={showPose}
            />
          )}
          {harnessState === 'idle' || harnessState === 'stopped' ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-on-surface-variant gap-sm">
              <Icon name="videocam_off" className="text-[40px]" />
              <span className="text-label-sm">Cámara inactiva</span>
            </div>
          ) : null}
          {harnessState === 'initializing' && (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-on-surface-variant gap-sm">
              <Icon name="hourglass_empty" className="text-[40px] animate-spin" />
              <span className="text-label-sm">Inicializando motor…</span>
            </div>
          )}
        </div>
      </Card>

      {/* C-30: Toggles del overlay — visibles cuando el motor real está activo */}
      {engineMode === 'real-active' && (
        <Card className="space-y-sm">
          <p className="text-label-sm font-semibold text-on-surface">Overlay de visión</p>
          <div className="flex items-center gap-md flex-wrap">
            <label className="flex items-center gap-sm cursor-pointer select-none">
              <input
                type="checkbox"
                checked={showPose}
                onChange={(e) => setShowPose(e.target.checked)}
                className="w-4 h-4 accent-primary rounded"
              />
              <span className="text-label-sm text-on-surface">
                <Icon name="accessibility_new" className="text-[14px] inline mr-base" />
                Pose (keypoints corporales)
              </span>
            </label>
            <label className="flex items-center gap-sm cursor-pointer select-none">
              <input
                type="checkbox"
                checked={showFullMesh}
                onChange={(e) => setShowFullMesh(e.target.checked)}
                className="w-4 h-4 accent-primary rounded"
              />
              <span className="text-label-sm text-on-surface">
                <Icon name="face" className="text-[14px] inline mr-base" />
                Mesh completo (468 pts) — diagnóstico de staff
              </span>
            </label>
          </div>
        </Card>
      )}
    </>
  );
}
