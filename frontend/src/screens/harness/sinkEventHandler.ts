/**
 * sinkEventHandler — cuerpo del callback que el LocalHarnessEventSink invoca por
 * cada evento discreto del pipeline (C-23).
 *
 * Extraído VERBATIM desde onSinkEvent.current en useDetectionHarness.
 * NO cambia la lógica: empuja al store, actualiza cobertura, acumula score,
 * registra en el log local y dispara el envío real-time (screenshot + POST)
 * fire-and-forget en modo sesión.
 *
 * Recibe refs y setters por una estructura de deps; como todas son estables
 * (refs de useRef y setters de useState/Zustand), el handler puede construirse
 * una vez y seguir leyendo el valor fresco de cada ref/closure — igual que el
 * patrón "ref estable" del original.
 */

import type { RefObject, MutableRefObject } from 'react';
import { api } from '../../lib/api';
import { captureVideoFrame } from '../../lib/videoFrameCapture';
import { pesoEvento, severidadEvento } from '../../proctoring/scoringWeights';
import { getEffectiveConfig } from '../../config/effectiveConfigCache';
import { detectorActivo } from '../../proctoring/detectorActivo';
import type { EventoSesion, TipoEvento, Severidad } from '../../lib/types';
import {
  LOG_MAX,
  type HarnessLogEntry,
  type SinkEventCallback,
  type CoverageEntry,
} from './types';

interface SinkEventDeps {
  anomaliasLengthRef: MutableRefObject<number>;
  sessionIdRef: MutableRefObject<string | null>;
  sessionPromiseRef: MutableRefObject<Promise<string | null> | null>;
  faceCountRef: MutableRefObject<number>;
  videoRef: RefObject<HTMLVideoElement>;
  logSeqRef: MutableRefObject<number>;
  pushAnomalia: (ev: EventoSesion) => void;
  setCoverage: (fn: (prev: Partial<Record<string, CoverageEntry>>) => Partial<Record<string, CoverageEntry>>) => void;
  setHarnessScore: (fn: (prev: number) => number) => void;
  setLogEntries: (fn: (prev: HarnessLogEntry[]) => HarnessLogEntry[]) => void;
  setLogTruncated: (v: boolean) => void;
  setEventosEnviados: (fn: (c: number) => number) => void;
  /** Overrides locales (modo what-if del harness). Si vacío, usa la config persistida. */
  scoringOverridesRef?: MutableRefObject<Record<string, number>>;
  /** Detectores activos para ESTA prueba (override local del harness, sembrado de la
   *  config). null = no cargado aún → fail-open (usa la config persistida). */
  detectoresActivosRef?: MutableRefObject<string[] | null>;
}

/** Construye el callback que el sink invoca por evento (lógica idéntica al original). */
export function buildSinkEventHandler(deps: SinkEventDeps): SinkEventCallback {
  const {
    anomaliasLengthRef,
    sessionIdRef,
    sessionPromiseRef,
    faceCountRef,
    videoRef,
    logSeqRef,
    pushAnomalia,
    setCoverage,
    setHarnessScore,
    setLogEntries,
    setLogTruncated,
    setEventosEnviados,
    scoringOverridesRef,
    detectoresActivosRef,
  } = deps;

  return (rawEvent, sinkStatus, sinkError) => {
    // Respeta los detectores activos (igual que el examen real): si el detector está
    // desactivado, NO se registra en el test. Prioriza el override local de la prueba;
    // si no hay (null), cae a la config persistida. Fail-open si tampoco hay config.
    const detectoresActivos = detectoresActivosRef?.current ?? getEffectiveConfig()?.detectores_activos;
    if (!detectorActivo(rawEvent.tipo, detectoresActivos)) {
      return;
    }

    const wasAtLimit = anomaliasLengthRef.current >= 50;

    // Severidad VIGENTE del tipo (config viva). Si no hay config cargada, cae a la
    // del catalogo del cliente (rawEvent.severidad). Así el log muestra lo que el
    // admin configuró en Scoring, no el default hardcodeado.
    const sev = severidadEvento(rawEvent.tipo, rawEvent.severidad as Severidad);

    // Empujar al store (igual que el flujo del alumno)
    const ev: EventoSesion = {
      id: rawEvent.id,
      tipo: rawEvent.tipo as TipoEvento,
      severidad: sev,
      ts_backend: new Date().toISOString(),
      descripcion: rawEvent.payload ? JSON.stringify(rawEvent.payload).slice(0, 80) : '',
      tiene_evidencia: !!(rawEvent.payload?.['trigger_evidence']),
    };
    pushAnomalia(ev);

    // C-25: actualizar checklist de cobertura (primer evento de cada tipo)
    setCoverage((prev) => {
      if (prev[rawEvent.tipo]) return prev; // ya capturado
      return { ...prev, [rawEvent.tipo]: { capturedAt: Date.now(), severidad: sev } };
    });

    // C-33: acumular score de riesgo diagnóstico (setter funcional — sin stale closure).
    // El peso se resuelve por: 1) overrides locales (modo what-if), 2) cache de la BD
    // (config viva), 3) fallback por severidad (si la API fallo).
    const overrides = scoringOverridesRef?.current;
    // Puntos que suma ESTE evento al score (mismo valor que se acumula). Se guarda
    // en el log para mostrar "+N pts" por evento.
    const puntos = pesoEvento(rawEvent.tipo, sev, overrides);
    setHarnessScore((prev) => Math.min(100, prev + puntos));

    // Registrar en log local
    const seqId = String(logSeqRef.current++);
    const entry: HarnessLogEntry = {
      id: seqId,
      event: {
        tipo: rawEvent.tipo,
        severidad: sev,
        ts_ms: Date.now(),
        payload: rawEvent.payload ?? {},
        trigger_evidence: !!(rawEvent.payload?.['trigger_evidence']),
      },
      puntos,
      sinkStatus,
      sinkError,
      inStore: true, // pushAnomalia fue llamado; el store hace slice(0,50)
      loggedAt: Date.now(),
      storeOverflow: wasAtLimit,
    };

    setLogEntries((prev) => {
      const next = [entry, ...prev];
      if (next.length > LOG_MAX) {
        setLogTruncated(true);
        return next.slice(0, LOG_MAX);
      }
      return next;
    });

    // Captura y envío real-time al backend — cada evento discreto emitido por el pipeline
    // dispara un screenshot + POST al instante. Fire-and-forget; degradación silenciosa si
    // no hay red o el backend está en mock (USE_REAL_BACKEND=0).
    // D4: no bloquea el loop. Si falla → badge "⚠ sin red" en el log.
    void (async () => {
      const sid = sessionIdRef.current ?? (sessionPromiseRef.current ? await sessionPromiseRef.current : null);
      if (!sid) return; // detección no iniciada / sesión no lista todavía
      const screenshot = videoRef.current ? captureVideoFrame(videoRef.current, 0.7) : null;
      const faceCountCliente = rawEvent.payload?.face_count != null
        ? Number(rawEvent.payload.face_count)
        : faceCountRef.current;

      void api.enviarEventoProctoring(sid, {
        tipo: rawEvent.tipo,
        severidad: sev,
        ts_cliente: new Date().toISOString(),
        payload: rawEvent.payload,
        screenshot_base64: screenshot,
        face_count_cliente: faceCountCliente,
      })
        // c-78: `enviarEventoProctoring` ya no devuelve null ante un fallo, lo
        // PROPAGA (antes se lo tragaba y el buffer del examen se vaciaba solo).
        // Acá eso se traduce a la misma badge de siempre, pero desde el rechazo.
        .then(
          (resp) => ({
            badge: 'ok' as const,
            verdict: resp.veredicto_reinferencia ?? null,
            faceCount: resp.face_count_servidor ?? null,
          }),
          () => ({ badge: 'net-error' as const, verdict: null, faceCount: null }),
        )
        .then(({ badge, verdict, faceCount }) => {
          // Incrementar contador de eventos enviados y actualizar badge en el log
          setEventosEnviados((c) => c + 1);
          setLogEntries((prev) =>
            prev.map((e) =>
              e.id === seqId
                ? {
                    ...e,
                    networkBadge: badge,
                    verdictServer: verdict,
                    faceCountServer: faceCount,
                  }
                : e,
            ),
          );
        });
    })();
  };
}
