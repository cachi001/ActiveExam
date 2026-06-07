/**
 * BiometricCapture — componente compartido de captura biométrica inmersiva (C-36).
 *
 * Encapsula la LÓGICA: acceso a cámara (getUserMedia), loop RAF de detección real
 * con el motor MediaPipe (loadEnrollmentEngine/disposeEnrollmentEngine), evaluación
 * secuencial de retos con baseline neutral (C-54: evaluateChallengeRelative,
 * framesMinForChallengeSeq, fisherYatesShuffle) y fallback manual cuando WebGL no
 * está disponible. La parte PRESENTACIONAL vive en ./biometric/ (CaptureOverlay +
 * sub-componentes).
 *
 * C-54 — Máquina de estados secuencial (D-1):
 * idle → baseline → challenge[N] → cooldown → done
 * Solo un reto activo por vez (challengeIndexRef). Los retos se barajan con
 * Fisher-Yates al montar. La evaluación usa delta relativo al baseline neutral.
 *
 * C-54 — Frame de referencia para embedding (D-3):
 * Se captura durante el baseline (cara frontal neutral), no el último frame del loop.
 * Se entrega al caller vía onComplete como `bestReferenceFrameRef.current`.
 *
 * Decisiones (C-36): D-1 overlay `fixed inset-0 z-50` cross-platform; D-2
 * requestFullscreen() best-effort (el overlay CSS cubre todo si rechaza); D-3 óvalo
 * dominante aspect-[3/4], paso actual abajo, dots + "N / total", cancelar top-right;
 * D-5 el embedding lo computa el caller (este solo pasa landmarks a onComplete);
 * D-6 fallback manual si loadEnrollmentEngine rechaza.
 *
 * DATOS SENSIBLES (Ley 25.326): los landmarks del último frame se entregan al caller
 * via onComplete; el caller computa el embedding (dato sensible) según RN-BIO-07/08.
 * El cliente es SENSOR NO CONFIABLE (RN-GLB-01): el backend re-infiere y firma.
 * L2.5 intacto: el sistema nunca sanciona automáticamente.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { CaptureOverlay } from './biometric/CaptureOverlay';
import { CaptureError } from './biometric/CaptureError';
import { loadEnrollmentEngine, disposeEnrollmentEngine } from '../vision/enrollmentEngineLoader';
import {
  evaluateChallengeRelative,
  framesMinForChallengeSeq,
  fisherYatesShuffle,
  computeBaselineFromAccumulator,
  isBaselineSmileValid,
} from '../vision/enrollmentChallengeDetector';
import type { BaselineFrame } from '../vision/enrollmentChallengeDetector';
import { SEQUENTIAL_CHALLENGES, derivePassiveSignals, passivePassed, detectVirtualCamera } from '../vision/liveness';
import { DESAFIOS } from '../lib/api';
import type { FaceLandmark, VisionEngine } from '../vision/VisionEngine';
import type { BaselineMetrics, SequentialChallenge, TurnDirection } from '../vision/liveness';

// Props del componente
export interface BiometricCaptureProps {
  /**
   * Retos a usar. Si se pasan, deben ser SequentialChallenge[].
   * Si no se pasan, se usa SEQUENTIAL_CHALLENGES barajado internamente.
   * @deprecated El catálogo secuencial es fijo desde C-54; no pasar challenges externos.
   */
  challenges?: SequentialChallenge[];
  /**
   * Callback al completar todos los retos. Recibe los landmarks del último frame,
   * un canvas con el frame del baseline (para que el caller compute el descriptor
   * 128-d con face-api), el resultado del liveness pasivo, los retos resueltos y
   * si se detectó cámara virtual. `frame` es null si la cámara no estaba lista.
   *
   * D3: firma ampliada para propagar liveness real (no hardcodeado) a los callers.
   * C-54 (D-3): `frame` es ahora el frame capturado durante el baseline (cara
   * frontal neutral), no el último frame arbitrario del loop.
   */
  onComplete: (
    landmarks: FaceLandmark[],
    frame: HTMLCanvasElement | null,
    passiveOk: boolean,
    retosResueltos: string[],
    virtualCameraDetected: boolean,
  ) => void;
  /** Callback al cancelar. */
  onCancel: () => void;
}

// Task 1.3: Fase interna del componente
// 'exito' = todos los retos resueltos → se muestra el estado de verificación
// completada ~1.6s ANTES de invocar onComplete (mejor feedback de cierre).
type Fase = 'capturando' | 'exito' | 'error';

// Helper — label de un reto desde DESAFIOS (usa id como fallback)
function getLabelForChallenge(id: SequentialChallenge): string {
  // El catálogo DESAFIOS tiene los labels de los retos secuenciales también
  const found = DESAFIOS.find((d) => d.id === id);
  if (found) return found.label;
  // Fallback con labels en español para los retos secuenciales
  switch (id) {
    case 'parpadear':    return 'Parpadear';
    case 'girar_cabeza': return 'Girar la cabeza';
    case 'sonreír':      return 'Sonreír';
    default:             return id;
  }
}

// Helper — varianza de un array numérico (sum of squared deviations / n).
// Retorna 0 si n < 2 (sin ventana suficiente para calcular varianza).
function variance(arr: number[]): number {
  if (arr.length < 2) return 0;
  const mean = arr.reduce((s, v) => s + v, 0) / arr.length;
  return arr.reduce((s, v) => s + (v - mean) ** 2, 0) / arr.length;
}

// Helper — desviación estándar
function stddev(arr: number[]): number {
  return Math.sqrt(variance(arr));
}

// Cooldown entre pasos: 350 ms (C-54, D-5)
const COOLDOWN_MS = 350;

// Número de frames de cara detectada antes de iniciar acumulación del baseline.
// Evita subexposición inicial de cámara (OQ-3).
const BASELINE_WARMUP_FRAMES = 10;

// Número mínimo de frames acumulados (frame 10+) para declarar baseline estable.
const BASELINE_MIN_FRAMES = 12;

// Frame máximo antes del fallback del baseline.
const BASELINE_TIMEOUT_FRAMES = 60;

// Umbral de varianza del centroide de nariz para declarar baseline estable.
const BASELINE_NOSE_VARIANCE_THRESHOLD = 0.002;

export function BiometricCapture({
  challenges,
  onComplete,
  onCancel,
}: BiometricCaptureProps) {
  // ── Refs de cámara y motor ───────────────────────────────────────────────
  const videoRef             = useRef<HTMLVideoElement>(null);
  const containerRef         = useRef<HTMLDivElement>(null);
  const streamRef            = useRef<MediaStream | null>(null);
  const rafHandleRef         = useRef<number | null>(null);
  const engineRef            = useRef<VisionEngine | null>(null);
  const lastLandmarksRef     = useRef<FaceLandmark[]>([]);
  const faseRef              = useRef<Fase>('capturando');
  const desafiosRef          = useRef<SequentialChallenge[]>([]);
  const resueltosRef         = useRef<string[]>([]);
  const procesarCompletadoRef = useRef<(() => void) | null>(null);

  // ── C-54: Refs de la máquina de estados secuencial (Tasks 3.1-3.8) ──────

  /** Índice del reto activo en la secuencia barajada (D-1). */
  const challengeIndexRef = useRef(0);

  /** Métricas del baseline neutral (null mientras no se declara). */
  const baselineRef = useRef<BaselineMetrics | null>(null);

  /**
   * Buffer de frames para el baseline.
   * Se acumula desde el frame BASELINE_WARMUP_FRAMES (frame 10+) de cara detectada.
   */
  const baselineAccumulatorRef = useRef<BaselineFrame[]>([]);

  /**
   * Contador de frames totales de detección (con cara).
   * Controla el warmup y el timeout del baseline.
   */
  const baselineFrameCountRef = useRef(0);

  /**
   * Buffer de posiciones de nariz (landmark 1) para calcular varianza de estabilidad.
   * Se sincroniza con baselineAccumulatorRef.
   */
  const nosePositionsRef = useRef<Array<{ x: number; y: number }>>([]);

  /** Frame del video capturado durante el baseline (cara frontal neutral). */
  const bestReferenceFrameRef = useRef<HTMLCanvasElement | null>(null);

  /** true cuando el cooldown de 350ms entre pasos está activo. */
  const cooldownActiveRef = useRef(false);

  /** Timer del cooldown (para limpiarlo en cleanup). */
  const cooldownTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  /** Secuencia de retos barajada con Fisher-Yates al montar. */
  const desafiosBarajadosRef = useRef<SequentialChallenge[]>([]);

  /** Dirección de giro elegida al azar al montar. */
  const turnDirectionRef = useRef<TurnDirection>('izquierda');

  /** Acumulador de frames consecutivos del reto activo. */
  const challengeCountsRef = useRef<Map<SequentialChallenge, number>>(new Map());

  // ── Liveness pasivo (D2) ────────────────────────────────────────────────
  const livenessWindowRef = useRef<Array<{
    blinkL: number;
    blinkR: number;
    noseX: number;
    noseY: number;
    minZ: number;
    maxZ: number;
    frameTime: number;
  }>>([]);
  const passiveOkRef = useRef(false);
  const passiveFalseFramesRef = useRef(0);

  // ── Detección de cámara virtual (D4) ────────────────────────────────────
  const prevFrameDataRef = useRef<ImageData | null>(null);
  const virtualCameraRef = useRef(false);

  // ── Estado de UI ─────────────────────────────────────────────────────────
  const [fase, setFase]               = useState<Fase>('capturando');
  const [desafios, setDesafios]       = useState<SequentialChallenge[]>([]);
  const [resueltos, setResueltos]     = useState<string[]>([]);
  const [motorListo, setMotorListo]   = useState(false);
  const [camaraLista, setCamaraLista] = useState(false);
  const [motorError, setMotorError]   = useState<string | null>(null);
  const [fallbackManual, setFallbackManual] = useState(false);
  const fallbackManualRef             = useRef(false);
  const [errorMsg, setErrorMsg]       = useState<string | null>(null);

  // C-54: Estado de UI para cooldown e instrucción direccional (Tasks 9.1-9.3)
  const [cooldownActivo, setCooldownActivo]         = useState(false);
  const [retoRecienResuelto, setRetoRecienResuelto] = useState<SequentialChallenge | null>(null);

  // turnDirection como estado estable inicializado al montar (Task 9.3)
  // Se inicializa con la dirección elegida al montar (se sincroniza con turnDirectionRef)
  const [turnDirection, setTurnDirection] = useState<TurnDirection>('izquierda');

  // Sync de refs para acceso desde el loop RAF (sin stale closure)
  useEffect(() => { faseRef.current = fase; }, [fase]);
  useEffect(() => { resueltosRef.current = resueltos; }, [resueltos]);
  useEffect(() => { desafiosRef.current = desafios; }, [desafios]);
  useEffect(() => { fallbackManualRef.current = fallbackManual; }, [fallbackManual]);

  // C-54: Inicialización al montar: barajar retos y elegir dirección (Tasks 3.7, 3.8, 9.3)
  useEffect(() => {
    // Barajar SEQUENTIAL_CHALLENGES con Fisher-Yates
    const catalogo = challenges && challenges.length > 0
      ? challenges
      : [...SEQUENTIAL_CHALLENGES];
    const barajados = fisherYatesShuffle([...catalogo]);
    desafiosBarajadosRef.current = barajados;
    setDesafios(barajados);
    desafiosRef.current = barajados;

    // Elegir dirección de giro aleatoria
    const dir: TurnDirection = Math.random() < 0.5 ? 'izquierda' : 'derecha';
    turnDirectionRef.current = dir;
    setTurnDirection(dir);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // activarFullscreen — best-effort, no lanza error
  const activarFullscreen = useCallback(() => {
    const container = containerRef.current;
    if (!container || !container.requestFullscreen) return;
    container.requestFullscreen().catch(() => {
      // rechazado (iOS Safari, entornos sin API) → el overlay CSS es suficiente
    });
  }, []);

  // C-54: procesarCompletado — usa bestReferenceFrameRef en lugar del último frame (D-3)
  // Tasks 7.1, 7.2, 7.3
  const procesarCompletado = useCallback(() => {
    // Cancelar RAF
    if (rafHandleRef.current !== null) {
      cancelAnimationFrame(rafHandleRef.current);
      rafHandleRef.current = null;
    }
    // Limpiar cooldown timer si activo
    if (cooldownTimerRef.current !== null) {
      clearTimeout(cooldownTimerRef.current);
      cooldownTimerRef.current = null;
    }
    // Dispose del motor
    void disposeEnrollmentEngine();
    // Salir de fullscreen si está activo
    if (document.fullscreenElement) {
      document.exitFullscreen?.().catch(() => {});
    }

    // C-54 (D-3): usar el frame del baseline como frame de referencia para el embedding.
    // Si no está disponible (baseline no capturado / modo fallback), capturar el frame actual.
    // Tasks 7.1-7.3
    let frame: HTMLCanvasElement | null = bestReferenceFrameRef.current;

    if (!frame) {
      // Fallback: capturar el frame actual del video
      const video = videoRef.current;
      if (video && video.videoWidth > 0 && video.videoHeight > 0) {
        try {
          const canvas = document.createElement('canvas');
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
          const ctx = canvas.getContext('2d');
          if (ctx) {
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            frame = canvas;
          }
        } catch {
          frame = null;
        }
      }
    }

    const isFallback = fallbackManualRef.current;
    onComplete(
      lastLandmarksRef.current,
      frame,
      isFallback ? false : passiveOkRef.current,
      resueltosRef.current,
      isFallback ? false : virtualCameraRef.current,
    );
  }, [onComplete]);

  // Registrar procesarCompletado en ref para acceso desde el loop RAF
  useEffect(() => {
    procesarCompletadoRef.current = procesarCompletado;
  }, [procesarCompletado]);

  // Al entrar en fase 'exito', mostrar "Verificación completada" ~1.6s y recién invocar onComplete
  useEffect(() => {
    if (fase !== 'exito') return;
    const t = setTimeout(() => {
      procesarCompletadoRef.current?.();
    }, 1600);
    return () => clearTimeout(t);
  }, [fase]);

  // handleCancel — cancelar RAF, dispose, salir fullscreen, detener stream
  const handleCancel = useCallback(() => {
    if (rafHandleRef.current !== null) {
      cancelAnimationFrame(rafHandleRef.current);
      rafHandleRef.current = null;
    }
    if (cooldownTimerRef.current !== null) {
      clearTimeout(cooldownTimerRef.current);
      cooldownTimerRef.current = null;
    }
    void disposeEnrollmentEngine();
    if (document.fullscreenElement) {
      document.exitFullscreen?.().catch(() => {});
    }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    onCancel();
  }, [onCancel]);

  // resolverRetoFromLoop — updater funcional para evitar stale closure
  const resolverRetoFromLoop = useCallback((id: SequentialChallenge) => {
    setResueltos((prev) => {
      if (prev.includes(id)) return prev;
      const next = [...prev, id];
      if (desafiosRef.current.length > 0 && next.length >= desafiosRef.current.length) {
        // Al completar todos los retos, entrar en fase 'exito'
        setFase('exito');
      }
      return next;
    });
  }, []);

  // C-54: activarCooldown — entre pasos (Tasks 6.1, 9.1, 9.2)
  const activarCooldown = useCallback((retoResueltoId: SequentialChallenge) => {
    cooldownActiveRef.current = true;
    setCooldownActivo(true);
    setRetoRecienResuelto(retoResueltoId);
    resolverRetoFromLoop(retoResueltoId);

    // avanzarAlSiguienteReto después del cooldown (Task 6.2)
    cooldownTimerRef.current = setTimeout(() => {
      challengeIndexRef.current += 1;
      cooldownActiveRef.current = false;
      setCooldownActivo(false);
      setRetoRecienResuelto(null);
      cooldownTimerRef.current = null;
      // Si challengeIndexRef ya apunta más allá del último reto,
      // la fase éxito ya fue activada por resolverRetoFromLoop arriba.
    }, COOLDOWN_MS);
  }, [resolverRetoFromLoop]);

  // C-54: startDetectionLoop — loop RAF con máquina de estados secuencial
  const startDetectionLoop = useCallback((engine: VisionEngine) => {
    engineRef.current = engine;

    const detectFrame = async () => {
      // Detener si la fase cambió
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

          const { landmarks, gaze } = meshResult;
          const face_count = faceResult.face_count;

          // Actualizar landmarks del último frame
          if (face_count > 0 && landmarks.length > 0) {
            lastLandmarksRef.current = landmarks;

            // ── Liveness pasivo — acumulador de ventana deslizante N=15 (D2) ──
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

            // ── Detección de cámara virtual (D4) ──
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

            // ── C-54: Fase baseline (Tasks 4.1-4.7) ──────────────────────────
            if (baselineRef.current === null) {
              // Incrementar contador de frames detectados (Task 4.2)
              baselineFrameCountRef.current += 1;
              const frameCount = baselineFrameCountRef.current;

              // Solo acumular desde el frame 10+ (evitar subexposición, OQ-3) (Task 4.2)
              if (frameCount >= BASELINE_WARMUP_FRAMES && landmarks.length >= 292) {
                const blinkOpenness = Math.abs(landmarks[159].y - landmarks[145].y);
                const smileWidth    = Math.abs(landmarks[291].x - landmarks[61].x);
                const gazeX         = gaze.x;

                baselineAccumulatorRef.current.push({ blinkOpenness, smileWidth, gazeX });
                nosePositionsRef.current.push({ x: noseX, y: noseY });

                // Task 4.4: verificar estabilidad con >= 12 frames acumulados
                const acc = baselineAccumulatorRef.current;
                if (acc.length >= BASELINE_MIN_FRAMES) {
                  const noseXArr = nosePositionsRef.current.map((p) => p.x);
                  const noseYArr = nosePositionsRef.current.map((p) => p.y);
                  const noseVariance = variance(noseXArr) + variance(noseYArr);

                  if (noseVariance < BASELINE_NOSE_VARIANCE_THRESHOLD) {
                    // Nariz estable — intentar declarar el baseline
                    const avgSmileWidth = acc.reduce((s, f) => s + f.smileWidth, 0) / acc.length;

                    if (!isBaselineSmileValid(avgSmileWidth)) {
                      // Task 4.5: alumno estaba sonriendo → resetear acumulador
                      // (la UI ya muestra "Relajá la expresión..." via retoActualLabel)
                      baselineAccumulatorRef.current = [];
                      nosePositionsRef.current = [];
                    } else {
                      // Task 4.6: baseline válido — calcular promedios y capturar frame
                      const baseline = computeBaselineFromAccumulator(acc);
                      if (baseline) {
                        baselineRef.current = baseline;
                        // Capturar frame del video para el embedding (D-3)
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

              // Task 4.7: timeout a los 60 frames → usar los últimos 10 frames como fallback
              if (frameCount >= BASELINE_TIMEOUT_FRAMES && baselineRef.current === null) {
                const acc = baselineAccumulatorRef.current;
                const ultimosDiez = acc.slice(-10);
                if (ultimosDiez.length >= 1) {
                  const n = ultimosDiez.length;
                  const blinkOpenness = ultimosDiez.reduce((s, f) => s + f.blinkOpenness, 0) / n;
                  const smileWidth    = ultimosDiez.reduce((s, f) => s + f.smileWidth, 0) / n;
                  const gazeX         = ultimosDiez.reduce((s, f) => s + f.gazeX, 0) / n;
                  // Fallback: usar sin check de smileWidth (robustez ante iluminación pobre)
                  baselineRef.current = { blinkOpenness: Math.max(blinkOpenness, 0.01), smileWidth, gazeX };
                } else {
                  // Sin frames — usar defaults razonables
                  baselineRef.current = { blinkOpenness: 0.05, smileWidth: 0.08, gazeX: 0 };
                }
                // Capturar frame fallback también
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

              // Si baseline aún no declarado, salir (no evaluar retos)
              if (baselineRef.current === null) {
                // Continuar loop
                if (faseRef.current === 'capturando') {
                  rafHandleRef.current = requestAnimationFrame(() => { void detectFrame(); });
                } else {
                  rafHandleRef.current = null;
                }
                return;
              }
            }

            // ── C-54: Evaluación secuencial de retos (Tasks 5.1-5.7) ─────────

            // Task 5.2: si cooldown activo, no evaluar
            if (cooldownActiveRef.current) {
              if (faseRef.current === 'capturando') {
                rafHandleRef.current = requestAnimationFrame(() => { void detectFrame(); });
              } else {
                rafHandleRef.current = null;
              }
              return;
            }

            // Task 5.3: obtener el reto activo
            const idx = challengeIndexRef.current;
            const barajados = desafiosBarajadosRef.current;
            if (idx >= barajados.length) {
              // Todos los retos completados — no evaluar
              if (faseRef.current === 'capturando') {
                rafHandleRef.current = requestAnimationFrame(() => { void detectFrame(); });
              } else {
                rafHandleRef.current = null;
              }
              return;
            }

            const retoActivo = barajados[idx];

            // Task 5.7: sin rostro → resetear acumulador del reto activo
            if (face_count === 0) {
              challengeCountsRef.current.set(retoActivo, 0);
            } else {
              // Task 5.4: evaluar el reto activo con delta relativo
              const cumple = evaluateChallengeRelative(
                retoActivo,
                landmarks,
                gaze,
                baselineRef.current,
                turnDirectionRef.current,
              );

              const prevCount = challengeCountsRef.current.get(retoActivo) ?? 0;

              if (cumple) {
                // Task 5.5: incrementar acumulador
                const newCount = prevCount + 1;
                challengeCountsRef.current.set(retoActivo, newCount);

                if (newCount >= framesMinForChallengeSeq(retoActivo)) {
                  // Task 5.5: reto completado → resetear acumulador y activar cooldown
                  challengeCountsRef.current.set(retoActivo, 0);
                  activarCooldown(retoActivo);
                }
              } else {
                // Task 5.6: no cumple → resetear acumulador
                challengeCountsRef.current.set(retoActivo, 0);
              }
            }
          } else if (face_count === 0) {
            // Sin rostro fuera del bloque de landmarks — resetear reto activo si hay baseline
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

      // Continuar el loop
      if (faseRef.current === 'capturando') {
        rafHandleRef.current = requestAnimationFrame(() => { void detectFrame(); });
      } else {
        rafHandleRef.current = null;
      }
    };

    rafHandleRef.current = requestAnimationFrame(() => { void detectFrame(); });
  }, [activarCooldown]); // eslint-disable-line react-hooks/exhaustive-deps

  // useEffect de inicialización de cámara y motor
  useEffect(() => {
    let cancelado = false;

    navigator.mediaDevices?.getUserMedia({
      video: { facingMode: 'user', width: 640, height: 480 },
    }).then((stream) => {
      if (cancelado) { stream.getTracks().forEach((t) => t.stop()); return; }
      streamRef.current = stream;
      if (videoRef.current) {
        const video = videoRef.current;
        video.srcObject = stream;
        const marcarLista = () => {
          if (!cancelado && video.videoWidth > 0 && video.videoHeight > 0) {
            setCamaraLista(true);
          }
        };
        video.addEventListener('loadeddata', marcarLista);
        video.addEventListener('playing', marcarLista);
        video.play().then(marcarLista).catch(() => {});
      }
    }).catch((err) => {
      if (!cancelado) {
        setErrorMsg(`Sin acceso a la cámara: ${err?.message ?? 'permiso denegado'}`);
        setFase('error');
      }
    });

    const onFullscreenChange = () => {};
    document.addEventListener('fullscreenchange', onFullscreenChange);

    loadEnrollmentEngine().then((engine) => {
      if (cancelado) {
        void disposeEnrollmentEngine();
        return;
      }
      engineRef.current = engine;
      setMotorListo(true);
      activarFullscreen();
      startDetectionLoop(engine);
    }).catch((err) => {
      if (!cancelado) {
        const msg = err instanceof Error ? err.message : String(err);
        setMotorError(msg);
        setFallbackManual(true);
      }
    });

    // Task 6.3: cleanup — limpiar cooldown timer (memory leak prevention)
    return () => {
      cancelado = true;
      if (rafHandleRef.current !== null) {
        cancelAnimationFrame(rafHandleRef.current);
        rafHandleRef.current = null;
      }
      if (cooldownTimerRef.current !== null) {
        clearTimeout(cooldownTimerRef.current);
        cooldownTimerRef.current = null;
      }
      void disposeEnrollmentEngine();
      streamRef.current?.getTracks().forEach((t) => t.stop());
      document.removeEventListener('fullscreenchange', onFullscreenChange);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // resolverRetoManual — fallback manual, sin RAF
  const resolverRetoManual = useCallback((id: string) => {
    setResueltos((prev) => {
      if (prev.includes(id)) return prev;
      const next = [...prev, id];
      if (desafiosRef.current.length > 0 && next.length >= desafiosRef.current.length) {
        setFase('exito');
      }
      return next;
    });
  }, []);

  // Derivados para la UI
  // C-54: el reto activo es el del challengeIndexRef (no el primero de la lista pendiente)
  const challengeIdx = desafios.findIndex((id) => !resueltos.includes(id));
  const retoActivoId = challengeIdx >= 0 ? desafios[challengeIdx] : null;

  // Label del reto activo — si cooldown activo, mostrar confirmación
  let retoActualLabel: string;
  if (cooldownActivo && retoRecienResuelto) {
    const pasoNum = resueltos.length; // ya fue agregado por resolverRetoFromLoop
    retoActualLabel = `Paso ${pasoNum} completado ✓`;
  } else if (!retoActivoId) {
    retoActualLabel = '¡Listo!';
  } else if (retoActivoId === 'girar_cabeza') {
    // Label direccional para girar_cabeza (Task 8.5)
    const dir = turnDirection === 'izquierda' ? 'IZQUIERDA' : 'DERECHA';
    retoActualLabel = `Girá la cabeza a la ${dir}`;
  } else {
    retoActualLabel = getLabelForChallenge(retoActivoId);
  }

  const totalResueltos = resueltos.length;
  const totalDesafios  = desafios.length;
  const todosResueltos = totalDesafios > 0 && totalResueltos >= totalDesafios;
  const enExito        = fase === 'exito' || todosResueltos;
  const listoParaMostrar = (motorListo && camaraLista) || fallbackManual;

  // Label del reto recién resuelto (para CaptureProgress)
  const retoRecienResueltoLabel = retoRecienResuelto
    ? getLabelForChallenge(retoRecienResuelto)
    : null;

  // Render — estado de error de cámara
  if (fase === 'error') {
    return createPortal(
      <div ref={containerRef} className="fixed inset-0 z-[60] bg-white flex flex-col items-center justify-center px-6">
        <CaptureError errorMsg={errorMsg} onCancel={handleCancel} />
      </div>,
      document.body,
    );
  }

  return createPortal(
    // C-58 D4: contextLabel y turnDirection eliminados (chrome redundante del overlay de liveness).
    <CaptureOverlay
      ref={containerRef}
      videoRef={videoRef}
      listoParaMostrar={listoParaMostrar}
      motorError={motorError}
      enExito={enExito}
      motorListo={motorListo}
      fallbackManual={fallbackManual}
      retoActualLabel={retoActualLabel}
      desafios={desafios}
      resueltos={resueltos}
      totalResueltos={totalResueltos}
      totalDesafios={totalDesafios}
      getLabel={getLabelForChallenge}
      onResolverManual={resolverRetoManual}
      onCancel={handleCancel}
      cooldownActivo={cooldownActivo}
      retoRecienResueltoLabel={retoRecienResueltoLabel}
    />,
    document.body,
  );
}
