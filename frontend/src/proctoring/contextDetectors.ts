/**
 * Detectores de contexto del navegador (C-11, RN-EV-04, US-006).
 *
 * Producen SENALES (no eventos) que alimentan las reglas de transicion:
 *  - cambio de pestana activa / perdida de foco (Page Visibility + focus/blur)
 *  - monitores multiples (Window Management API / getScreenDetails) donde el
 *    navegador lo permita.
 *
 * Las dependencias del DOM son inyectables (``doc``, ``win``, ``screenDetailsProvider``)
 * para testear la logica sin un navegador real.
 */

/** Senal de contexto consumida por las reglas de transicion. */
export interface ContextSignal {
  focus_lost?: boolean;
  extra_monitor?: boolean;
}

export interface FocusDetectorDeps {
  doc?: Pick<Document, "addEventListener" | "removeEventListener" | "visibilityState">;
  win?: Pick<Window, "addEventListener" | "removeEventListener">;
}

/**
 * Detector de pestana/foco. Emite ``focus_lost: true`` cuando la pestana deja de ser
 * visible o la ventana pierde el foco; ``false`` al recuperarlo.
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
      const onVisibility = () => {
        this.onSignal({ focus_lost: doc.visibilityState === "hidden" });
      };
      doc.addEventListener("visibilitychange", onVisibility);
      this.listeners.push(() => doc.removeEventListener("visibilitychange", onVisibility));
    }
    if (win) {
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
