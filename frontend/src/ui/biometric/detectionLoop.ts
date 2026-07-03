import type { MutableRefObject, RefObject } from 'react';
import {
  variance, stddev, medirLuminancia,
  HINT_STABLE_FRAMES, NEUTRAL_GATE_FRAMES, MAX_FRAME_DT_MS,
  BASELINE_WARMUP_FRAMES, BASELINE_MIN_FRAMES, BASELINE_TIMEOUT_FRAMES,
  BASELINE_NOSE_VARIANCE_THRESHOLD,
} from './biometricUtils';
import { evaluateFraming, isHintBloqueante, isFrontal, type FramingHint } from './framingGuide';
import { playHint, playGestureProgress, playGestureLost } from './sounds';
import type { OvalTono } from './CaptureOval';
import {
  evaluateChallengeRelative,
  computeBaselineFromAccumulator,
  isBaselineSmileValid,
  gestureAccumulator,
  GESTURE_HOLD_MS,
  SMILE_GESTURE_HOLD_MS,
  type BaselineFrame,
} from '../../vision/enrollmentChallengeDetector';
import {
  derivePassiveSignals,
  passivePassed,
  detectVirtualCamera,
  type BaselineMetrics,
  type SequentialChallenge,
  type TurnDirection,
} from '../../vision/liveness';
import type { FaceLandmark, VisionEngine } from '../../vision/VisionEngine';

export type Fase = 'capturando' | 'exito' | 'error';

export interface DetectionLoopDeps {
  faseRef: MutableRefObject<Fase>;
  videoRef: RefObject<HTMLVideoElement>;
  rafHandleRef: MutableRefObject<number | null>;
  engineRef: MutableRefObject<VisionEngine | null>;
  luminanceCanvasRef: MutableRefObject<HTMLCanvasElement | null>;
  framingStableRef: MutableRefObject<{ hint: FramingHint | null; frames: number }>;
  framingHintRef: MutableRefObject<FramingHint | null>;
  livenessWindowRef: MutableRefObject<Array<{
    blinkL: number; blinkR: number; noseX: number; noseY: number;
    minZ: number; maxZ: number; frameTime: number;
  }>>;
  passiveOkRef: MutableRefObject<boolean>;
  passiveFalseFramesRef: MutableRefObject<number>;
  prevFrameDataRef: MutableRefObject<ImageData | null>;
  virtualCameraRef: MutableRefObject<boolean>;
  wasBlockedByFramingRef: MutableRefObject<boolean>;
  baselineRef: MutableRefObject<BaselineMetrics | null>;
  baselineFrameCountRef: MutableRefObject<number>;
  baselineAccumulatorRef: MutableRefObject<BaselineFrame[]>;
  nosePositionsRef: MutableRefObject<Array<{ x: number; y: number }>>;
  bestReferenceFrameRef: MutableRefObject<HTMLCanvasElement | null>;
  cooldownActiveRef: MutableRefObject<boolean>;
  challengeIndexRef: MutableRefObject<number>;
  desafiosBarajadosRef: MutableRefObject<SequentialChallenge[]>;
  completadosRef: MutableRefObject<number>;
  challengeCountsRef: MutableRefObject<Map<SequentialChallenge, number>>;
  challengeNeutralFramesRef: MutableRefObject<Map<SequentialChallenge, number>>;
  gestureAccumMsRef: MutableRefObject<Map<SequentialChallenge, number>>;
  gestureLostMsRef: MutableRefObject<Map<SequentialChallenge, number>>;
  lastFrameTimeRef: MutableRefObject<number | null>;
  wasHoldingRef: MutableRefObject<Map<SequentialChallenge, boolean>>;
  lastProgressTickFractionRef: MutableRefObject<number>;
  turnDirectionRef: MutableRefObject<TurnDirection>;
  lastLandmarksRef: MutableRefObject<FaceLandmark[]>;
  setFramingHint: (hint: FramingHint | null) => void;
  setTonoOvalo: (tono: OvalTono) => void;
  setProgreso: (p: number) => void;
  activarCooldown: (retoId: SequentialChallenge) => void;
}

export function startDetectionLoop(engine: VisionEngine, deps: DetectionLoopDeps): void {
  const {
    faseRef, videoRef, rafHandleRef, engineRef,
    luminanceCanvasRef, framingStableRef, framingHintRef,
    livenessWindowRef, passiveOkRef, passiveFalseFramesRef,
    prevFrameDataRef, virtualCameraRef, wasBlockedByFramingRef,
    baselineRef, baselineFrameCountRef, baselineAccumulatorRef,
    nosePositionsRef, bestReferenceFrameRef, cooldownActiveRef,
    challengeIndexRef, desafiosBarajadosRef, completadosRef,
    challengeCountsRef, challengeNeutralFramesRef, gestureAccumMsRef,
    gestureLostMsRef, lastFrameTimeRef, wasHoldingRef,
    lastProgressTickFractionRef, turnDirectionRef, lastLandmarksRef,
    setFramingHint, setTonoOvalo, setProgreso, activarCooldown,
  } = deps;

  engineRef.current = engine;

  const detectFrame = async () => {
    if (faseRef.current !== 'capturando') {
      rafHandleRef.current = null;
      return;
    }

    if (videoRef.current && videoRef.current.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
      try {
        const bitmap = await createImageBitmap(videoRef.current);

        const [meshResult, faceResult] = await Promise.all([
          engine.detectFaceMesh(bitmap),
          engine.detectFaces(bitmap),
        ]);

        bitmap.close();

        const { landmarks, gaze, smile } = meshResult;
        const face_count = faceResult.face_count;

        let bboxWidth: number | null = null;
        let centerX: number | null = null;
        let centerY: number | null = null;
        if (face_count > 0 && landmarks.length > 0) {
          let minX = 1, maxX = 0, minY = 1, maxY = 0;
          for (const l of landmarks) {
            if (l.x < minX) minX = l.x;
            if (l.x > maxX) maxX = l.x;
            if (l.y < minY) minY = l.y;
            if (l.y > maxY) maxY = l.y;
          }
          bboxWidth = Math.max(0, Math.min(1, maxX - minX));
          centerX = (minX + maxX) / 2;
          centerY = (minY + maxY) / 2;
        }
        const lum = medirLuminancia(videoRef.current, luminanceCanvasRef);
        let hintAhora = evaluateFraming({
          faceCount: face_count,
          luminanceAvg: lum,
          faceBboxWidth: bboxWidth,
          faceCenterX: centerX,
          faceCenterY: centerY,
        });
        if (hintAhora === null) {
          let retoEsGiro = false;
          if (baselineRef.current !== null) {
            const retoActivo = desafiosBarajadosRef.current[challengeIndexRef.current];
            retoEsGiro = typeof retoActivo === 'string' && retoActivo.startsWith('girar');
          }
          if (!retoEsGiro && !isFrontal(landmarks)) {
            hintAhora = 'no_frontal';
          }
        }
        const estable = framingStableRef.current;
        if (estable.hint === hintAhora) {
          estable.frames = Math.min(estable.frames + 1, HINT_STABLE_FRAMES + 1);
        } else {
          estable.hint = hintAhora;
          estable.frames = 1;
        }
        if (estable.frames >= HINT_STABLE_FRAMES && framingHintRef.current !== hintAhora) {
          framingHintRef.current = hintAhora;
          setFramingHint(hintAhora);
          setTonoOvalo(hintAhora ? 'aviso' : 'ok');
          if (hintAhora) playHint();
        }

        if (face_count > 0 && landmarks.length > 0) {
          lastLandmarksRef.current = landmarks;

          const blinkL = Math.abs(landmarks[159].y - landmarks[145].y);
          const blinkR = landmarks.length > 386 ? Math.abs(landmarks[386].y - landmarks[374].y) : blinkL;
          const noseX  = landmarks[1].x;
          const noseY  = landmarks[1].y;
          const allZ   = landmarks.map((l) => l.z);
          const minZ   = Math.min(...allZ);
          const maxZ   = Math.max(...allZ);
          const frameTime = performance.now();

          const win = livenessWindowRef.current;
          if (win.length >= 15) win.shift();
          win.push({ blinkL, blinkR, noseX, noseY, minZ, maxZ, frameTime });

          const blinkVariance  = variance([...win.map((f) => f.blinkL), ...win.map((f) => f.blinkR)]);
          const motionVariance = variance([...win.map((f) => f.noseX), ...win.map((f) => f.noseY)]);
          const depthRange     = Math.max(...win.map((f) => f.maxZ)) - Math.min(...win.map((f) => f.minZ));

          const signals = derivePassiveSignals({ blinkVariance, motionVariance, depthRange });
          const livenessOk = passivePassed(signals);
          passiveOkRef.current = livenessOk;

          if (livenessOk) {
            passiveFalseFramesRef.current = 0;
          } else {
            passiveFalseFramesRef.current += 1;
          }

          const frameTimes = win.map((f) => f.frameTime);
          const frameIntervals = frameTimes.slice(1).map((t, i) => t - frameTimes[i]);
          const frameRateJitter = stddev(frameIntervals);
          const faceCountStability = face_count === 1 ? win.length / 15 : 0;

          let interFramePixelVariance = 0;
          try {
            const offscreen = document.createElement('canvas');
            offscreen.width  = 16;
            offscreen.height = 12;
            const ctx2d = offscreen.getContext('2d');
            if (ctx2d && videoRef.current) {
              ctx2d.drawImage(videoRef.current, 0, 0, 16, 12);
              const currentData = ctx2d.getImageData(0, 0, 16, 12);
              if (prevFrameDataRef.current) {
                const prev = prevFrameDataRef.current.data;
                const curr = currentData.data;
                let sumSqDiff = 0;
                for (let i = 0; i < prev.length; i += 4) {
                  const diff = (curr[i] - prev[i]) / 255;
                  sumSqDiff += diff * diff;
                }
                interFramePixelVariance = sumSqDiff / (prev.length / 4);
              }
              prevFrameDataRef.current = currentData;
            }
          } catch {
            // Canvas bloqueado → usar 0
          }

          if (detectVirtualCamera({ interFramePixelVariance, frameRateJitter, faceCountStability })) {
            virtualCameraRef.current = true;
          }

          if (baselineRef.current === null) {
            baselineFrameCountRef.current += 1;
            const frameCount = baselineFrameCountRef.current;

            if (frameCount >= BASELINE_WARMUP_FRAMES && landmarks.length >= 292) {
              const blinkOpenness = Math.abs(landmarks[159].y - landmarks[145].y);
              const smileWidth    = Math.abs(landmarks[291].x - landmarks[61].x);
              const gazeX         = gaze.x;
              const smileCornerY  = (landmarks[61].y + landmarks[291].y) / 2;

              baselineAccumulatorRef.current.push({ blinkOpenness, smileWidth, gazeX, smileCornerY });
              nosePositionsRef.current.push({ x: noseX, y: noseY });

              const acc = baselineAccumulatorRef.current;
              if (acc.length >= BASELINE_MIN_FRAMES) {
                const noseXArr = nosePositionsRef.current.map((p) => p.x);
                const noseYArr = nosePositionsRef.current.map((p) => p.y);
                const noseVariance = variance(noseXArr) + variance(noseYArr);

                if (noseVariance < BASELINE_NOSE_VARIANCE_THRESHOLD && isFrontal(landmarks)) {
                  const avgSmileWidth = acc.reduce((s, f) => s + f.smileWidth, 0) / acc.length;

                  if (!isBaselineSmileValid(avgSmileWidth)) {
                    baselineAccumulatorRef.current = [];
                    nosePositionsRef.current = [];
                  } else {
                    const baseline = computeBaselineFromAccumulator(acc);
                    if (baseline) {
                      baselineRef.current = baseline;
                      const video = videoRef.current;
                      if (video && video.videoWidth > 0) {
                        try {
                          const canvas = document.createElement('canvas');
                          canvas.width = video.videoWidth;
                          canvas.height = video.videoHeight;
                          const ctx = canvas.getContext('2d');
                          if (ctx) {
                            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                            bestReferenceFrameRef.current = canvas;
                          }
                        } catch {
                          // Si falla, bestReferenceFrameRef queda null → fallback en procesarCompletado
                        }
                      }
                    }
                  }
                }
              }
            }

            if (frameCount >= BASELINE_TIMEOUT_FRAMES && baselineRef.current === null) {
              const acc = baselineAccumulatorRef.current;
              const ultimosDiez = acc.slice(-10);
              if (ultimosDiez.length >= 1) {
                const n = ultimosDiez.length;
                const blinkOpenness = ultimosDiez.reduce((s, f) => s + f.blinkOpenness, 0) / n;
                const smileWidth    = ultimosDiez.reduce((s, f) => s + f.smileWidth, 0) / n;
                const gazeX         = ultimosDiez.reduce((s, f) => s + f.gazeX, 0) / n;
                const cornerFrames = ultimosDiez.filter((f) => f.smileCornerY !== undefined);
                const smileCornerY = cornerFrames.length > 0
                  ? cornerFrames.reduce((s, f) => s + (f.smileCornerY ?? 0), 0) / cornerFrames.length
                  : undefined;
                baselineRef.current = { blinkOpenness: Math.max(blinkOpenness, 0.01), smileWidth, gazeX, smileCornerY };
              } else {
                baselineRef.current = { blinkOpenness: 0.05, smileWidth: 0.08, gazeX: 0 };
              }
              const video = videoRef.current;
              if (video && video.videoWidth > 0 && bestReferenceFrameRef.current === null) {
                try {
                  const canvas = document.createElement('canvas');
                  canvas.width = video.videoWidth;
                  canvas.height = video.videoHeight;
                  const ctx = canvas.getContext('2d');
                  if (ctx) {
                    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                    bestReferenceFrameRef.current = canvas;
                  }
                } catch { /* ignorar */ }
              }
            }

            if (baselineRef.current === null) {
              if (faseRef.current === 'capturando') {
                rafHandleRef.current = requestAnimationFrame(() => { void detectFrame(); });
              } else {
                rafHandleRef.current = null;
              }
              return;
            }
          }

          if (cooldownActiveRef.current) {
            lastFrameTimeRef.current = null;
            if (faseRef.current === 'capturando') {
              rafHandleRef.current = requestAnimationFrame(() => { void detectFrame(); });
            } else {
              rafHandleRef.current = null;
            }
            return;
          }

          if (isHintBloqueante(framingHintRef.current)) {
            wasBlockedByFramingRef.current = true;
            lastFrameTimeRef.current = null;
            if (faseRef.current === 'capturando') {
              rafHandleRef.current = requestAnimationFrame(() => { void detectFrame(); });
            } else {
              rafHandleRef.current = null;
            }
            return;
          }

          if (wasBlockedByFramingRef.current) {
            wasBlockedByFramingRef.current = false;
            const idxReset = challengeIndexRef.current;
            const barReset = desafiosBarajadosRef.current;
            if (idxReset < barReset.length) {
              challengeCountsRef.current.set(barReset[idxReset], 0);
              challengeNeutralFramesRef.current.set(barReset[idxReset], 0);
              gestureAccumMsRef.current.set(barReset[idxReset], 0);
              gestureLostMsRef.current.set(barReset[idxReset], 0);
              lastProgressTickFractionRef.current = 0;
            }
          }

          const idx = challengeIndexRef.current;
          const barajados = desafiosBarajadosRef.current;
          if (idx >= barajados.length) {
            if (faseRef.current === 'capturando') {
              rafHandleRef.current = requestAnimationFrame(() => { void detectFrame(); });
            } else {
              rafHandleRef.current = null;
            }
            return;
          }

          const retoActivo = barajados[idx];

          const gestureHoldForReto =
            retoActivo === 'sonreír' ? SMILE_GESTURE_HOLD_MS : GESTURE_HOLD_MS;

          if (face_count === 0) {
            challengeCountsRef.current.set(retoActivo, 0);
            challengeNeutralFramesRef.current.set(retoActivo, 0);
            gestureAccumMsRef.current.set(retoActivo, 0);
            gestureLostMsRef.current.set(retoActivo, 0);
            lastFrameTimeRef.current = null;
            lastProgressTickFractionRef.current = 0;
          } else {
            const cumple = evaluateChallengeRelative(
              retoActivo,
              landmarks,
              gaze,
              baselineRef.current,
              turnDirectionRef.current,
              smile,
            );

            const prevCount = challengeCountsRef.current.get(retoActivo) ?? 0;
            const neutralVistos = challengeNeutralFramesRef.current.get(retoActivo) ?? 0;
            const neutralListo = neutralVistos >= NEUTRAL_GATE_FRAMES;

            const nowMs = performance.now();
            const rawDt = lastFrameTimeRef.current !== null ? nowMs - lastFrameTimeRef.current : 0;
            const dt = Math.min(rawDt, MAX_FRAME_DT_MS);
            lastFrameTimeRef.current = nowMs;

            if (cumple) {
              if (!neutralListo) {
                challengeCountsRef.current.set(retoActivo, 0);
              } else {
                const prevAccumMs = gestureAccumMsRef.current.get(retoActivo) ?? 0;
                const prevWasHolding = wasHoldingRef.current.get(retoActivo) ?? false;
                const accumResult = gestureAccumulator({
                  prevAccumMs,
                  cumple: true,
                  dt,
                  gestureHoldMs: gestureHoldForReto,
                  prevLostMs: gestureLostMsRef.current.get(retoActivo) ?? 0,
                });
                gestureAccumMsRef.current.set(retoActivo, accumResult.accumMs);
                gestureLostMsRef.current.set(retoActivo, accumResult.lostMs);
                wasHoldingRef.current.set(retoActivo, true);

                challengeCountsRef.current.set(retoActivo, prevCount + 1);

                const fracCurrent = accumResult.fracReto;
                if (Math.floor(fracCurrent * 4) > Math.floor(lastProgressTickFractionRef.current * 4)) {
                  playGestureProgress();
                  lastProgressTickFractionRef.current = fracCurrent;
                }

                if (!prevWasHolding) {
                  // Reanudación desde pausa — no reproducir nada extra aquí
                }

                if (accumResult.confirmado) {
                  challengeCountsRef.current.set(retoActivo, 0);
                  challengeNeutralFramesRef.current.set(retoActivo, 0);
                  gestureAccumMsRef.current.set(retoActivo, 0);
                  gestureLostMsRef.current.set(retoActivo, 0);
                  wasHoldingRef.current.set(retoActivo, false);
                  lastProgressTickFractionRef.current = 0;
                  completadosRef.current += 1;
                  activarCooldown(retoActivo);
                }
              }
            } else {
              const prevAccumMs = gestureAccumMsRef.current.get(retoActivo) ?? 0;
              const prevWasHolding = wasHoldingRef.current.get(retoActivo) ?? false;
              const accumResult = gestureAccumulator({
                prevAccumMs,
                cumple: false,
                dt,
                gestureHoldMs: gestureHoldForReto,
                prevLostMs: gestureLostMsRef.current.get(retoActivo) ?? 0,
              });
              gestureAccumMsRef.current.set(retoActivo, accumResult.accumMs);
              gestureLostMsRef.current.set(retoActivo, accumResult.lostMs);
              wasHoldingRef.current.set(retoActivo, false);

              if (prevWasHolding && prevAccumMs > 0) {
                playGestureLost();
              }

              challengeCountsRef.current.set(retoActivo, 0);
              challengeNeutralFramesRef.current.set(
                retoActivo,
                Math.min(neutralVistos + 1, NEUTRAL_GATE_FRAMES),
              );
            }

            const totalRetos = desafiosBarajadosRef.current.length;
            if (totalRetos > 0) {
              const completos = completadosRef.current;
              const accumMs = gestureAccumMsRef.current.get(retoActivo) ?? 0;
              const fracReto = Math.min(1, accumMs / gestureHoldForReto);
              setProgreso(Math.min(1, (completos + fracReto) / totalRetos));
            }
          }
        } else if (face_count === 0) {
          if (baselineRef.current !== null && !cooldownActiveRef.current) {
            const idx = challengeIndexRef.current;
            const barajados = desafiosBarajadosRef.current;
            if (idx < barajados.length) {
              challengeCountsRef.current.set(barajados[idx], 0);
            }
          }
        }
      } catch {
        // Errores de detección son transitorios — continuar el loop
      }
    }

    if (faseRef.current === 'capturando') {
      rafHandleRef.current = requestAnimationFrame(() => { void detectFrame(); });
    } else {
      rafHandleRef.current = null;
    }
  };

  rafHandleRef.current = requestAnimationFrame(() => { void detectFrame(); });
}
