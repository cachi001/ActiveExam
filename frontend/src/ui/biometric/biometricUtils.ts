import { DESAFIOS } from '../../lib/api';
import type { SequentialChallenge } from '../../vision/liveness';

// ── Frame-count constants ────────────────────────────────────────────────────
export const HINT_STABLE_FRAMES = 8;
export const COOLDOWN_MS = 800;
export const NEUTRAL_GATE_FRAMES = 3;
export const MAX_FRAME_DT_MS = 100;
export const BASELINE_WARMUP_FRAMES = 10;
export const BASELINE_MIN_FRAMES = 12;
export const BASELINE_TIMEOUT_FRAMES = 60;
export const BASELINE_NOSE_VARIANCE_THRESHOLD = 0.002;

// ── Pure math ────────────────────────────────────────────────────────────────

export function variance(arr: number[]): number {
  if (arr.length < 2) return 0;
  const mean = arr.reduce((s, v) => s + v, 0) / arr.length;
  return arr.reduce((s, v) => s + (v - mean) ** 2, 0) / arr.length;
}

export function stddev(arr: number[]): number {
  return Math.sqrt(variance(arr));
}

export function medirLuminancia(
  video: HTMLVideoElement | null,
  canvasRef: { current: HTMLCanvasElement | null },
): number | null {
  if (!video || video.videoWidth === 0 || video.videoHeight === 0) return null;
  try {
    if (!canvasRef.current) {
      canvasRef.current = document.createElement('canvas');
      canvasRef.current.width = 32;
      canvasRef.current.height = 24;
    }
    const ctx = canvasRef.current.getContext('2d');
    if (!ctx) return null;
    ctx.drawImage(video, 0, 0, 32, 24);
    const data = ctx.getImageData(0, 0, 32, 24).data;
    const W = 32;
    const X0 = 8, X1 = 24, Y0 = 6, Y1 = 18;
    let sum = 0;
    let count = 0;
    for (let y = Y0; y < Y1; y++) {
      for (let x = X0; x < X1; x++) {
        const i = (y * W + x) * 4;
        sum += 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
        count++;
      }
    }
    return count > 0 ? sum / count : null;
  } catch {
    return null;
  }
}

export function snapshotToCanvas(video: HTMLVideoElement | null): HTMLCanvasElement | null {
  if (!video || video.videoWidth === 0 || video.videoHeight === 0) return null;
  try {
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas;
  } catch {
    return null;
  }
}

export function getLabelForChallenge(id: SequentialChallenge): string {
  const found = DESAFIOS.find((d) => d.id === id);
  if (found) return found.label;
  switch (id) {
    case 'parpadear':    return 'Parpadear';
    case 'girar_cabeza': return 'Girar la cabeza';
    case 'sonreír':      return 'Sonreír';
    default:             return id;
  }
}
