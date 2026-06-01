/**
 * Detectores de contexto del navegador (C-11, C-25, RN-EV-04, US-006).
 *
 * Producen SENALES (no eventos) que alimentan las reglas de transicion:
 *  - perdida de foco de ventana (focus/blur)
 *  - cambio/apertura de pestana (Page Visibility API) — C-25: senal propia distinta de focus_lost
 *  - monitores multiples (Window Management API / getScreenDetails)
 *  - salida de pantalla completa (fullscreenchange) — C-25: nuevo
 *  - actividad de portapapeles (copy/paste) — C-25: nuevo; SIN leer contenido
 *
 * Las dependencias del DOM son inyectables (``doc``, ``win``, ``screenDetailsProvider``)
 * para testear la logica sin un navegador real.
 *
 * NINGUN detector emite veredicto ni sancion: solo producen senales (L2.5).
 */

/** Senal de contexto consumida por las reglas de transicion. */
export interface ContextSignal {
  focus_lost?: boolean;
  extra_monitor?: boolean;
  /** C-25: la pestana del examen dejo de ser visible (visibilitychange). */
  tab_changed?: boolean;
  /** C-25: el documento salio del modo pantalla completa. */
  fullscreen_exited?: boolean;
  /** C-25: accion de portapapeles ('copy' | 'paste'). SIN contenido. */
  clipboard_action?: 'copy' | 'paste';
}

export interface FocusDetectorDeps {
  doc?: Pick<Document, "addEventListener" | "removeEventListener" | "visibilityState">;
  win?: Pick<Window, "addEventListener" | "removeEventListener">;
}

/**
 * Detector de pestana/foco.
 *
 * - Emite ``focus_lost: true`` cuando la VENTANA pierde el foco del SO (blur/focus).
 * - Emite ``tab_changed: true`` cuando la PESTANA deja de estar visible (visibilitychange).
 *
 * Las dos senales son distintas (C-25): ``focus_lost`` = blur de ventana OS;
 * ``tab_changed`` = cambio/apertura de pestana del navegador.
 * Ninguna deriva sancion (L2.5).
 */
export class FocusDetector {
  private readonly listeners: Array<() => void> = [];

  constructor(
    private readonly onSignal: (s: ContextSignal) => void,
    private readonly deps: FocusDetectorDeps = {},
  ) {}

  start(): void {
    const doc = this.deps.doc ?? (typeof document !== "undefined" ? document : undefined);
    const win = this.deps.win ?? (typeof window !== "undefined" ? window : undefined);
    if (doc) {
      // C-25: visibilitychange -> tab_changed (distinto de focus_lost de ventana)
      const onVisibility = () => {
        this.onSignal({ tab_changed: doc.visibilityState === "hidden" });
      };
      doc.addEventListener("visibilitychange", onVisibility);
      this.listeners.push(() => doc.removeEventListener("visibilitychange", onVisibility));
    }
    if (win) {
      // blur/focus de ventana -> focus_lost (comportamiento original, retrocompat)
      const onBlur = () => this.onSignal({ focus_lost: true });
      const onFocus = () => this.onSignal({ focus_lost: false });
      win.addEventListener("blur", onBlur);
      win.addEventListener("focus", onFocus);
      this.listeners.push(() => win.removeEventListener("blur", onBlur));
      this.listeners.push(() => win.removeEventListener("focus", onFocus));
    }
  }

  stop(): void {
    for (const off of this.listeners.splice(0)) off();
  }
}

// ---------------------------------------------------------------------------
// C-25: FullscreenDetector — salida de pantalla completa
// ---------------------------------------------------------------------------

export interface FullscreenDetectorDeps {
  doc?: Pick<Document, "addEventListener" | "removeEventListener" | "fullscreenElement">;
}

/**
 * Detecta cuando el documento sale del modo pantalla completa (fullscreenchange).
 * Emite ``fullscreen_exited: true`` al salir, ``false`` al entrar de nuevo.
 * Dep inyectable para testear sin navegador real. Solo senales, sin sancion (L2.5).
 */
export class FullscreenDetector {
  private readonly listeners: Array<() => void> = [];

  constructor(
    private readonly onSignal: (s: ContextSignal) => void,
    private readonly deps: FullscreenDetectorDeps = {},
  ) {}

  start(): void {
    const doc = this.deps.doc ?? (typeof document !== "undefined" ? document : undefined);
    if (!doc) return;
    const onFullscreenChange = () => {
      // fullscreenElement es null cuando se sale de fullscreen
      this.onSignal({ fullscreen_exited: doc.fullscreenElement === null });
    };
    doc.addEventListener("fullscreenchange", onFullscreenChange);
    this.listeners.push(() => doc.removeEventListener("fullscreenchange", onFullscreenChange));
  }

  stop(): void {
    for (const off of this.listeners.splice(0)) off();
  }
}

// ---------------------------------------------------------------------------
// C-25: ClipboardDetector — copy/paste sin leer contenido
// ---------------------------------------------------------------------------

export interface ClipboardDetectorDeps {
  doc?: Pick<Document, "addEventListener" | "removeEventListener">;
}

/**
 * Detecta eventos copy/paste sobre el documento del examen.
 * NO lee ni almacena el contenido del portapapeles (privacidad; cliente no confiable).
 * Emite solo la accion ('copy' | 'paste'). Dep inyectable para tests sin navegador.
 * Solo senales, sin sancion (L2.5).
 */
export class ClipboardDetector {
  private readonly listeners: Array<() => void> = [];

  constructor(
    private readonly onSignal: (s: ContextSignal) => void,
    private readonly deps: ClipboardDetectorDeps = {},
  ) {}

  start(): void {
    const doc = this.deps.doc ?? (typeof document !== "undefined" ? document : undefined);
    if (!doc) return;
    const onCopy = () => this.onSignal({ clipboard_action: "copy" });
    const onPaste = () => this.onSignal({ clipboard_action: "paste" });
    doc.addEventListener("copy", onCopy);
    doc.addEventListener("paste", onPaste);
    this.listeners.push(() => doc.removeEventListener("copy", onCopy));
    this.listeners.push(() => doc.removeEventListener("paste", onPaste));
  }

  stop(): void {
    for (const off of this.listeners.splice(0)) off();
  }
}

/** Proveedor de detalles de pantallas (abstrae getScreenDetails, opcional). */
export type ScreenDetailsProvider = () => Promise<{ screens: unknown[] }>;

/**
 * Detecta monitores adicionales cuando la API de pantallas esta disponible. Devuelve
 * la senal ``extra_monitor: true`` si hay mas de una pantalla. Si la API no esta
 * disponible (provider undefined), devuelve ``null`` (no se puede determinar) sin
 * abortar: el navegador puede no permitirlo.
 */
export async function detectExtraMonitor(
  provider?: ScreenDetailsProvider,
): Promise<ContextSignal | null> {
  if (!provider) return null;
  try {
    const details = await provider();
    return { extra_monitor: details.screens.length > 1 };
  } catch {
    // Permiso denegado o API ausente: no se puede determinar, sin abortar.
    return null;
  }
}
