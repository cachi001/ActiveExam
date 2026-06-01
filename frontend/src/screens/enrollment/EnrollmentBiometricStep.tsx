/**
 * Paso de captura de referencia biométrica en el enrollment del perfil (C-22).
 *
 * C-34: biometría FUNCIONAL para test.
 * - Detección REAL de retos de liveness vía motor MediaPipe (loop RAF frame-a-frame).
 * - Embedding REAL con embeddingFromLandmarks(landmarks) — NO Math.random.
 * - Fullscreen en móvil: requestFullscreen() + fallback CSS fixed-inset para iOS Safari.
 * - Loader lazy singleton (enrollmentEngineLoader.ts, patrón C-32).
 * - Fallback manual cuando el motor no puede cargar (WebGL ausente).
 *
 * DATOS SENSIBLES (Ley 25.326):
 * - Imagen de referencia: cifrada at-rest server-side; finalidad acotada a verificación
 *   de identidad y revisión humana; eliminada al egreso; holds legales difieren.
 * - Embedding: cifrado at-rest server-side; finalidad acotada a verificación 1:1;
 *   marcado para eliminación al egreso; holds legales difieren (RN-BIO-07/08).
 *   El embedding tiene dimensionalidad 3 × N_landmarks (no 128): el backend de
 *   producción comprimirá vía PCA o capa densa a la dimensión canónica (OQ-1 de C-34).
 * El cliente es SENSOR NO CONFIABLE (RN-GLB-01): el backend re-infiere y firma (C-12).
 * L2.5 intacto: el sistema nunca sanciona automáticamente.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Icon, Button, Card } from '../../ui/components';
import { api, BIOMETRIC_VALIDITY_MONTHS } from '../../lib/api';
import { pickActiveChallenges } from '../../vision/liveness';
import { DESAFIOS } from '../../lib/api';
import { Term } from '../../ui/Term';
import { embeddingFromLandmarks } from '../../vision/MediaPipeVisionEngine';
import { loadEnrollmentEngine, disposeEnrollmentEngine } from '../../vision/enrollmentEngineLoader';
import {
  evaluateChallenge,
  framesMinForChallenge,
} from '../../vision/enrollmentChallengeDetector';
import type { ReferenciasBiometrica } from '../../lib/types';
import type { DesafioActivo } from '../../lib/types';
import type { ActiveChallenge } from '../../vision/liveness';
import type { FaceLandmark, VisionEngine } from '../../vision/VisionEngine';

// ---------------------------------------------------------------------------
// Tipos locales
// ---------------------------------------------------------------------------

type Fase =
  | 'instrucciones'   // Pantalla inicial con instrucciones
  | 'capturando'      // Cámara activa + retos de liveness
  | 'procesando'      // Calculando embedding
  | 'completado'      // Referencia guardada con éxito
  | 'error';          // Error de cámara u otro

interface Props {
  /** Referencia existente (para mostrar estado actual antes de renovar). */
  referenciaActual: ReferenciasBiometrica | null;
  /** Callback tras captura exitosa. */
  onCapturada: (referencia: ReferenciasBiometrica) => void;
  /** true cuando se está renovando una referencia existente (caducada o por deriva). */
  esRenovacion?: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * C-34 Task 7.1: detecta si el dispositivo es móvil o táctil.
 * Se considera móvil si el ancho es < 768px O si hay soporte de toque.
 */
function isMobileOrTouch(): boolean {
  return (
    window.innerWidth < 768 ||
    'ontouchstart' in window ||
    navigator.maxTouchPoints > 0
  );
}

// ---------------------------------------------------------------------------
// Componente
// ---------------------------------------------------------------------------

export function EnrollmentBiometricStep({ referenciaActual, onCapturada, esRenovacion = false }: Props) {
  // ── Refs de cámara/canvas (preexistentes) ──────────────────────────────
  const videoRef   = useRef<HTMLVideoElement>(null);
  const canvasRef  = useRef<HTMLCanvasElement>(null);
  const streamRef  = useRef<MediaStream | null>(null);

  // ── C-34 Task 3.4: ref del contenedor de captura (target de requestFullscreen)
  const containerRef = useRef<HTMLDivElement>(null);

  // ── C-34 Task 3.2: refs de detección (no disparan re-render) ──────────
  const rafHandleRef     = useRef<number | null>(null);
  const lastLandmarksRef = useRef<FaceLandmark[]>([]);
  /** Acumuladores de frames consecutivos por reto (D-3). */
  const challengeCountsRef = useRef<Map<ActiveChallenge, number>>(new Map());
  /** Instancia del motor cargada por loadEnrollmentEngine (ref para el loop). */
  const engineRef = useRef<VisionEngine | null>(null);

  // ── Estado de UI ────────────────────────────────────────────────────────
  const [fase, setFase]           = useState<Fase>('instrucciones');
  const [desafios, setDesafios]   = useState<DesafioActivo[]>([]);
  const [resueltos, setResueltos] = useState<string[]>([]);
  const [errorMsg, setErrorMsg]   = useState<string | null>(null);
  const [camaraLista, setCamaraLista] = useState(false);

  // ── C-34 Task 3.1: estado del motor ────────────────────────────────────
  const [motorListo, setMotorListo]   = useState(false);
  const [motorError, setMotorError]   = useState<string | null>(null);
  /** Modo fallback manual: el usuario resuelve retos con botones. */
  const [fallbackManual, setFallbackManual] = useState(false);

  // ── C-34 Task 3.3: estado de fullscreen ────────────────────────────────
  // fullscreenActive: refleja si document.fullscreenElement está activo (para
  // sincronización con el listener 'fullscreenchange' y la salida explícita).
  const [, setFullscreenActive]   = useState(false);
  const [fullscreenFallback, setFullscreenFallback] = useState(false);

  // ── Fase en ref para el loop RAF (evita stale closure) ─────────────────
  const faseRef = useRef<Fase>('instrucciones');
  useEffect(() => { faseRef.current = fase; }, [fase]);

  // ── Resueltos en ref para el loop RAF (evita stale closure) ────────────
  const resueltosRef = useRef<string[]>([]);
  useEffect(() => { resueltosRef.current = resueltos; }, [resueltos]);

  // ── Desafíos en ref para el loop RAF ────────────────────────────────────
  const desafiosRef = useRef<DesafioActivo[]>([]);
  useEffect(() => { desafiosRef.current = desafios; }, [desafios]);

  // ── procesarCaptura en ref (se llama desde el loop RAF) ─────────────────
  const procesarCapturaRef = useRef<(() => Promise<void>) | null>(null);

  // ---------------------------------------------------------------------------
  // Inicializar cámara al montar el componente
  // ---------------------------------------------------------------------------
  useEffect(() => {
    let cancelado = false;
    navigator.mediaDevices?.getUserMedia({ video: { facingMode: 'user', width: 640, height: 480 } })
      .then((stream) => {
        if (cancelado) { stream.getTracks().forEach((t) => t.stop()); return; }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.play().catch(() => {});
        }
        setCamaraLista(true);
      })
      .catch((err) => {
        if (!cancelado) {
          setErrorMsg(`No se pudo acceder a la cámara: ${err.message ?? 'permiso denegado'}`);
          setFase('error');
        }
      });

    // C-34 Task 7.3: listener de fullscreenchange para sincronizar estado
    const onFullscreenChange = () => {
      if (document.fullscreenElement === null) {
        setFullscreenActive(false);
        setFullscreenFallback(false);
      }
    };
    document.addEventListener('fullscreenchange', onFullscreenChange);

    return () => {
      cancelado = true;
      streamRef.current?.getTracks().forEach((t) => t.stop());

      // C-34 Task 4.3: cancelar RAF al desmontar
      if (rafHandleRef.current !== null) {
        cancelAnimationFrame(rafHandleRef.current);
        rafHandleRef.current = null;
      }

      // C-34 Task 4.2: dispose del motor al desmontar
      void disposeEnrollmentEngine();

      document.removeEventListener('fullscreenchange', onFullscreenChange);
    };
  }, []);

  // ---------------------------------------------------------------------------
  // C-34 Task 5.1–5.6: loop RAF de detección de retos
  // ---------------------------------------------------------------------------

  const startDetectionLoop = useCallback((engine: VisionEngine) => {
    engineRef.current = engine;

    const detectFrame = async () => {
      // Detener el loop si la fase cambió
      if (faseRef.current !== 'capturando') {
        rafHandleRef.current = null;
        return;
      }

      // C-34 Task 5.2: capturar bitmap del video → detectar
      if (videoRef.current && videoRef.current.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
        try {
          const bitmap = await createImageBitmap(videoRef.current);

          // Detección paralela de face mesh y faces
          const [meshResult, faceResult] = await Promise.all([
            engine.detectFaceMesh(bitmap),
            engine.detectFaces(bitmap),
          ]);

          bitmap.close();

          const { landmarks, gaze } = meshResult;
          const face_count = faceResult.face_count;
          const bbox = faceResult.faces[0] ?? null;

          // C-34 Task 5.3: actualizar landmarks del último frame
          if (face_count > 0 && landmarks.length > 0) {
            lastLandmarksRef.current = landmarks;
          }

          const currentResueltos = resueltosRef.current;
          const currentDesafios  = desafiosRef.current;

          if (face_count === 0) {
            // C-34 Task 5.6: sin rostro → resetear todos los acumuladores
            challengeCountsRef.current.clear();
          } else {
            // C-34 Task 5.4–5.5: evaluar retos pendientes
            for (const desafio of currentDesafios) {
              const id = desafio.id as ActiveChallenge;
              if (currentResueltos.includes(id)) continue;

              const cumple = evaluateChallenge(id, landmarks, gaze, bbox);
              const prevCount = challengeCountsRef.current.get(id) ?? 0;

              if (cumple) {
                const newCount = prevCount + 1;
                challengeCountsRef.current.set(id, newCount);

                // Si alcanza el mínimo de frames consecutivos → marcar resuelto
                if (newCount >= framesMinForChallenge(id)) {
                  challengeCountsRef.current.set(id, 0);
                  // Resolver reto (desde el loop RAF, actualizamos mediante callback)
                  resolverRetoFromLoop(id);
                }
              } else {
                // Rompe consecutividad → resetear acumulador
                challengeCountsRef.current.set(id, 0);
              }
            }
          }
        } catch {
          // Errores de detección son transitorios — continuar el loop
        }
      }

      // Continuar el loop
      if (faseRef.current === 'capturando') {
        rafHandleRef.current = requestAnimationFrame(() => { void detectFrame(); });
      } else {
        rafHandleRef.current = null;
      }
    };

    rafHandleRef.current = requestAnimationFrame(() => { void detectFrame(); });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ---------------------------------------------------------------------------
  // Resolver reto desde el loop RAF (updater funcional para acceder al estado
  // más reciente sin closure stale)
  // ---------------------------------------------------------------------------
  const resolverRetoFromLoop = useCallback((id: ActiveChallenge) => {
    setResueltos((prev) => {
      if (prev.includes(id)) return prev;
      const next = [...prev, id];
      // Si se completaron todos los retos, procesar captura
      if (desafiosRef.current.length > 0 && next.length >= desafiosRef.current.length) {
        // Defer para no mutar estado dentro de otro setter
        setTimeout(() => {
          if (procesarCapturaRef.current) {
            void procesarCapturaRef.current();
          }
        }, 0);
      }
      return next;
    });
  }, []);

  // ---------------------------------------------------------------------------
  // C-34 Task 7.2: fullscreen al iniciar captura
  // ---------------------------------------------------------------------------
  const activarFullscreen = useCallback(() => {
    if (!isMobileOrTouch()) return;

    const container = containerRef.current;
    if (!container) {
      setFullscreenFallback(true);
      return;
    }

    if (!container.requestFullscreen) {
      // API no disponible (iOS Safari sin PWA) → fallback CSS
      setFullscreenFallback(true);
      return;
    }

    container.requestFullscreen().then(() => {
      setFullscreenActive(true);
    }).catch(() => {
      // requestFullscreen rechazado (iOS Safari) → fallback CSS
      setFullscreenFallback(true);
    });
  }, []);

  // ---------------------------------------------------------------------------
  // C-34 Task 7.4: salir de fullscreen
  // ---------------------------------------------------------------------------
  const salirFullscreen = useCallback(() => {
    document.exitFullscreen?.().catch(() => {});
    setFullscreenActive(false);
    setFullscreenFallback(false);
  }, []);

  // ---------------------------------------------------------------------------
  // C-34 Task 4.1: iniciar captura — cargar motor, iniciar RAF, fullscreen
  // ---------------------------------------------------------------------------
  const iniciarCaptura = useCallback(async () => {
    // Elegir retos de liveness al azar (pickActiveChallenges de liveness.ts, RN-BIO-05)
    const ids = pickActiveChallenges(2);
    const nuevosDesafios = ids
      .map((id) => DESAFIOS.find((d) => d.id === id)!)
      .filter(Boolean);

    setDesafios(nuevosDesafios);
    desafiosRef.current = nuevosDesafios;
    setResueltos([]);
    resueltosRef.current = [];
    challengeCountsRef.current.clear();
    lastLandmarksRef.current = [];

    // C-34 Task 7.2: activar fullscreen en móvil antes de cambiar de fase
    activarFullscreen();

    if (fallbackManual) {
      // Modo fallback: ir directamente a capturando sin motor
      setFase('capturando');
      return;
    }

    // C-34 Task 4.1: mostrar spinner mientras carga el motor
    setMotorListo(false);
    setMotorError(null);

    // Cambiar fase inmediatamente para mostrar la cámara con spinner
    setFase('capturando');

    try {
      const engine = await loadEnrollmentEngine();
      setMotorListo(true);
      // C-34 Task 5.1: arrancar el loop RAF
      startDetectionLoop(engine);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setMotorError(msg);
      // Motor no disponible — el componente ofrecerá modo fallback manual
    }
  }, [fallbackManual, activarFullscreen, startDetectionLoop]);

  // ---------------------------------------------------------------------------
  // Resolver reto manualmente (modo fallback)
  // ---------------------------------------------------------------------------
  const resolverRetoManual = useCallback((id: string) => {
    setResueltos((prev) => {
      if (prev.includes(id)) return prev;
      const next = [...prev, id];
      if (desafiosRef.current.length > 0 && next.length >= desafiosRef.current.length) {
        setTimeout(() => {
          if (procesarCapturaRef.current) {
            void procesarCapturaRef.current();
          }
        }, 0);
      }
      return next;
    });
  }, []);

  // ---------------------------------------------------------------------------
  // C-34 Task 6.1–6.3: procesarCaptura con embedding real
  // ---------------------------------------------------------------------------
  const procesarCaptura = useCallback(async () => {
    // Evitar doble ejecución
    if (faseRef.current === 'procesando' || faseRef.current === 'completado') return;

    setFase('procesando');

    // Detener el loop RAF
    if (rafHandleRef.current !== null) {
      cancelAnimationFrame(rafHandleRef.current);
      rafHandleRef.current = null;
    }

    // Salir del fullscreen al completar (C-34 Task 7.4)
    salirFullscreen();

    // Capturar frame del video como imagen de referencia (demo)
    let imagenDataUrl: string | null = null;
    if (videoRef.current && canvasRef.current) {
      const canvas = canvasRef.current;
      const video  = videoRef.current;
      canvas.width  = video.videoWidth  || 320;
      canvas.height = video.videoHeight || 240;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        imagenDataUrl = canvas.toDataURL('image/jpeg', 0.85);
        // NOTA: Server-side esta imagen sería cifrada AES-256-GCM antes de persistir.
        // Finalidad: verificación de identidad y revisión humana. Eliminada al egreso.
      }
    }

    // C-34 Task 6.1: embedding real desde landmarks (reemplaza Math.random)
    // NOTA: Server-side el embedding real se re-infiere y cifra (RN-BIO-08, C-12).
    // NOTA: embeddingFromLandmarks produce 3 × N_landmarks floats (no 128).
    //       El backend de producción comprimirá vía PCA/capa densa a la dimensión
    //       canónica. El mock API acepta cualquier longitud (OQ-1, C-34 design D-7).
    const landmarks = lastLandmarksRef.current;

    // C-34 Task 6.2: si no se detectó cara, volver a capturando
    if (landmarks.length === 0) {
      setFase('capturando');
      setErrorMsg('No se detectó tu cara, intentá de nuevo');
      // Reiniciar el loop si el motor está listo
      if (engineRef.current && motorListo) {
        startDetectionLoop(engineRef.current);
      }
      return;
    }

    // C-34 Task 6.1: embedding determinista desde geometría facial
    // (NO Math.random — ver comentario de datos sensibles en el header del archivo)
    const embeddingReal = embeddingFromLandmarks(landmarks);

    // Guardar en api mock (persiste referencia con metadatos de vigencia)
    const referencia = await api.guardarReferenciaBiometrica({
      imagen: imagenDataUrl,
      embedding: embeddingReal,
    });

    setFase('completado');
    onCapturada(referencia);
  }, [salirFullscreen, motorListo, startDetectionLoop, onCapturada]);

  // Registrar procesarCaptura en ref para acceso desde el loop RAF y resolverReto
  useEffect(() => {
    procesarCapturaRef.current = procesarCaptura;
  }, [procesarCaptura]);

  // ---------------------------------------------------------------------------
  // Cancelar captura
  // ---------------------------------------------------------------------------
  const cancelarCaptura = useCallback(() => {
    if (rafHandleRef.current !== null) {
      cancelAnimationFrame(rafHandleRef.current);
      rafHandleRef.current = null;
    }
    salirFullscreen();
    setFase('instrucciones');
    setResueltos([]);
    setMotorError(null);
  }, [salirFullscreen]);

  // ---------------------------------------------------------------------------
  // Formatear fecha
  // ---------------------------------------------------------------------------
  const formatearFecha = (iso: string) =>
    new Date(iso).toLocaleDateString('es-AR', { day: '2-digit', month: 'long', year: 'numeric' });

  // ---------------------------------------------------------------------------
  // C-34 Task 7.5: clases del contenedor según estado de fullscreen
  // ---------------------------------------------------------------------------
  const containerClasses = fullscreenFallback
    ? 'fixed inset-0 z-50 bg-black flex flex-col items-center justify-center overflow-auto'
    : 'space-y-lg animate-in fade-in duration-400';

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div ref={containerRef} className={containerClasses}>

      {/* En modo fullscreen fallback, mostrar solo la sección de captura */}
      {!fullscreenFallback && (
        <>
          {/* Encabezado */}
          <div className="flex items-center gap-sm">
            <div className="w-10 h-10 rounded-xl bg-primary-fixed text-primary flex items-center justify-center shrink-0">
              <Icon name="face" className="text-[20px]" fill />
            </div>
            <div>
              <h3 className="font-headline text-title-md text-on-surface">
                {esRenovacion ? 'Renovar referencia biométrica' : 'Captura de referencia biométrica'}
              </h3>
              <p className="text-label-sm text-on-surface-variant">
                Vigencia {BIOMETRIC_VALIDITY_MONTHS} meses · <Term termKey="face_mesh" /> + <Term termKey="liveness">liveness híbrido</Term>
              </p>
            </div>
          </div>

          {/* Estado actual (si hay referencia previa caducada o por renovar) */}
          {referenciaActual && esRenovacion && (
            <div className="flex items-start gap-sm bg-warning-container border border-warning/30 rounded-xl p-md">
              <Icon name="refresh" className="text-warning text-[18px] shrink-0 mt-px" />
              <div className="text-label-sm text-on-surface">
                <p><strong>Referencia anterior:</strong> capturada el {formatearFecha(referenciaActual.fecha_captura)},
                  {' '}vencía el {formatearFecha(referenciaActual.fecha_expiracion)}.</p>
                <p className="text-on-surface-variant mt-base">
                  {referenciaActual.renovacion_anticipada_requerida
                    ? 'Se detectó deriva del embedding durante las verificaciones. La nueva captura reemplazará la referencia anterior.'
                    : 'La referencia venció. La nueva captura reemplazará la referencia anterior.'}
                </p>
              </div>
            </div>
          )}
        </>
      )}

      {/* Visor de cámara */}
      <Card className={`flex flex-col items-center gap-lg${fullscreenFallback ? ' w-full max-w-sm mx-auto bg-transparent border-0 shadow-none' : ''}`}>
        <div className="relative w-[260px] h-[320px] rounded-[36px] overflow-hidden bg-inverse-surface flex items-center justify-center">
          <video
            ref={videoRef}
            muted
            playsInline
            className="absolute inset-0 w-full h-full object-cover"
            aria-label="Vista de cámara para captura biométrica"
          />
          {/* Canvas oculto para capturar el frame de referencia */}
          <canvas ref={canvasRef} className="hidden" aria-hidden />

          {/* Guía de encuadre */}
          <div className={`relative w-[160px] h-[210px] rounded-[50%] border-2 border-dashed transition-colors duration-300 ${
            fase === 'completado'  ? 'border-success' :
            fase === 'capturando' ? 'border-primary scanning-ring' :
            fase === 'procesando' ? 'border-warning animate-pulse' :
            'border-primary-container'
          }`} />

          {/* Indicador de cámara en vivo */}
          {(fase === 'capturando' || fase === 'instrucciones') && camaraLista && (
            <div className="absolute bottom-3 left-3 inline-flex items-center gap-base bg-error text-on-error text-label-sm font-bold px-sm py-base rounded-full">
              <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
              CÁMARA
            </div>
          )}

          {/* Motor cargando — overlay sobre la cámara */}
          {fase === 'capturando' && !motorListo && !motorError && !fallbackManual && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-inverse-surface/80 rounded-[36px]">
              <Icon name="progress_activity" className="ae-spin text-primary text-[32px]" />
              <span className="text-label-sm text-on-surface mt-sm">Preparando verificación…</span>
            </div>
          )}
        </div>

        {/* ── Estado: instrucciones iniciales ── */}
        {fase === 'instrucciones' && (
          <div className="text-center space-y-md w-full">
            <p className="text-body-md text-on-surface-variant">
              Encuadrá tu rostro dentro del óvalo con buena iluminación y sin objetos que lo cubran.
              La captura dura 3–5 segundos y requiere dos gestos anti-suplantación.
            </p>
            {!camaraLista && !errorMsg && (
              <div className="flex items-center justify-center gap-sm text-on-surface-variant">
                <Icon name="progress_activity" className="ae-spin text-[18px]" />
                <span className="text-label-sm">Iniciando cámara…</span>
              </div>
            )}

            {/* C-34 Task 8.3: spinner de carga del motor */}
            {camaraLista && !motorListo && !motorError && !fallbackManual && (
              <div className="flex flex-col items-center gap-sm text-on-surface-variant">
                <Icon name="progress_activity" className="ae-spin text-[18px]" />
                <span className="text-label-sm">Preparando verificación…</span>
              </div>
            )}

            {/* Botón iniciar — visible cuando la cámara está lista */}
            {camaraLista && (
              <Button icon="photo_camera" onClick={() => { void iniciarCaptura(); }}>
                Iniciar captura de referencia
              </Button>
            )}
          </div>
        )}

        {/* ── Estado: retos de liveness activos ── */}
        {fase === 'capturando' && (
          <div className="w-full space-y-sm">

            {/* C-34 Task 8.1: error del motor + botón para activar fallback manual */}
            {motorError !== null && !fallbackManual && (
              <div className="bg-error-container border border-error/30 rounded-xl p-sm space-y-sm text-center">
                <p className="text-label-sm text-on-error-container">
                  <strong>Motor de visión no disponible.</strong><br />
                  {motorError.includes('WebGL') ? 'WebGL no disponible en este dispositivo.' : 'No se pudo cargar el detector.'}
                </p>
                <Button
                  icon="touch_app"
                  onClick={() => {
                    setFallbackManual(true);
                    setMotorError(null);
                  }}
                >
                  Continuar sin detección automática
                </Button>
              </div>
            )}

            {/* C-34 Task 8.2: banner de modo fallback manual */}
            {fallbackManual && (
              <div className="bg-warning-container border border-warning/30 rounded-xl px-sm py-xs text-center">
                <p className="text-label-sm text-on-surface">
                  Motor de visión no disponible — <strong>modo de prueba manual</strong>
                </p>
              </div>
            )}

            {/* Instrucción de retos */}
            <p className="text-label-md text-on-surface text-center font-semibold">
              {fallbackManual
                ? 'Tocá cada gesto para simular su detección:'
                : motorListo
                  ? 'Realizá los siguientes gestos (anti-suplantación de identidad):'
                  : 'Preparando el detector de gestos…'}
            </p>

            {/* C-34 Task 8.4: botones de retos */}
            {/* En modo automático: botones deshabilitados (solo visual del progreso).
                En modo fallback: botones clicables para resolución manual. */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-sm">
              {desafios.map((d) => {
                const hecho = resueltos.includes(d.id);
                return (
                  <button
                    key={d.id}
                    disabled={hecho || (!fallbackManual && motorListo)}
                    onClick={() => fallbackManual ? resolverRetoManual(d.id) : undefined}
                    className={`flex items-center gap-sm p-sm rounded-xl border transition-all ${
                      hecho
                        ? 'bg-success-container border-success/30 text-success'
                        : fallbackManual
                          ? 'bg-surface-container-low border-outline-variant hover:border-primary-container cursor-pointer'
                          : 'bg-surface-container-low border-outline-variant cursor-default'
                    }`}
                  >
                    <Icon name={hecho ? 'check_circle' : (motorListo && !fallbackManual ? 'face' : 'gesture')} fill={hecho} />
                    <span className="text-label-md font-semibold">{d.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Instrucción contextual */}
            {!fallbackManual && motorListo && (
              <p className="text-label-sm text-on-surface-variant text-center">
                El sistema detecta los gestos automáticamente — realizalos frente a la cámara.
              </p>
            )}

            {/* Botón cancelar */}
            <div className="flex justify-center pt-xs">
              <button
                onClick={cancelarCaptura}
                className="text-label-sm text-on-surface-variant underline underline-offset-2"
              >
                Cancelar
              </button>
            </div>
          </div>
        )}

        {/* ── Estado: procesando ── */}
        {fase === 'procesando' && (
          <div className="text-center space-y-sm text-on-surface-variant">
            <Icon name="progress_activity" className="ae-spin text-primary text-[32px]" />
            <p className="text-body-md">
              Calculando <Term termKey="embedding">embedding</Term> de referencia con <Term termKey="face_mesh" />…
            </p>
            <p className="text-label-sm">Re-inferencia server-side y firma (C-12)</p>
          </div>
        )}

        {/* ── Estado: completado ── */}
        {fase === 'completado' && (
          <div className="text-center space-y-sm">
            <Icon name="verified_user" className="text-success text-[40px]" fill />
            <p className="font-headline text-title-lg text-on-surface">¡Referencia capturada!</p>
            <p className="text-label-sm text-on-surface-variant">
              Vigencia: {BIOMETRIC_VALIDITY_MONTHS} meses desde hoy.
            </p>
          </div>
        )}

        {/* ── Estado: error ── */}
        {fase === 'error' && (
          <div className="text-center space-y-sm">
            <Icon name="videocam_off" className="text-error text-[40px]" fill />
            <p className="font-headline text-title-md text-on-surface">Sin acceso a la cámara</p>
            <p className="text-label-sm text-on-surface-variant">{errorMsg}</p>
            <p className="text-label-sm text-on-surface-variant">
              Habilitá el permiso de cámara en tu navegador y recargá la página.
            </p>
          </div>
        )}
      </Card>

      {/* Nota de privacidad (solo fuera del modo fullscreen) */}
      {!fullscreenFallback && (
        <div className="text-label-sm text-on-surface-variant bg-surface-container-low rounded-xl p-md border border-outline-variant/30 space-y-xs">
          <p className="font-semibold text-on-surface flex items-center gap-xs">
            <Icon name="lock" className="text-[16px]" />
            Privacidad y custodia de datos (Ley 25.326)
          </p>
          <p>
            La imagen de referencia y el <Term termKey="embedding">embedding</Term> se tratan como <strong>datos sensibles</strong>:
            cifrados at-rest, con finalidad acotada exclusivamente a la verificación de tu identidad
            y la revisión humana. Se eliminan al egreso de la institución (salvo hold disciplinario vigente).
            <strong> El sistema nunca sanciona automáticamente</strong> — solo prioriza para revisión humana (<Term termKey="l2_5" />).
            El cliente es sensor no confiable: el backend re-infiere y firma toda evidencia.
          </p>
        </div>
      )}
    </div>
  );
}
