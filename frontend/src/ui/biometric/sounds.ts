/**
 * sounds — feedback auditivo de la captura biométrica.
 *
 * Generamos los tonos en runtime con WebAudio (sin assets externos, sin red,
 * sin licencias). El AudioContext se crea perezosamente en el primer uso para
 * cumplir las políticas de auto-play de los navegadores (requiere gesto del
 * usuario para arrancar, lo cual queda satisfecho con el click "Iniciar
 * captura de referencia" antes de montar BiometricCapture).
 *
 * Catálogo:
 *  - `tick`       — beep breve cuando se completa un paso (Sí, lo agarramos).
 *  - `success`    — arpegio ascendente al verificar (tres notas: do-mi-sol).
 *  - `warning`    — beep grave breve cuando aparece un hint (lejos, oscuro…).
 *
 * Reglas de uso:
 *  - Los sonidos son DISCRETOS (≤ 250 ms) y a volumen 0.18 para no asustar.
 *  - Cooldown interno: el mismo nombre no se vuelve a tocar antes de 400 ms,
 *    así no estallan en bucle si la condición que lo dispara es ruidosa.
 *  - Respeta `prefers-reduced-motion`: si el usuario lo activó, no suena nada.
 *  - El usuario puede silenciar todo con `setSoundEnabled(false)`.
 */

let ctx: AudioContext | null = null;
let enabled = true;
const lastPlayedAt = new Map<string, number>();
const SAME_SOUND_COOLDOWN_MS = 400;

/** Habilita/deshabilita TODO el feedback auditivo en runtime. */
export function setSoundEnabled(value: boolean): void {
  enabled = value;
}

/** True si el SO/navegador pide reducir el movimiento (proxy razonable para "menos estímulos"). */
function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * Devuelve el AudioContext perezoso (lo crea en el primer uso). Si el navegador
 * lo dejó en `suspended` (Chrome lo hace al perder gesto), intenta resumirlo.
 */
function getCtx(): AudioContext | null {
  if (typeof window === 'undefined') return null;
  if (!ctx) {
    type AcCtor = typeof AudioContext;
    const AC: AcCtor | undefined =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext?: AcCtor }).webkitAudioContext;
    if (!AC) return null;
    try {
      ctx = new AC();
    } catch {
      return null;
    }
  }
  if (ctx.state === 'suspended') {
    void ctx.resume().catch(() => {});
  }
  return ctx;
}

interface ToneSpec {
  /** Hz */
  freq: number;
  /** segundos */
  duration: number;
  /** segundos a partir del ahora */
  delay?: number;
  /** 0..1 — multiplica el volumen base 0.18 */
  gain?: number;
  /** triangle suena más cálido que sine y menos chillón que square */
  type?: OscillatorType;
}

/**
 * Toca una secuencia de tonos cortos. Cada uno usa un envelope ASR breve para
 * evitar clicks de inicio/fin. Si el contexto no está disponible (Safari sin
 * gesto, navegador sin WebAudio), no hace nada — el feedback visual sigue.
 */
function playSequence(name: string, tones: ToneSpec[]): void {
  if (!enabled) return;
  if (prefersReducedMotion()) return;

  const ahora = Date.now();
  const ult = lastPlayedAt.get(name) ?? 0;
  if (ahora - ult < SAME_SOUND_COOLDOWN_MS) return;
  lastPlayedAt.set(name, ahora);

  const c = getCtx();
  if (!c) return;

  const t0 = c.currentTime;
  for (const tone of tones) {
    const start = t0 + (tone.delay ?? 0);
    const dur = tone.duration;
    const peak = 0.18 * (tone.gain ?? 1);

    const osc = c.createOscillator();
    osc.type = tone.type ?? 'triangle';
    osc.frequency.value = tone.freq;

    const gain = c.createGain();
    // Envelope: 8 ms attack, decay lineal al silencio.
    gain.gain.setValueAtTime(0, start);
    gain.gain.linearRampToValueAtTime(peak, start + 0.008);
    gain.gain.linearRampToValueAtTime(0, start + dur);

    osc.connect(gain).connect(c.destination);
    osc.start(start);
    osc.stop(start + dur + 0.02);
  }
}

/** Beep corto al completar un paso (la4 → afirmativo pero no estridente). */
export function playStepCompleted(): void {
  playSequence('step', [{ freq: 880, duration: 0.12, type: 'triangle' }]);
}

/** Arpegio ascendente do-mi-sol al verificar la captura completa. */
export function playSuccess(): void {
  playSequence('success', [
    { freq: 523.25, duration: 0.13, delay: 0 },        // do5
    { freq: 659.25, duration: 0.13, delay: 0.10 },     // mi5
    { freq: 783.99, duration: 0.20, delay: 0.20, gain: 1.1 }, // sol5
  ]);
}

/** Beep grave breve cuando aparece un hint (lejos, oscuro, descentrado). */
export function playHint(): void {
  playSequence('hint', [{ freq: 330, duration: 0.10, type: 'sine' }]);
}
