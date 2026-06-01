/**
 * Paso de captura de referencia biométrica en el enrollment del perfil (C-22).
 *
 * Reutiliza el motor de visión existente (vision/VisionEngine.ts, liveness.ts).
 * Captura clip 3-5s + liveness activo + calcula embedding.
 * En demo: simula el embedding y captura un frame de video como imagen de referencia.
 *
 * DATOS SENSIBLES (Ley 25.326):
 * - Imagen de referencia: cifrada at-rest server-side; finalidad acotada a verificación
 *   de identidad y revisión humana; eliminada al egreso; holds legales difieren.
 * - Embedding: cifrado at-rest server-side; finalidad acotada a verificación 1:1;
 *   marcado para eliminación al egreso; holds legales difieren (RN-BIO-07/08).
 * El cliente es SENSOR NO CONFIABLE (RN-GLB-01): el backend re-infiere y firma (C-12).
 */
import { useEffect, useRef, useState } from 'react';
import { Icon, Button, Card } from '../../ui/components';
import { api, BIOMETRIC_VALIDITY_MONTHS } from '../../lib/api';
import { pickActiveChallenges } from '../../vision/liveness';
import { DESAFIOS } from '../../lib/api';
import { Term } from '../../ui/Term';
import type { ReferenciasBiometrica } from '../../lib/types';
import type { DesafioActivo } from '../../lib/types';

type Fase =
  | 'instrucciones'   // Pantalla inicial con instrucciones
  | 'capturando'      // Cámara activa + retos de liveness
  | 'procesando'      // Calculando embedding (simula re-inferencia)
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

export function EnrollmentBiometricStep({ referenciaActual, onCapturada, esRenovacion = false }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [fase, setFase] = useState<Fase>('instrucciones');
  const [desafios, setDesafios] = useState<DesafioActivo[]>([]);
  const [resueltos, setResueltos] = useState<string[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [camaraLista, setCamaraLista] = useState(false);

  // Inicializar cámara al mostrar el componente
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
    return () => {
      cancelado = true;
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const iniciarCaptura = () => {
    // Elegir retos de liveness al azar (pickActiveChallenges de vision/liveness.ts, RN-BIO-05)
    const ids = pickActiveChallenges(2);
    setDesafios(ids.map((id) => DESAFIOS.find((d) => d.id === id)!).filter(Boolean));
    setResueltos([]);
    setFase('capturando');
  };

  const resolverReto = (id: string) => {
    const next = [...resueltos, id];
    setResueltos(next);
    // Si todos los retos están resueltos, procesar
    if (next.length >= desafios.length) procesarCaptura();
  };

  /**
   * Captura un frame del video como imagen de referencia y simula el cálculo del embedding.
   * En producción: el clip 3-5s se envía al backend para re-inferencia y firma (C-12).
   * El embedding real se calcula con Face Mesh sobre el clip en el Web Worker.
   */
  const procesarCaptura = async () => {
    setFase('procesando');

    // Capturar frame del video como imagen de referencia (demo)
    let imagenDataUrl: string | null = null;
    if (videoRef.current && canvasRef.current) {
      const canvas = canvasRef.current;
      const video = videoRef.current;
      canvas.width = video.videoWidth || 320;
      canvas.height = video.videoHeight || 240;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        imagenDataUrl = canvas.toDataURL('image/jpeg', 0.85);
        // NOTA: Server-side esta imagen sería cifrada AES-256-GCM antes de persistir.
        // Finalidad: verificación de identidad y revisión humana. Eliminada al egreso.
      }
    }

    // Simular embedding facial (demo — en producción: Face Mesh sobre el clip en Worker)
    // NOTA: Server-side el embedding real se re-infiere y cifra (RN-BIO-08, C-12).
    const embeddingSimulado = Array.from({ length: 128 }, () => Math.random() * 2 - 1);

    // Guardar en api mock (persiste referencia con metadatos de vigencia)
    const referencia = await api.guardarReferenciaBiometrica({
      imagen: imagenDataUrl,
      embedding: embeddingSimulado,
    });

    setFase('completado');
    onCapturada(referencia);
  };

  const formatearFecha = (iso: string) =>
    new Date(iso).toLocaleDateString('es-AR', { day: '2-digit', month: 'long', year: 'numeric' });

  return (
    <div className="space-y-lg animate-in fade-in duration-400">
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

      {/* Visor de cámara */}
      <Card className="flex flex-col items-center gap-lg">
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
            fase === 'completado' ? 'border-success' :
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
        </div>

        {/* Estado: instrucciones iniciales */}
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
            {camaraLista && (
              <Button icon="photo_camera" onClick={iniciarCaptura}>
                Iniciar captura de referencia
              </Button>
            )}
          </div>
        )}

        {/* Estado: retos de liveness activos */}
        {fase === 'capturando' && (
          <div className="w-full space-y-sm">
            <p className="text-label-md text-on-surface text-center font-semibold">
              Realizá los siguientes gestos (anti-suplantación de identidad):
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-sm">
              {desafios.map((d) => {
                const hecho = resueltos.includes(d.id);
                return (
                  <button
                    key={d.id}
                    disabled={hecho}
                    onClick={() => resolverReto(d.id)}
                    className={`flex items-center gap-sm p-sm rounded-xl border transition-all ${
                      hecho
                        ? 'bg-success-container border-success/30 text-success'
                        : 'bg-surface-container-low border-outline-variant hover:border-primary-container'
                    }`}
                  >
                    <Icon name={hecho ? 'check_circle' : 'gesture'} fill={hecho} />
                    <span className="text-label-md font-semibold">{d.label}</span>
                  </button>
                );
              })}
            </div>
            <p className="text-label-sm text-on-surface-variant text-center">
              (Demo: tocá cada gesto para simular su detección por el motor de visión)
            </p>
          </div>
        )}

        {/* Estado: procesando */}
        {fase === 'procesando' && (
          <div className="text-center space-y-sm text-on-surface-variant">
            <Icon name="progress_activity" className="ae-spin text-primary text-[32px]" />
            <p className="text-body-md">
              Calculando <Term termKey="embedding">embedding</Term> de referencia con <Term termKey="face_mesh" />…
            </p>
            <p className="text-label-sm">Re-inferencia server-side y firma (C-12)</p>
          </div>
        )}

        {/* Estado: completado */}
        {fase === 'completado' && (
          <div className="text-center space-y-sm">
            <Icon name="verified_user" className="text-success text-[40px]" fill />
            <p className="font-headline text-title-lg text-on-surface">¡Referencia capturada!</p>
            <p className="text-label-sm text-on-surface-variant">
              Vigencia: {BIOMETRIC_VALIDITY_MONTHS} meses desde hoy.
            </p>
          </div>
        )}

        {/* Estado: error */}
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

      {/* Nota de privacidad */}
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
    </div>
  );
}
