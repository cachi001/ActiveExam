/**
 * useExamProctoring — proctoring REAL de fondo para el flujo de EXAMEN del alumno.
 *
 * Cablea las mismas primitivas que el harness admin pero en una versión LEAN
 * pensada para correr en silencio mientras el alumno rinde:
 *
 *  1. Abre una sesión `modo:'examen'` en el backend slim al iniciar.
 *  2. Carga el motor MediaPipe real (fallback honesto al stub si init() falla)
 *     y crea un VisionPipeline (motor → reglas → sink).
 *  3. Corre un loop de frames (setInterval) sobre el <video> del preview,
 *     monta los detectores de contexto del navegador y por CADA evento discreto
 *     captura un screenshot y lo streamea al backend (fire-and-forget).
 *  4. Expone { sessionId, score, eventCount, activo } + detener() para cerrar
 *     prolijo al finalizar el examen.
 *
 * REGLAS DE DOMINIO:
 * - L2.5: solo produce/streamea señales y evidencia; NUNCA sanciona.
 * - Cliente = sensor no confiable: el backend re-infiere y firma server-side.
 * - Degradación silenciosa: un error de red NUNCA rompe el examen.
 * - Dual-mode: con USE_REAL_BACKEND=0 funciona (sesión mock, envío null).
 *
 * GUARDIA DE OVERLAY (C-53/D4): este flujo de examen del alumno corre el
 * pipeline de visión EN SILENCIO y NUNCA debe montar `VisionOverlay` ni dibujar
 * puntos/box sobre la cara del alumno. El overlay de diagnóstico (canvas con
 * mesh/box/gaze) queda restringido al harness de staff. NO importar ni instanciar
 * `VisionOverlay` aquí: pintar el rostro del examinado es intrusivo y viola la spec
 * `vision-overlay-canvas` ("El examen del alumno no dibuja overlay sobre la cara").
 *
 * DATO SENSIBLE (Ley 25.326): el screenshot base64 es imagen del alumno; se
 * transmite solo al backend, nunca se loguea ni se persiste localmente.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type { RefObject } from 'react';
import { api } from '../lib/api';
import { useApp } from '../lib/store';
import { useAuth } from '../lib/authStore';
import { captureVideoFrame } from '../lib/videoFrameCapture';
import { MediaPipeVisionEngine } from '../vision/MediaPipeVisionEngine';
import type { VisionEngine } from '../vision/VisionEngine';
import { loadRealEngine, disposeRealEngine } from '../vision/harnessEngineLoader';
import { VisionPipeline, type EventSink } from './visionPipeline';
import { StateTransitionRules, DEFAULT_CONFIG } from './stateTransitionRules';
import { loadScoringWeights, pesoEvento, severidadEvento } from './scoringWeights';
import { loadEffectiveConfig, getEffectiveConfig } from '../config/effectiveConfigCache';
import { detectorActivo } from './detectorActivo';
import {
  FocusDetector,
  FullscreenDetector,
  ClipboardDetector,
  detectExtraMonitor,
  type ScreenDetailsProvider,
} from './contextDetectors';
import { descripcionEvento } from '../lib/api';
import { nombreCompleto } from '../lib/types';
import type { EventoSesion, Severidad, TipoEvento } from '../lib/types';
import { CircularEventBuffer } from '../transport/eventBuffer';
import { IndexedDbEventBufferStore } from '../transport/indexedDbBufferStore';
import { drainAndReplay } from '../transport/replayCoordinator';
import type { ReplaySender } from '../transport/replayCoordinator';
import { hashClip } from '../features/biometria/clipCustody';

// DEUDA TÉCNICA: los siguientes módulos están implementados y testeados pero no se
// cablea porque el backend slim no los soporta aún:
//
// - `../transport/eventSignature.ts` (firma HMAC de eventos): el backend slim NO valida
//   la firma del payload del evento. Firmar sin validación es teatro de seguridad.
//   Cablear cuando el backend implemente la validación.
//
// - `../features/custodia/evidenceCapture.ts` (cadena de custodia completa): requiere
//   el endpoint `/evidence/presign` (inexistente en el slim), storage externo
//   (MinIO/S3 con Object Lock) y `sessionKey` rotativa post-verificación biométrica.
//   Cablear cuando se implemente el backend completo de evidencia (C-12/C-24).

/** Máximo de eventos recientes que el panel del examen muestra. */
const MAX_EVENTOS = 30;

/**
 * Tipos de evento que adjuntan imagen de evidencia (el frame de la cámara ES la
 * prueba). El resto (eventos de sistema/comportamiento) NO captura screenshot:
 * el registro del evento ya es la evidencia (privacidad L2.5, regla dura #7).
 */
const EVENTOS_CON_EVIDENCIA_VISUAL = new Set<string>([
  'rostro_ausente',
  'multiples_rostros',
  'mirada_desviada_sostenida',
  'monitor_adicional',
  'reanudacion_tardia',
]);

/**
 * Guarda de idempotencia para la CREACIÓN de sesión, a nivel de MÓDULO (sobrevive
 * a los re-montajes del effect en React.StrictMode dev, que monta→desmonta→monta).
 *
 * Mapea examen.id → promesa de creación EN VUELO o YA RESUELTA. El effect, en vez de
 * llamar a `api.crearSesionProctoring` directamente, consulta este mapa: si ya hay una
 * promesa para ese examen, la reutiliza (no dispara un segundo POST). Sin esto, el
 * doble montaje de StrictMode crea DOS sesiones (el `cancelled` solo descarta el
 * RESULTADO del segundo, pero el POST ya salió).
 *
 * No interfiere con el reuso de `existingSessionId` (Consent.tsx): ese camino ni
 * siquiera consulta el mapa. La entrada se limpia si la creación falla (vuelve null),
 * para permitir un reintento legítimo en un montaje posterior.
 */
const sesionEnCreacion = new Map<string, Promise<string | null>>();

/**
 * Devuelve la sesión para `examenId`, creándola solo si no hay una en vuelo/creada.
 * Exportada para testeo de la guarda de idempotencia (no se usa fuera del hook).
 */
export function obtenerOCrearSesion(
  examenId: string,
  nombre: string | undefined,
  examenContenidoId?: string | null,
  onError?: (err: unknown) => void,
  onCreadaEn?: (creadaEn: string) => void,
): Promise<string | null> {
  const enVuelo = sesionEnCreacion.get(examenId);
  if (enVuelo) return enVuelo;
  const p = api
    // C-69: propagamos examen_contenido_id para que la sesión registre server-side
    // contra qué contenido (Moodle XML) rinde el alumno (vínculo REAL en proctoring_session).
    // Vuln reload: el backend es idempotente — si el alumno ya tiene una sesión ACTIVA
    // para este examen (p.ej. tras un F5), esto devuelve ESA MISMA sesión (misma
    // `creada_en`) en vez de crear una zombie. `onCreadaEn` propaga esa fecha para
    // anclar el timer del examen a la creación ORIGINAL.
    .crearSesionProctoring('examen', nombre, examenId, examenContenidoId)
    .then((s) => {
      onCreadaEn?.(s.creada_en);
      return s.id;
    })
    .catch((err) => {
      // La creación falló: liberar la entrada para permitir reintento futuro.
      sesionEnCreacion.delete(examenId);
      // Surface la causa al hook para que Examen.tsx bloquee la entrada al examen
      // en vez de dejar al alumno respondiendo en el vacío (sin sesión → nada se
      // guarda ni se califica). `setSessionError` de useState es estable entre el
      // doble montaje de StrictMode, así que el callback siempre apunta al mismo
      // setter del fiber vivo.
      onError?.(err);
      return null;
    });
  sesionEnCreacion.set(examenId, p);
  return p;
}

/** Motivo por el que NO se pudo iniciar la sesión de examen (bloquea la entrada). */
export interface SessionInitError {
  /** status HTTP del fallo (409 intentos, 403 ventana, otro/undefined = red/desconocido). */
  status?: number;
  /** Título corto para el overlay bloqueante. */
  titulo: string;
  /** Explicación en lenguaje claro para el alumno. */
  mensaje: string;
  /** true si reintentar tiene sentido (fallo de red), false si es una regla de negocio. */
  reintentable: boolean;
}

/** Mapea el error de creación de sesión a un motivo legible para el alumno. */
export function mapearSessionInitError(err: unknown): SessionInitError {
  const status = (err as { status?: number } | null)?.status;
  if (status === 409) {
    return {
      status,
      titulo: 'Sin intentos disponibles',
      mensaje:
        'Ya agotaste los intentos permitidos para este examen. Si creés que es un error, contactá a tu tutor.',
      reintentable: false,
    };
  }
  if (status === 403) {
    return {
      status,
      titulo: 'Examen fuera de horario',
      mensaje:
        'Este examen está fuera de la ventana de rendición (todavía no abrió o ya cerró). Revisá la fecha y el horario con tu tutor.',
      reintentable: false,
    };
  }
  return {
    status,
    titulo: 'No pudimos iniciar tu examen',
    mensaje:
      'Hubo un problema al iniciar la sesión de examen. Revisá tu conexión a internet y volvé a intentar.',
    reintentable: true,
  };
}

/** Test-only: limpia la guarda de idempotencia de módulo entre casos de test. */
export function __resetSesionEnCreacionParaTest(): void {
  sesionEnCreacion.clear();
}

/** ~5 fps: suficiente para detección en vivo sin saturar el cliente. */
const FRAME_INTERVAL_MS = 200;

/** Identificación mínima del examen que necesita el proctoring. */
interface ExamenInfo {
  id?: string;
  nombre?: string;
  /**
   * C-69: ID del examen de contenido (preguntas/opciones importadas de Moodle XML).
   * Se envía al crear la sesión para registrar el vínculo REAL server-side
   * (proctoring_session.examen_contenido_id). Examen.tsx lo consume para cargar
   * las preguntas vía GET /api/v1/exam-content/{examen_contenido_id}.
   */
  examen_contenido_id?: string | null;
}

/** Estado observable que el hook expone al componente Examen. */
export interface ExamProctoringState {
  /** id de la sesión backend (real o mock). null hasta que resuelve. */
  sessionId: string | null;
  /**
   * `creada_en` (ISO) de la sesión, server-autoritativa. Vuln reload: Examen.tsx
   * ancla el countdown a esta fecha (creación ORIGINAL de la sesión) en vez de a
   * la hora de montaje del componente — así un F5 a mitad de examen no le regala
   * tiempo extra al alumno. null hasta que la sesión resuelve.
   */
  sessionCreadaEn: string | null;
  /** score de riesgo acumulado (0..100). Prioriza, NO sanciona. */
  score: number;
  /** cantidad de eventos discretos detectados en la sesión. */
  eventCount: number;
  /** true mientras el loop de detección está corriendo. */
  activo: boolean;
  /** últimos eventos detectados (para el panel de señales del examen). */
  eventos: EventoSesion[];
  /** true si hay un monitor adicional conectado AHORA mismo (polling, no historial). */
  extraMonitorActive: boolean;
  /**
   * Motivo por el que NO se pudo iniciar la sesión de examen, o null si todo OK.
   * Cuando NO es null, Examen.tsx bloquea la entrada al examen (no se puede rendir
   * sin sesión: las respuestas no se guardarían ni se calcularía la nota).
   */
  sessionError: SessionInitError | null;
}

export interface UseExamProctoringResult extends ExamProctoringState {
  /** Corta el loop, dispone el motor y limpia detectores. Idempotente. */
  detener: () => void;
}

/**
 * Hook de proctoring real para el examen.
 *
 * @param videoRef - ref al <video> del preview (su stream alimenta la detección).
 * @param examen   - examen activo (etiqueta + examId para la sesión backend).
 */
export function useExamProctoring(
  videoRef: RefObject<HTMLVideoElement>,
  examen?: ExamenInfo | null,
): UseExamProctoringResult {
  const setProctoringSessionId = useApp((s) => s.setProctoringSessionId);
  const setProctoringSessionCreadaEn = useApp((s) => s.setProctoringSessionCreadaEn);
  const biometriaPendientePayload = useApp((s) => s.biometriaPendientePayload);
  const setBiometriaPendientePayload = useApp((s) => s.setBiometriaPendientePayload);
  const principal = useAuth((s) => s.principal);
  const addScore = useApp((s) => s.addScore);
  // C-64 D1: si Consent.tsx ya creó la sesión anticipada, reutilizarla — no crear otra.
  const existingSessionId = useApp((s) => s.proctoringSessionId);
  // Vuln reload: `creada_en` persistida junto al id (sessionStorage). Sobrevive a un
  // F5 y permite anclar el timer a la creación ORIGINAL sin volver a golpear el backend.
  const existingSessionCreadaEn = useApp((s) => s.proctoringSessionCreadaEn);

  // ------ Estado observable ------
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionCreadaEn, setSessionCreadaEn] = useState<string | null>(null);
  const [score, setScore] = useState(0);
  const [eventCount, setEventCount] = useState(0);
  const [activo, setActivo] = useState(false);
  const [eventos, setEventos] = useState<EventoSesion[]>([]);
  // Estado en vivo del monitor adicional. Refleja la ultima lectura del polling
  // (cada 5s). Examen.tsx lo usa para bloquear la rendicion mientras este `true`.
  const [extraMonitorActive, setExtraMonitorActive] = useState(false);
  const [sessionError, setSessionError] = useState<SessionInitError | null>(null);

  // ------ Refs del motor / pipeline / loop ------
  const engineRef = useRef<VisionEngine | null>(null);
  const pipelineRef = useRef<VisionPipeline | null>(null);
  const frameLoopRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const sessionPromiseRef = useRef<Promise<string | null> | null>(null);
  const faceCountRef = useRef(0);
  const stoppedRef = useRef(false);
  // Nombre del alumno para la etiqueta de la sesión (lo que ve el proctor en las
  // cards). En un ref para no meter `principal` en las deps del effect de arranque.
  const nombreAlumnoRef = useRef('');
  nombreAlumnoRef.current = nombreCompleto(principal);
  // examen.id de la sesión creada por ESTE hook (no por reuso de existingSessionId).
  // Lo usamos para liberar la guarda de idempotencia de módulo al finalizar, así una
  // rendición posterior del mismo examen puede crear una sesión nueva (no reusar la ya
  // finalizada). Permanece null si reutilizamos la sesión anticipada de Consent.tsx.
  const createdExamenIdRef = useRef<string | null>(null);

  // ------ Buffer IndexedDB (D1) ------
  // Instancia única que persiste toda la duración del hook. Null si IndexedDB
  // no está disponible (modo privado / iOS Safari → degradación silenciosa, R3).
  const bufferRef = useRef<CircularEventBuffer | null>(null);

  // ------ Señales de contexto del navegador (acumuladas, consumidas por tick) ------
  const focusLostRef = useRef(false);
  const tabChangedRef = useRef(false);
  const fullscreenExitedRef = useRef(false);
  const clipboardRef = useRef<'copy' | 'paste' | null>(null);
  const extraMonitorRef = useRef<boolean | null>(null);

  // ------ Callback de cada evento discreto (ref estable, lee estado fresco) ------
  const handleEvent = useRef<EventSink['sendEvent']>(async () => {});
  handleEvent.current = async (rawEvent) => {
    // Respetar detectores_activos de la config efectiva (FIX C-68):
    // si el detector no está activo, descartar el evento completamente — sin score,
    // sin log, sin envío al backend. Fail-open: si la config no cargó (undefined),
    // no suprimimos nada (el examen sigue funcionando).
    if (!detectorActivo(rawEvent.tipo, getEffectiveConfig()?.detectores_activos)) {
      return;
    }

    // Severidad VIGENTE del tipo (config viva del backend). Si la config no cargó,
    // cae a la del catalogo del cliente. Misma fuente que el peso → score y severidad
    // mostrada quedan consistentes con lo que el admin configuró.
    const sev = severidadEvento(rawEvent.tipo, rawEvent.severidad as Severidad);

    // Acumular score en el store global (scorePropio, L2.5 — prioriza, no sanciona).
    // El peso por tipo se resuelve dinamicamente desde la BD (cache poblada en mount);
    // si la API fallo, pesoEvento() vuelve al fallback por severidad.
    const peso = pesoEvento(rawEvent.tipo, sev);
    addScore(peso);
    setScore((prev) => Math.min(100, prev + peso));
    setEventCount((c) => c + 1);

    // Registrar en el panel de señales del examen.
    const ev: EventoSesion = {
      id: rawEvent.id,
      tipo: rawEvent.tipo as TipoEvento,
      severidad: sev,
      ts_backend: new Date().toISOString(),
      descripcion: descripcionEvento(rawEvent.tipo as TipoEvento),
      tiene_evidencia: !!rawEvent.payload?.['trigger_evidence'],
    };
    setEventos((prev) => [ev, ...prev].slice(0, MAX_EVENTOS));

    // Streaming al backend: screenshot + POST por cada evento. Fire-and-forget,
    // degradación silenciosa — un error de red NO rompe el examen.
    const sid =
      sessionIdRef.current ??
      (sessionPromiseRef.current ? await sessionPromiseRef.current : null);
    if (!sid) return;
    // Gate de evidencia (privacidad L2.5, regla dura #7): solo se captura una imagen
    // para eventos de VISIÓN, donde el frame de la cámara ES la prueba. Los eventos de
    // sistema/comportamiento (copiar_pegar, cambio_pestana, perdida_de_foco,
    // salida_pantalla_completa, monitor_adicional, corte_conectividad) NO adjuntan
    // screenshot: el registro del evento + timestamp ya es la evidencia. Menos capturas
    // = mejor privacidad (menos imágenes del alumno) y menos storage/ancho de banda.
    const screenshot =
      EVENTOS_CON_EVIDENCIA_VISUAL.has(rawEvent.tipo) && videoRef.current
        ? captureVideoFrame(videoRef.current, 0.7)
        : null;
    const faceCountCliente =
      rawEvent.payload?.face_count != null
        ? Number(rawEvent.payload.face_count)
        : faceCountRef.current;

    // Calcular hash SHA-256 del screenshot para la primera capa de cadena de
    // custodia del cliente (D5). Si falla (screenshot null / WebCrypto no disponible),
    // se omite el campo del payload — no bloquea el evento.
    let screenshotHash: string | undefined;
    if (screenshot) {
      try {
        const b64 = screenshot.replace(/^data:[^;]+;base64,/, '');
        const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
        screenshotHash = await hashClip(bytes.buffer);
      } catch {
        // error de WebCrypto: continuar sin el hash
      }
    }

    // Payload del evento — omitir screenshot_sha256_cliente si es undefined.
    const eventoPayload: {
      tipo: string;
      severidad: string;
      ts_cliente: string;
      payload?: Record<string, unknown>;
      screenshot_base64?: string | null;
      face_count_cliente?: number | null;
      screenshot_sha256_cliente?: string;
    } = {
      tipo: rawEvent.tipo,
      severidad: sev,
      ts_cliente: new Date().toISOString(),
      payload: rawEvent.payload,
      screenshot_base64: screenshot,
      face_count_cliente: faceCountCliente,
      ...(screenshotHash !== undefined && { screenshot_sha256_cliente: screenshotHash }),
    };

    // Patrón buffer-first con purga-en-éxito (D1, CRÍTICO):
    // 1. Persistir ANTES del POST (idempotente por id — si falla el POST, queda para el drain).
    // 2. Ejecutar el POST.
    // 3. Si el POST resuelve OK → confirm(id) para PURGAR del buffer.
    // 4. Si el POST rechaza (red caída) → NO confirmar (queda pendiente para drainAndReplay).
    //
    // Sin confirm on-success, el buffer retiene todos los eventos del examen y el drain
    // los reinyecta masivamente en la primera reconexión (el backend slim NO deduplica).
    await bufferRef.current?.append(rawEvent.id, eventoPayload).catch(() => {});

    try {
      await api.enviarEventoProctoring(sid, eventoPayload);
      // POST resolvió OK → purgar del buffer (evento a salvo server-side).
      await bufferRef.current?.confirm(rawEvent.id).catch(() => {});
    } catch (err) {
      // POST rechazado (red caída) → no confirmar; el evento queda en el buffer
      // para que drainAndReplay lo reenvíe al recuperar la conexión.
      // C-64 D5: loguear el error para diagnóstico en prod (antes era catch silencioso).
      console.error('[proctoring] POST evento falló:', err);
    }
  };

  // ------ detener(): corta loop, dispone motor, limpia ------
  //
  // `finalizarSesion` distingue el CIERRE EXPLÍCITO del examen (botón "Finalizar y
  // entregar" → true) de un desmontaje TRANSITORIO del componente (cleanup del effect
  // por remontaje / StrictMode / navegación de ida y vuelta → false).
  //
  // CRÍTICO (bug "no sale nada en Supervisión en vivo"): finalizar la sesión en CADA
  // cleanup la marcaba `finalizada_en` apenas el componente remontaba, y como el panel
  // del proctor solo muestra sesiones con `finalizada_en = NULL`, la sesión viva del
  // alumno desaparecía. La finalización es responsabilidad del cierre explícito: el
  // botón llama detener() (true) y además `Cierre.tsx` finaliza (idempotente). El
  // cleanup transitorio NO debe finalizar: la sesión sigue viva y el remontaje la reusa.
  const detener = useCallback((finalizarSesion = true) => {
    if (stoppedRef.current) return;
    stoppedRef.current = true;
    if (frameLoopRef.current) {
      clearInterval(frameLoopRef.current);
      frameLoopRef.current = null;
    }
    pipelineRef.current = null;
    engineRef.current = null;
    // Finalizar la sesión SOLO en el cierre explícito. Marca `finalizada_en` (sale de
    // "Supervisión en vivo", entra a Grabadas y, si supera el umbral, a la Cola de
    // revisión). Fire-and-forget + idempotente (el Cierre lo reintenta). NO limpiamos
    // proctoringSessionId del store acá — el Cierre lo necesita para leer el detalle.
    const sid = sessionIdRef.current;
    if (sid && finalizarSesion) {
      void api.finalizarSesionProctoring(sid).catch(() => {});
      // Liberar la guarda de idempotencia: la sesión quedó finalizada, así una
      // rendición posterior del mismo examen crea una sesión nueva (no reusa esta).
      const examenId = createdExamenIdRef.current;
      if (examenId) sesionEnCreacion.delete(examenId);
    }
    sessionIdRef.current = null;
    sessionPromiseRef.current = null;
    setActivo(false);
    // Liberar el motor WASM/GPU (singleton de módulo).
    void disposeRealEngine().catch(() => {});
  }, []);

  // ------ Arranque del proctoring (una vez por montaje) ------
  useEffect(() => {
    stoppedRef.current = false;
    let cancelled = false;

    // --- Cargar config efectiva desde el backend (pesos + umbrales vivos).
    // Primero cargamos la config efectiva completa (tarea 5.1/5.2); si falla,
    // pesoEvento() recurre al fallback por severidad (degradación silenciosa).
    // loadScoringWeights() sigue como fallback si loadEffectiveConfig falla.
    void loadEffectiveConfig().catch(() => void loadScoringWeights());

    // --- Inicializar buffer IndexedDB (R3: degradación silenciosa si no está disponible) ---
    try {
      bufferRef.current = new CircularEventBuffer(new IndexedDbEventBufferStore());
    } catch {
      bufferRef.current = null; // IndexedDB no disponible → operar sin buffer
    }

    // --- Adaptador ReplaySender: envuelve api.enviarEventoProctoring como ReplaySender ---
    // El buffer almacena el payload del evento (message) serializado; el sender
    // lo reenvía al backend usando el sessionId actual de sessionIdRef.
    const replaySender: ReplaySender = async (record) => {
      const sid = sessionIdRef.current;
      if (!sid) return { status: 'persisted', id: record.id };
      await api.enviarEventoProctoring(sid, record.message as Parameters<typeof api.enviarEventoProctoring>[1]);
      // El backend slim no distingue persisted/duplicate — siempre tratamos el 200 como persisted.
      return { status: 'persisted', id: record.id };
    };

    // --- handleDrain: drena el buffer al recuperar la conexión ---
    // Gracias al confirm on-success en handleEvent, solo contiene eventos que fallaron
    // mientras la red estaba caída — el drain reenvía únicamente esos (no el examen completo).
    const handleDrain = () => {
      if (bufferRef.current) {
        drainAndReplay(bufferRef.current, replaySender).catch(() => {});
      }
    };

    // --- handleOffline: solo para diagnóstico / future use ---
    const handleOffline = () => {
      // sin acción requerida: el patrón buffer-first en handleEvent ya persiste
      // cada evento antes del POST; al volver online handleDrain los reenvía.
    };

    window.addEventListener('online', handleDrain);
    window.addEventListener('offline', handleOffline);

    // --- Detectores de contexto del navegador ---
    const focus = new FocusDetector((sig) => {
      if (sig.focus_lost !== undefined) focusLostRef.current = sig.focus_lost;
      if (sig.tab_changed !== undefined) tabChangedRef.current = sig.tab_changed;
    });
    const fullscreen = new FullscreenDetector((sig) => {
      if (sig.fullscreen_exited) fullscreenExitedRef.current = true;
    });
    const clipboard = new ClipboardDetector((sig) => {
      if (sig.clipboard_action) clipboardRef.current = sig.clipboard_action;
    });
    focus.start();
    fullscreen.start();
    clipboard.start();

    // Monitor adicional — polling pasivo cada 5 s (degrada a null si no hay API).
    let monitorPollActive = true;
    const pollMonitor = async () => {
      const provider: ScreenDetailsProvider | undefined =
        typeof window !== 'undefined' && 'getScreenDetails' in window
          ? () =>
              (
                window as unknown as {
                  getScreenDetails: () => Promise<{ screens: unknown[] }>;
                }
              ).getScreenDetails()
          : undefined;
      const sig = await detectExtraMonitor(provider);
      const active = sig?.extra_monitor === true;
      extraMonitorRef.current = sig?.extra_monitor ?? null;
      // Solo set-state si cambia (evita re-renders innecesarios).
      setExtraMonitorActive((prev) => (prev !== active ? active : prev));
      if (monitorPollActive) setTimeout(pollMonitor, 5000);
    };
    void pollMonitor();

    // --- Carga del motor + sesión + loop (async) ---
    void (async () => {
      // C-64 D1: idempotencia — si Consent.tsx ya creó la sesión anticipada, reutilizarla.
      // Si ya existe en el store, setear directamente sin llamar al backend de nuevo.
      if (existingSessionId) {
        sessionIdRef.current = existingSessionId;
        setSessionId(existingSessionId);
        // Ancla el timer a la creada_en YA persistida (sobrevive al F5): no hace
        // falta golpear el backend de nuevo para tener esta fecha.
        setSessionCreadaEn(existingSessionCreadaEn);
        sessionPromiseRef.current = Promise.resolve(existingSessionId);
      } else if (examen?.id) {
        // Abrir sesión en el backend (fire-and-forget; sessionPromiseRef permite que
        // el primer evento espere si llega antes de que resuelva). Exigimos `examen.id`:
        // sin él, la sesión quedaba orfana ("examen sin examen vinculado") y aparecía
        // en supervisión en vivo sin contexto, indistinguible de una prueba.
        //
        // IDEMPOTENCIA (StrictMode): pasamos por obtenerOCrearSesion, que dedupe la
        // creación por examen.id a nivel de módulo. El doble montaje de StrictMode
        // reutiliza la MISMA promesa en lugar de disparar un segundo POST → una sola
        // sesión. El `cancelled` sigue protegiendo de aplicar el resultado a un montaje
        // ya desmontado, pero ya no hay POST duplicado que limpiar.
        createdExamenIdRef.current = examen.id;
        sessionPromiseRef.current = obtenerOCrearSesion(
          examen.id,
          nombreAlumnoRef.current || examen.nombre,
          examen.examen_contenido_id,
          // Si la creación falla (409 intentos agotados, 403 fuera de ventana, red),
          // surface el motivo: Examen.tsx bloquea la entrada en vez de dejar una
          // rendición fantasma que no guarda respuestas ni calcula nota.
          (err) => setSessionError(mapearSessionInitError(err)),
          // Persistir la creada_en junto al id: sobrevive a un F5 posterior y evita
          // que el reload tenga que volver a pedirla (ver rama existingSessionId).
          (creadaEn) => { setSessionCreadaEn(creadaEn); setProctoringSessionCreadaEn(creadaEn); },
        ).then(
          (id) => {
            if (cancelled || !id) return id ?? null;
            sessionIdRef.current = id;
            setSessionId(id);
            setProctoringSessionId(id);
            // Enviar payload biométrico que quedó pendiente de la pantalla /biometria
            // (la sesión no existía todavía cuando el alumno verificó su identidad).
            if (biometriaPendientePayload) {
              void api.enviarBiometriaProctoring(id, biometriaPendientePayload).catch(() => {});
              setBiometriaPendientePayload(null);
            }
            return id;
          },
        );
      } else {
        // Llegamos a /examen sin un examenActivo válido (deep-link, reload sin
        // contexto). NO creamos sesión orfana — el flujo del alumno falla seguro
        // y el panel de supervisión queda limpio.
        sessionPromiseRef.current = Promise.resolve(null);
      }

      // Cargar motor real; fallback honesto al stub si init() falla (no rompe).
      let engine: VisionEngine;
      try {
        engine = await loadRealEngine();
      } catch {
        engine = new MediaPipeVisionEngine();
        try {
          await engine.init();
        } catch {
          /* el stub no debería fallar; si lo hace, abortar el arranque */
          return;
        }
      }
      if (cancelled || stoppedRef.current) {
        void disposeRealEngine().catch(() => {});
        return;
      }
      engineRef.current = engine;

      // Sink LEAN: delega cada evento al handler con estado fresco.
      const sink: EventSink = {
        sendEvent: (args) => handleEvent.current(args),
      };
      // Usa la config efectiva si ya fue cargada; si no, DEFAULT_CONFIG como fallback.
      const efectiva = getEffectiveConfig();
      const thresholds = efectiva
        ? {
            face_absent_ms: efectiva.face_absent_ms,
            multiple_faces_frames: efectiva.multiple_faces_frames,
            gaze_deviation_threshold: efectiva.gaze_deviation_threshold,
            gaze_sustained_ms: efectiva.gaze_sustained_ms,
            gaze_fixation_tolerance: efectiva.gaze_fixation_tolerance,
          }
        : { ...DEFAULT_CONFIG };
      pipelineRef.current = new VisionPipeline({
        engine,
        sink,
        rules: new StateTransitionRules(thresholds),
      });
      setActivo(true);

      // Loop de frames: captura + inferencia + reglas (onSignals para no doblar
      // la inferencia) + consumo de señales de contexto.
      frameLoopRef.current = setInterval(() => {
        void runFrameTick({
          videoRef,
          engineRef,
          pipelineRef,
          faceCountRef,
          focusLostRef,
          tabChangedRef,
          fullscreenExitedRef,
          clipboardRef,
          extraMonitorRef,
        });
      }, FRAME_INTERVAL_MS);
    })();

    return () => {
      cancelled = true;
      monitorPollActive = false;
      focus.stop();
      fullscreen.stop();
      clipboard.stop();
      window.removeEventListener('online', handleDrain);
      window.removeEventListener('offline', handleOffline);
      // Drain final: enviar cualquier evento pendiente al finalizar el examen.
      if (bufferRef.current) {
        drainAndReplay(bufferRef.current, replaySender).catch(() => {});
      }
      // Cleanup TRANSITORIO: corta el loop y dispone el motor pero NO finaliza la
      // sesión (la deja viva). Un remontaje (StrictMode/navegación) la reusa y sigue
      // apareciendo en "Supervisión en vivo". La finalización real la hace el cierre
      // explícito: el botón "Finalizar y entregar" (Examen.tsx) + Cierre.tsx.
      detener(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [examen?.id]);

  return { sessionId, sessionCreadaEn, score, eventCount, activo, eventos, extraMonitorActive, sessionError, detener };
}

// ---------------------------------------------------------------------------
// runFrameTick — cuerpo del loop de frames (LEAN, sin estado de overlay).
// ---------------------------------------------------------------------------

interface FrameTickRefs {
  videoRef: RefObject<HTMLVideoElement>;
  engineRef: RefObject<VisionEngine | null>;
  pipelineRef: RefObject<VisionPipeline | null>;
  faceCountRef: { current: number };
  focusLostRef: { current: boolean };
  tabChangedRef: { current: boolean };
  fullscreenExitedRef: { current: boolean };
  clipboardRef: { current: 'copy' | 'paste' | null };
  extraMonitorRef: { current: boolean | null };
}

/**
 * Procesa un frame: capta ImageBitmap, corre detectFaces/detectFaceMesh y evalúa
 * las reglas con onSignals (la inferencia ya se hizo, evitamos doble pasada).
 * Un error de frame NO crashea el loop (degradación silenciosa).
 */
async function runFrameTick(refs: FrameTickRefs): Promise<void> {
  const video = refs.videoRef.current;
  const engine = refs.engineRef.current;
  const pipeline = refs.pipelineRef.current;
  if (!video || !engine || !pipeline || video.readyState < 2) return;

  try {
    const frame = await createImageBitmap(video);
    let faceCount = 0;
    let gaze: { x: number; y: number } | undefined;
    try {
      const fd = await engine.detectFaces(frame);
      faceCount = fd.face_count;
      if (fd.face_count >= 1) {
        try {
          const mesh = await engine.detectFaceMesh(frame);
          gaze = mesh.gaze;
        } catch {
          /* mesh opcional: la ausencia de gaze no interrumpe el frame */
        }
      }
    } catch {
      /* motor sin inferencia (stub): seguimos solo con señales de contexto */
      faceCount = 0;
    }
    frame.close();
    refs.faceCountRef.current = faceCount;

    // Consumir señales de contexto y resetear (excepto extra_monitor, por polling).
    const snapFocus = refs.focusLostRef.current;
    const snapTab = refs.tabChangedRef.current;
    const snapFullscreen = refs.fullscreenExitedRef.current;
    const snapClipboard = refs.clipboardRef.current;
    refs.focusLostRef.current = false;
    refs.tabChangedRef.current = false;
    refs.fullscreenExitedRef.current = false;
    refs.clipboardRef.current = null;

    await pipeline.onSignals({
      ts_ms: Date.now(),
      face_count: faceCount,
      gaze,
      focus_lost: snapFocus,
      extra_monitor: refs.extraMonitorRef.current === true,
      tab_changed: snapTab,
      fullscreen_exited: snapFullscreen,
      clipboard_action: snapClipboard ?? undefined,
    });
  } catch {
    /* error de frame: no romper el loop */
  }
}
