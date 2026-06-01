/**
 * CameraSnapshotCapture — componente compartido de captura de foto estática (C-37).
 *
 * Overlay full-screen (createPortal a document.body, estilo banco, fondo blanco).
 * getUserMedia + canvas.drawImage + toDataURL — sin MediaPipe, sin RAF.
 * Marco-guía parametrizable por forma: 'oval' para foto de perfil, 'rect' para DNI (C-38).
 *
 * Flujo: montar → getUserMedia → video en vivo con marco → "Capturar" → preview →
 *        "Usar foto" → onCapture(dataUrl) | "Repetir" → volver a video.
 *
 * Referencia visual: BiometricCapture (C-36) — NO reutilizado (liveness/RAF/MediaPipe),
 * pero el estilo de overlay (createPortal, clip-path, fondo blanco) es idéntico.
 *
 * DATO PERSONAL (Ley 25.326): la foto de perfil tiene finalidad acotada (avatar en la UI).
 * Demo: dataURL en memoria. Server-side: cifrado AES-256-GCM, eliminado al egreso.
 */

import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Icon } from './components';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface CameraSnapshotCaptureProps {
  /** Forma del marco-guía. 'oval' para foto de perfil; 'rect' para DNI (C-38). */
  shape: 'oval' | 'rect';
  /** Ratio ancho/alto del marco (default: oval → 3/4, rect → 85.6/54 ≈ CR80). */
  aspectRatio?: number;
  /** Texto de instrucción principal mostrado bajo el marco en estado 'capturando'. */
  instruction: string;
  /** Label contextual opcional sobre el marco (e.g., "Foto de perfil"). */
  contextLabel?: string;
  /** Calidad JPEG del snapshot (0.0–1.0, default: 0.85). */
  jpegQuality?: number;
  /** Callback al confirmar la foto. Recibe dataURL JPEG. */
  onCapture: (dataUrl: string) => void;
  /** Callback al cancelar. */
  onCancel: () => void;
  /** Mostrar esquinas tipo escáner (solo aplica a shape='rect', e.g. DNI). Default: false. */
  scannerCorners?: boolean;
  /** facingMode de la cámara: 'user' (frontal) o 'environment' (trasera, para DNI en móvil). Default: 'user'. */
  facingMode?: ConstrainDOMString;
}

// ---------------------------------------------------------------------------
// Estado interno
// ---------------------------------------------------------------------------

type Fase = 'capturando' | 'preview' | 'error';

// ---------------------------------------------------------------------------
// Componente
// ---------------------------------------------------------------------------

export function CameraSnapshotCapture({
  shape,
  aspectRatio,
  instruction,
  contextLabel,
  jpegQuality = 0.85,
  scannerCorners = false,
  facingMode = 'user',
  onCapture,
  onCancel,
}: CameraSnapshotCaptureProps) {

  // Task 3.3: Refs
  const videoRef  = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Task 3.4: Estados
  const [fase, setFase]                   = useState<Fase>('capturando');
  const [previewDataUrl, setPreviewDataUrl] = useState<string | null>(null);
  const [errorMsg, setErrorMsg]           = useState<string | null>(null);

  // ---------------------------------------------------------------------------
  // Task 4.1 + 4.2 + 4.3: useEffect de montaje — getUserMedia + cleanup
  // ---------------------------------------------------------------------------
  useEffect(() => {
    let cancelado = false;

    navigator.mediaDevices?.getUserMedia({ video: { facingMode } })
      .then((stream) => {
        if (cancelado) { stream.getTracks().forEach((t) => t.stop()); return; }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.play().catch(() => {});
        }
      })
      .catch((err: Error) => {
        if (!cancelado) {
          setErrorMsg(`Sin acceso a la cámara: ${err?.message ?? 'permiso denegado'}`);
          setFase('error');
        }
      });

    // Task 4.3: cleanup
    return () => {
      cancelado = true;
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  // ---------------------------------------------------------------------------
  // Task 4.4: handleCancel
  // ---------------------------------------------------------------------------
  const handleCancel = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    onCancel();
  };

  // ---------------------------------------------------------------------------
  // Task 5.1: handleCapturar — snapshot via canvas
  // ---------------------------------------------------------------------------
  const handleCapturar = () => {
    const video = videoRef.current;
    if (!video) return;

    const canvas = canvasRef.current ?? document.createElement('canvas');
    canvas.width  = video.videoWidth  || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Cámara frontal: el preview va espejado (scaleX-1); espejamos el canvas para que
    // la imagen GUARDADA coincida con lo que ve el usuario.
    if (facingMode === 'user') {
      ctx.translate(canvas.width, 0);
      ctx.scale(-1, 1);
    }
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL('image/jpeg', jpegQuality);
    setPreviewDataUrl(dataUrl);
    setFase('preview');
  };

  // ---------------------------------------------------------------------------
  // Task 5.2: handleUsarFoto
  // ---------------------------------------------------------------------------
  const handleUsarFoto = () => {
    if (!previewDataUrl) return;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    onCapture(previewDataUrl);
  };

  // ---------------------------------------------------------------------------
  // Task 5.3: handleRepetir
  // ---------------------------------------------------------------------------
  const handleRepetir = () => {
    setPreviewDataUrl(null);
    setFase('capturando');
  };

  // ---------------------------------------------------------------------------
  // Derivados de estilo según shape
  // ---------------------------------------------------------------------------
  const defaultAspect = shape === 'oval' ? (3 / 4) : (85.6 / 54);
  const ratio = aspectRatio ?? defaultAspect;
  // Para aspect-ratio CSS: necesitamos width/height relativos
  const aspectStyle = shape === 'oval'
    ? { aspectRatio: '3 / 4' }
    : { aspectRatio: `${ratio}` };

  // ---------------------------------------------------------------------------
  // Task 6.9: Estado de error de cámara
  // ---------------------------------------------------------------------------
  if (fase === 'error') {
    return createPortal(
      // Task 6.2: contenedor raíz
      <div className="fixed inset-0 z-[60] bg-white flex flex-col items-center justify-center px-6">
        {/* Task 6.3: Botón Cancelar discreto */}
        <button
          onClick={handleCancel}
          className="absolute top-4 right-4 inline-flex items-center gap-1 text-sm text-neutral-500 hover:text-neutral-900 transition-colors px-3 py-1.5 rounded-full"
        >
          Cancelar <Icon name="close" className="text-[18px]" />
        </button>
        {/* Task 6.9: Icono + mensaje de error */}
        <div className="text-center space-y-4 max-w-xs">
          <Icon name="videocam_off" className="text-error text-[48px]" fill />
          <p className="font-headline text-title-lg text-neutral-900">Sin acceso a la cámara</p>
          <p className="text-body-sm text-neutral-600">{errorMsg}</p>
          <p className="text-label-sm text-neutral-500">
            Habilitá el permiso de cámara en tu navegador y volvé a intentarlo.
          </p>
        </div>
      </div>,
      document.body,
    );
  }

  // ---------------------------------------------------------------------------
  // Task 6.1: Portal al body — overlay principal
  // ---------------------------------------------------------------------------
  return createPortal(
    // Task 6.2: contenedor raíz
    <div className="fixed inset-0 z-[60] bg-white flex flex-col items-center justify-center px-6">
      {/* Task 6.3: Botón Cancelar discreto */}
      <button
        onClick={handleCancel}
        className="absolute top-4 right-4 inline-flex items-center gap-1 text-sm text-neutral-500 hover:text-neutral-900 transition-colors px-3 py-1.5 rounded-full"
      >
        Cancelar <Icon name="close" className="text-[18px]" />
      </button>

      {/* Task 6.4: contextLabel opcional encima del marco */}
      {contextLabel && (
        <p className="text-sm text-neutral-500 mb-6 text-center max-w-xs">{contextLabel}</p>
      )}

      {/* ── Marco-guía ── */}
      {shape === 'oval' ? (
        /* Task 6.5: Marco oval */
        <div
          className="relative"
          style={{ width: 'min(80vw, 300px)', filter: 'drop-shadow(0 10px 24px rgba(0,0,0,0.15))' }}
        >
          <div
            className="relative w-full overflow-hidden bg-neutral-100"
            style={{ ...aspectStyle, clipPath: 'ellipse(50% 50% at 50% 50%)' }}
          >
            {fase === 'capturando' && (
              <video
                ref={videoRef}
                autoPlay
                muted
                playsInline
                className="absolute inset-0 w-full h-full object-cover"
                style={{ transform: facingMode === 'user' ? 'scaleX(-1)' : undefined }}
                aria-label="Vista de cámara para foto de perfil"
              />
            )}
            {fase === 'preview' && previewDataUrl && (
              <img
                src={previewDataUrl}
                className="rounded-full object-cover w-full h-full"
                alt="Vista previa de la foto capturada"
              />
            )}
          </div>
        </div>
      ) : (
        /* Task 6.6: Marco rect */
        <div
          className="relative rounded-xl border-2 border-neutral-300 overflow-hidden bg-neutral-100"
          style={{ width: 'min(80vw, 400px)', ...aspectStyle }}
        >
          {fase === 'capturando' && (
            <video
              ref={videoRef}
              autoPlay
              muted
              playsInline
              className="absolute inset-0 w-full h-full object-cover"
              style={{ transform: facingMode === 'user' ? 'scaleX(-1)' : undefined }}
              aria-label="Vista de cámara para escaneo de documento"
            />
          )}
          {fase === 'preview' && previewDataUrl && (
            <img
              src={previewDataUrl}
              className="rounded-xl object-cover w-full h-full"
              alt="Vista previa del documento capturado"
            />
          )}
          {scannerCorners && <ScannerCorners />}
        </div>
      )}

      {/* Canvas oculto para el snapshot */}
      <canvas ref={canvasRef} className="hidden" />

      {/* ── Sección inferior — instrucción + acciones ── */}
      <div className="mt-8 text-center space-y-4 w-full max-w-xs">
        {/* Task 6.7: Estado 'capturando' */}
        {fase === 'capturando' && (
          <>
            {/* Task 6.10: Texto de instrucción */}
            <p className="text-neutral-600 text-center max-w-xs text-sm">{instruction}</p>
            <button
              onClick={handleCapturar}
              className="inline-flex items-center gap-2 bg-neutral-900 hover:bg-neutral-700 text-white font-semibold text-sm px-6 py-3 rounded-full transition-colors"
            >
              <Icon name="photo_camera" className="text-[20px]" />
              Capturar
            </button>
          </>
        )}

        {/* Task 6.8: Estado 'preview' */}
        {fase === 'preview' && (
          <>
            <p className="text-neutral-600 text-center max-w-xs text-sm">
              ¿Usás esta foto?
            </p>
            <div className="flex items-center justify-center gap-3">
              <button
                onClick={handleRepetir}
                className="inline-flex items-center gap-2 border border-neutral-300 text-neutral-700 hover:bg-neutral-100 font-semibold text-sm px-5 py-2.5 rounded-full transition-colors"
              >
                <Icon name="refresh" className="text-[18px]" />
                Repetir
              </button>
              <button
                onClick={handleUsarFoto}
                className="inline-flex items-center gap-2 bg-neutral-900 hover:bg-neutral-700 text-white font-semibold text-sm px-5 py-2.5 rounded-full transition-colors"
              >
                <Icon name="check" className="text-[18px]" />
                Usar foto
              </button>
            </div>
          </>
        )}
      </div>
    </div>,
    document.body,
  );
}

/** Esquinas tipo escáner (4 ángulos en L) para el marco rectangular del DNI. */
function ScannerCorners() {
  const base = 'absolute w-7 h-7 border-white/90';
  return (
    <div className="absolute inset-0 pointer-events-none" aria-hidden>
      <span className={`${base} top-2 left-2 border-t-[3px] border-l-[3px] rounded-tl-md`} />
      <span className={`${base} top-2 right-2 border-t-[3px] border-r-[3px] rounded-tr-md`} />
      <span className={`${base} bottom-2 left-2 border-b-[3px] border-l-[3px] rounded-bl-md`} />
      <span className={`${base} bottom-2 right-2 border-b-[3px] border-r-[3px] rounded-br-md`} />
    </div>
  );
}
