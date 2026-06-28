/**
 * Enforcement de pantalla completa durante la rendición (C-69, D4).
 *
 * CAPA NUEVA — no modifica el contrato de FullscreenDetector / FocusDetector (D4).
 * Los detectores existentes siguen produciendo sus señales hacia el pipeline de score
 * EXACTAMENTE igual que antes (retrocompat). Este módulo los CONSUME para enforcement.
 *
 * Comportamiento:
 *  - Al iniciar (gesto del alumno): invoca requestFullscreen.
 *  - Ante fullscreen_exited / blur (focus_lost) / visibilitychange=hidden (tab_changed):
 *    marca estado "bloqueado" y re-intenta requestFullscreen automáticamente.
 *  - Al volver a fullscreen y pestaña visible: desmarca "bloqueado".
 *  - Cada señal se reporta a onSenalParaScore para que el pipeline de score la reciba.
 *
 * L2.5: NUNCA expulsa, NUNCA anula la sesión automáticamente. Solo bloquea y re-fuerza.
 * DD-21/D6: degradación honesta — si el navegador no soporta Fullscreen API, no lanza;
 * el examen sigue funcionando. El límite se comunica en la UI.
 *
 * Deps DOM inyectables (patrón de contextDetectors.ts) para testear sin navegador real.
 */

import { FullscreenDetector, FocusDetector } from './contextDetectors';
import type { FullscreenDetectorDeps, FocusDetectorDeps } from './contextDetectors';

export interface FullscreenLockdownDeps {
  /** Deps inyectables para FullscreenDetector (doc fake). */
  fullscreenDeps?: FullscreenDetectorDeps;
  /** Deps inyectables para FocusDetector (doc/win fake). */
  focusDeps?: FocusDetectorDeps;
  /** Función que invoca requestFullscreen sobre el elemento (inyectable). */
  requestFullscreen?: (element: Element) => Promise<void>;
  /** Proveedor del fullscreenElement actual (inyectable para tests). */
  getFullscreenElement?: () => Element | null;
  /** Proveedor del visibilityState actual (inyectable para tests). */
  getVisibilityState?: () => DocumentVisibilityState;
  /** Elemento sobre el que pedir fullscreen (inyectable; default: documentElement). */
  targetElement?: Element | null;
}

export interface FullscreenLockdownState {
  /** true cuando el examen está bloqueado (alumno salió de fullscreen/foco/pestaña). */
  bloqueado: boolean;
}

export type OnEstadoChange = (state: FullscreenLockdownState) => void;
/** Callback que reporta la señal al pipeline de score (retrocompat D4). */
export type OnSenalParaScore = (tipo: string) => void;

/**
 * Módulo de enforcement de pantalla completa.
 *
 * Uso:
 *   const lockdown = new FullscreenLockdown(onEstadoChange, onSenalParaScore, deps);
 *   await lockdown.iniciar(); // en respuesta a un gesto del usuario
 *   // ...
 *   lockdown.detener(); // al desmontar el componente
 */
export class FullscreenLockdown {
  private _bloqueado = false;
  private readonly _fullscreenDetector: FullscreenDetector;
  private readonly _focusDetector: FocusDetector;
  private readonly _requestFullscreen: (el: Element) => Promise<void>;
  private readonly _getFullscreenElement: () => Element | null;
  private readonly _getVisibilityState: () => DocumentVisibilityState;
  private readonly _targetElement: Element | null;

  constructor(
    private readonly onEstadoChange: OnEstadoChange,
    private readonly onSenalParaScore: OnSenalParaScore,
    deps: FullscreenLockdownDeps = {},
  ) {
    // Deps inyectables (patrón contextDetectors.ts — para testear sin navegador real)
    this._requestFullscreen =
      deps.requestFullscreen ??
      ((el) => {
        if (typeof (el as HTMLElement).requestFullscreen === 'function') {
          return (el as HTMLElement).requestFullscreen();
        }
        return Promise.resolve();
      });

    this._getFullscreenElement =
      deps.getFullscreenElement ??
      (() => (typeof document !== 'undefined' ? document.fullscreenElement : null));

    this._getVisibilityState =
      deps.getVisibilityState ??
      (() =>
        typeof document !== 'undefined'
          ? document.visibilityState
          : ('visible' as DocumentVisibilityState));

    this._targetElement =
      deps.targetElement !== undefined
        ? deps.targetElement
        : typeof document !== 'undefined'
          ? document.documentElement
          : null;

    // Consumir FullscreenDetector SIN modificar su contrato (D4).
    // Usamos el detector solo como fuente de EVENTOS (fullscreenchange).
    // El estado real se evalúa con el getter inyectado _getFullscreenElement
    // (no con signal.fullscreen_exited), para que los deps del test sean la
    // fuente de verdad y el DOM real no interfiera.
    this._fullscreenDetector = new FullscreenDetector((signal) => {
      if (signal.fullscreen_exited !== undefined) {
        // Evaluar estado REAL con el getter inyectado (no el flag del signal)
        const enFullscreen = this._getFullscreenElement() !== null;
        if (!enFullscreen) {
          // Realmente salió de fullscreen: reportar al score + bloquear + re-entrar
          this.onSenalParaScore('fullscreen_exited');
          this._marcarBloqueado();
          this._intentarReingresar();
        } else {
          // fullscreenchange disparado y estamos EN fullscreen → evaluar desbloqueo
          this._evaluarDesbloqueo();
        }
      }
    }, deps.fullscreenDeps);

    // Consumir FocusDetector SIN modificar su contrato (D4).
    // focus_lost y tab_changed siguen reportándose al score.
    this._focusDetector = new FocusDetector((signal) => {
      if (signal.focus_lost !== undefined) {
        this.onSenalParaScore('focus_lost');
        if (signal.focus_lost) {
          this._marcarBloqueado();
        } else {
          this._evaluarDesbloqueo();
        }
      }
      if (signal.tab_changed !== undefined) {
        this.onSenalParaScore('tab_changed');
        if (signal.tab_changed) {
          this._marcarBloqueado();
        } else {
          this._evaluarDesbloqueo();
        }
      }
    }, deps.focusDeps);
  }

  /**
   * Inicia el lockdown: monta los detectores y solicita fullscreen.
   * Debe llamarse en respuesta a un gesto del usuario (click de "Iniciar examen").
   */
  async iniciar(): Promise<void> {
    this._fullscreenDetector.start();
    this._focusDetector.start();
    await this._intentarReingresar();
  }

  /** Detiene el lockdown y limpia todos los event listeners. */
  detener(): void {
    this._fullscreenDetector.stop();
    this._focusDetector.stop();
  }

  /**
   * Re-intenta ingresar a pantalla completa (para el botón "Volver a pantalla completa").
   * L2.5: sólo re-fuerza, no sanciona.
   */
  async volverAPantallaCompleta(): Promise<void> {
    await this._intentarReingresar();
  }

  private _marcarBloqueado(): void {
    if (!this._bloqueado) {
      this._bloqueado = true;
      this.onEstadoChange({ bloqueado: true });
    }
  }

  private _evaluarDesbloqueo(): void {
    const enFullscreen = this._getFullscreenElement() !== null;
    const visible = this._getVisibilityState() === 'visible';
    if (enFullscreen && visible && this._bloqueado) {
      this._bloqueado = false;
      this.onEstadoChange({ bloqueado: false });
    }
  }

  /**
   * Intenta invocar requestFullscreen. Si falla (gesto requerido o API ausente),
   * silencia el error — el overlay sigue visible para que el alumno haga click.
   * D6: degradación honesta sin crash.
   */
  private async _intentarReingresar(): Promise<void> {
    const el = this._targetElement;
    if (!el) return; // D6: sin element, no se puede hacer nada
    try {
      await this._requestFullscreen(el);
    } catch {
      // El navegador puede requerir gesto explícito o no soportar la API.
      // El overlay permanece visible con el botón explícito "Volver a pantalla completa".
    }
  }
}

/**
 * DD-21/D6: detecta si el navegador actual soporta la Fullscreen API.
 * Si retorna false, el examen funciona igual pero sin lockdown de FS.
 */
export function soportaFullscreen(): boolean {
  return (
    typeof document !== 'undefined' &&
    typeof (document.documentElement as HTMLElement).requestFullscreen === 'function'
  );
}

/**
 * DD-21/D6: texto de degradación honesta sobre el límite del lockdown web.
 * Se muestra al alumno para no prometer una garantía falsa de nivel SO (L5).
 */
export const MENSAJE_LIMITE_FULLSCREEN =
  'El sistema detecta y reacciona ante la salida de pantalla completa o el cambio de ' +
  'pestaña, pero no puede impedir el minimize del sistema operativo ni ver fuera del ' +
  'sandbox del navegador. Esto es un límite del navegador (web app, no lockdown nativo).';
