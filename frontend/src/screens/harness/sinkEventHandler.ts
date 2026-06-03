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
import { PESO_SCORE } from '../../proctoring/riskWeights';
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
  } = deps;

  return (rawEvent, sinkStatus, sinkError) => {
    const wasAtLimit = anomaliasLengthRef.current >= 50;

    // Empujar al store (igual que el flujo del alumno)
    const ev: EventoSesion = {
      id: rawEvent.id,
      tipo: rawEvent.tipo as TipoEvento,
      severidad: rawEvent.severidad as Severidad,
      ts_backend: new Date().toISOString(),
      descripcion: rawEvent.payload ? JSON.stringify(rawEvent.payload).slice(0, 80) : '',
      tiene_evidencia: !!(rawEvent.payload?.['trigger_evidence']),
    };
    pushAnomalia(ev);

    // C-25: actualizar checklist de cobertura (primer evento de cada tipo)
    setCoverage((prev) => {
      if (prev[rawEvent.tipo]) return prev; // ya capturado
      return { ...prev, [rawEvent.tipo]: { capturedAt: Date.now(), severidad: rawEvent.severidad } };
    });

    // C-33: acumular score de riesgo diagnóstico (setter funcional — sin stale closure)
    setHarnessScore((prev) => Math.min(100, prev + (PESO_SCORE[rawEvent.severidad as Severidad] ?? 0)));

    // Registrar en log local
    const seqId = String(logSeqRef.current++);
    const entry: HarnessLogEntry = {
      id: seqId,
      event: {
        tipo: rawEvent.tipo,
        severidad: rawEvent.severidad as Severidad,
        ts_ms: Date.now(),
        payload: rawEvent.payload ?? {},
        trigger_evidence: !!(rawEvent.payload?.['trigger_evidence']),
      },
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
        severidad: rawEvent.severidad,
        ts_cliente: new Date().toISOString(),
        payload: rawEvent.payload,
        screenshot_base64: screenshot,
        face_count_cliente: faceCountCliente,
      }).then((resp) => {
        // Incrementar contador de eventos enviados y actualizar badge en el log
        setEventosEnviados((c) => c + 1);
        setLogEntries((prev) =>
          prev.map((e) =>
            e.id === seqId
              ? {
                  ...e,
                  networkBadge: resp !== null ? 'ok' : 'net-error',
                  verdictServer: resp?.veredicto_reinferencia ?? null,
                  faceCountServer: resp?.face_count_servidor ?? null,
                }
              : e,
          ),
        );
      });
    })();
  };
}
