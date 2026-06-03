/**
 * useContextDetectors — señales de entorno del navegador del harness (C-25).
 *
 * Posee el estado envSignals + los refs que el loop de frames consume, y monta
 * los detectores reales (foco/pestaña, pantalla completa, portapapeles) mientras
 * la detección corre, más el polling pasivo de monitor cuando hay permiso.
 *
 * Extraído VERBATIM desde useDetectionHarness — mismos efectos, mismas deps,
 * mismo flujo. Devuelve el estado y los refs para que el resto del hook y el
 * loop de frames los usen sin cambios.
 */

import { useEffect, useRef, useState } from 'react';
import {
  FocusDetector,
  FullscreenDetector,
  ClipboardDetector,
  detectExtraMonitor,
} from '../../proctoring/contextDetectors';
import type { EnvSignals, HarnessState, MonitorPermission } from './types';

export function useContextDetectors(harnessState: HarnessState, monitorPermission: MonitorPermission) {
  // ------ C-25: Señales de entorno (detectores reales) ------
  const [envSignals, setEnvSignals] = useState<EnvSignals>({
    focusLost: false,
    tabChanged: false,
    fullscreenExited: false,
    clipboardAction: null,
    extraMonitor: null,
  });
  // Refs para consumir en el loop de frames (evita stale closure)
  const envFocusLostRef = useRef(false);
  const envTabChangedRef = useRef(false);
  const envFullscreenExitedRef = useRef(false);
  const envClipboardRef = useRef<'copy' | 'paste' | null>(null);
  const envExtraMonitorRef = useRef<boolean | null>(null);

  // ------ C-25: Detectores de contexto reales (se montan al iniciar, se desmontan al detener) ------
  useEffect(() => {
    if (harnessState !== 'running') return;

    // Foco de ventana + cambio de pestaña
    const fd = new FocusDetector((sig) => {
      if (sig.focus_lost !== undefined) {
        envFocusLostRef.current = sig.focus_lost;
        setEnvSignals((prev) => ({ ...prev, focusLost: sig.focus_lost! }));
      }
      if (sig.tab_changed !== undefined) {
        envTabChangedRef.current = sig.tab_changed;
        setEnvSignals((prev) => ({ ...prev, tabChanged: sig.tab_changed! }));
      }
    });
    fd.start();

    // Salida de pantalla completa
    const fsd = new FullscreenDetector((sig) => {
      if (sig.fullscreen_exited !== undefined) {
        envFullscreenExitedRef.current = sig.fullscreen_exited;
        setEnvSignals((prev) => ({ ...prev, fullscreenExited: sig.fullscreen_exited! }));
      }
    });
    fsd.start();

    // Clipboard (copy/paste sin leer contenido)
    const cd = new ClipboardDetector((sig) => {
      if (sig.clipboard_action) {
        envClipboardRef.current = sig.clipboard_action;
        setEnvSignals((prev) => ({ ...prev, clipboardAction: sig.clipboard_action! }));
        // Reset del label después de 3 s para que no quede "pegado"
        setTimeout(() => {
          envClipboardRef.current = null;
          setEnvSignals((prev) => ({ ...prev, clipboardAction: null }));
        }, 3000);
      }
    });
    cd.start();

    // C-32: el polling de monitor ya NO se inicia automáticamente aquí.
    // Solo se inicia cuando el usuario concede el permiso mediante
    // el botón "Detectar pantallas" (monitorPermission === 'granted').
    // Ver useEffect de pollMonitor abajo.

    return () => {
      fd.stop();
      fsd.stop();
      cd.stop();
      // Resetear señales al detener
      setEnvSignals({ focusLost: false, tabChanged: false, fullscreenExited: false, clipboardAction: null, extraMonitor: null });
      envFocusLostRef.current = false;
      envTabChangedRef.current = false;
      envFullscreenExitedRef.current = false;
      envClipboardRef.current = null;
      envExtraMonitorRef.current = null;
    };
  }, [harnessState]);

  // C-32 Task 6.4: polling pasivo de monitor — se activa solo cuando el permiso fue concedido
  useEffect(() => {
    if (harnessState !== 'running' || monitorPermission !== 'granted') return;

    let pollActive = true;
    const pollMonitor = async () => {
      const provider = () => (window as unknown as { getScreenDetails: () => Promise<{ screens: unknown[] }> }).getScreenDetails();
      const sig = await detectExtraMonitor(provider);
      const val = sig?.extra_monitor ?? null;
      envExtraMonitorRef.current = val;
      setEnvSignals((prev) => ({ ...prev, extraMonitor: val }));
      if (pollActive) setTimeout(pollMonitor, 5000);
    };
    pollMonitor();

    return () => { pollActive = false; };
  }, [harnessState, monitorPermission]);

  return {
    envSignals,
    setEnvSignals,
    envFocusLostRef,
    envTabChangedRef,
    envFullscreenExitedRef,
    envClipboardRef,
    envExtraMonitorRef,
  };
}
