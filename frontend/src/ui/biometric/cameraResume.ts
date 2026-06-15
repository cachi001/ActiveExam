/**
 * Lógica pura para "descongelar" la cámara al volver de una pestaña oculta /
 * app en background (C-67 fix).
 *
 * Problema: cuando el navegador manda la pestaña al fondo, pausa el <video> y,
 * en mobile, suele MATAR el track de la cámara. Al volver, nadie le dice
 * "reanudá" → queda el último frame congelado en pantalla.
 *
 * Este módulo NO toca el DOM: decide qué acciones tomar a partir del estado.
 * El componente las traduce a llamadas reales (play / re-adquirir / reiniciar
 * loop). Mantenerlo puro lo hace testeable sin navegador (vitest, entorno node).
 */

/** Acción a ejecutar para recuperar la cámara tras volver a primer plano. */
export type CameraResumeAction = 'reacquire' | 'play' | 'restart-loop';

export interface CameraResumeState {
  /** ¿La página está visible? (document.visibilityState === 'visible'). */
  visible: boolean;
  /** ¿El track de video murió? (sin track o readyState === 'ended'). */
  trackEnded: boolean;
  /** ¿El elemento <video> quedó pausado (frame congelado)? */
  videoPaused: boolean;
  /** ¿El loop RAF de detección sigue vivo? (rafHandle !== null). */
  loopActive: boolean;
  /** ¿Estamos en fase de captura? (el loop DEBERÍA estar corriendo). */
  capturing: boolean;
}

/**
 * Decide las acciones para recuperar la cámara cuando la página vuelve a ser
 * visible. Orden de las acciones = orden de ejecución.
 */
export function decideCameraResumeActions(
  s: CameraResumeState,
): CameraResumeAction[] {
  // En background no hacemos nada: esperamos a que la página vuelva.
  if (!s.visible) return [];

  // Track muerto (típico mobile): re-adquirir es una acción TOTAL — vuelve a
  // pedir getUserMedia, reengancha el <video> y reinicia el loop. No se combina.
  if (s.trackEnded) return ['reacquire'];

  const actions: CameraResumeAction[] = [];

  // Track vivo pero el <video> quedó pausado → reanudar (descongela el frame).
  if (s.videoPaused) actions.push('play');

  // Si estamos capturando y el loop se murió, reiniciarlo.
  if (s.capturing && !s.loopActive) actions.push('restart-loop');

  return actions;
}
