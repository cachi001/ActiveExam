/**
 * Paso opcional de escaneo de DNI en el enrollment del perfil (C-22).
 *
 * Controlado por el feature flag ENABLE_DNI_SCAN (VITE_ENABLE_DNI_SCAN=1).
 * Con flag off: presenta el paso como "próximamente / opcional" y NO bloquea.
 * Con flag on: permite capturar el DNI pero su ausencia tampoco bloquea el perfil.
 *
 * DATO SENSIBLE (Ley 25.326):
 * Server-side: cifrado AES-256-GCM, finalidad acotada a verificación de identidad,
 * eliminado al egreso del estudiante, holds legales difieren la eliminación.
 *
 * Spec: optional-dni-scan (C-22)
 */
import { useRef, useState } from 'react';
import { Icon, Button, Card } from '../../ui/components';
import { api, ENABLE_DNI_SCAN } from '../../lib/api';
import type { EscaneDNI } from '../../lib/types';

interface Props {
  escanActual: EscaneDNI | null;
  onEscaneado: (escan: EscaneDNI) => void;
  onOmitir: () => void;
}

type Fase = 'inicio' | 'capturando' | 'procesando' | 'completado';

export function EnrollmentDniStep({ escanActual, onEscaneado, onOmitir }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [fase, setFase] = useState<Fase>(escanActual?.captura_completada ? 'completado' : 'inicio');
  const [camaraLista, setCamaraLista] = useState(false);
  const [errorCamara, setErrorCamara] = useState<string | null>(null);

  const iniciarCamara = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setCamaraLista(true);
      setFase('capturando');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'permiso denegado';
      setErrorCamara(`No se pudo acceder a la cámara: ${msg}`);
    }
  };

  const capturarDNI = async () => {
    if (!videoRef.current || !canvasRef.current) return;
    setFase('procesando');

    // Capturar frame del video como imagen del DNI (demo)
    const canvas = canvasRef.current;
    const video = videoRef.current;
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    let imagenDataUrl: string | null = null;
    if (ctx) {
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      imagenDataUrl = canvas.toDataURL('image/jpeg', 0.85);
      // NOTA: Server-side esta imagen sería cifrada AES-256-GCM antes de persistir.
      // Finalidad: verificación de identidad únicamente. Eliminada al egreso.
    }

    // Detener stream de cámara
    streamRef.current?.getTracks().forEach((t) => t.stop());
    setCamaraLista(false);

    if (imagenDataUrl) {
      const escan = await api.guardarEscaneDNI(imagenDataUrl);
      setFase('completado');
      onEscaneado(escan);
    } else {
      setFase('inicio');
    }
  };

  const formatearFecha = (iso: string) =>
    new Date(iso).toLocaleDateString('es-AR', { day: '2-digit', month: 'long', year: 'numeric' });

  return (
    <div className="space-y-lg animate-in fade-in duration-400">
      {/* Encabezado */}
      <div className="flex items-center gap-sm">
        <div className="w-10 h-10 rounded-xl bg-surface-container-high text-on-surface-variant flex items-center justify-center shrink-0">
          <Icon name="badge" className="text-[20px]" />
        </div>
        <div>
          <h3 className="font-headline text-title-md text-on-surface flex items-center gap-sm">
            Verificación de identidad documental
            <span className="text-label-sm font-normal text-on-surface-variant bg-surface-container px-sm py-base rounded-full">
              Opcional
            </span>
          </h3>
          <p className="text-label-sm text-on-surface-variant">
            Escaneo de DNI · No bloquea el perfil completo
          </p>
        </div>
      </div>

      {/* Flag inactivo — mostrar como próximamente */}
      {!ENABLE_DNI_SCAN ? (
        <Card className="border-outline-variant/30">
          <div className="flex items-start gap-sm">
            <Icon name="upcoming" className="text-on-surface-variant text-[22px] shrink-0 mt-px" />
            <div className="space-y-xs">
              <p className="text-label-md font-semibold text-on-surface">Verificación documental — Próximamente</p>
              <p className="text-label-sm text-on-surface-variant">
                El escaneo del DNI estará disponible en una próxima actualización de la plataforma.
                Este paso es <strong>completamente opcional</strong> y su ausencia no afecta tu
                habilitación para rendir exámenes.
              </p>
              <p className="text-label-sm text-on-surface-variant">
                Cuando esté disponible, el documento será tratado como <strong>dato sensible</strong> bajo
                la Ley 25.326: cifrado at-rest, finalidad acotada a la verificación de identidad,
                eliminado al egreso y protegido por holds legales.
              </p>
            </div>
          </div>
          <div className="mt-md pt-md border-t border-outline-variant/40">
            <Button variant="ghost" onClick={onOmitir} icon="arrow_forward">
              Continuar sin DNI
            </Button>
          </div>
        </Card>
      ) : (
        /* Flag activo — flujo de captura */
        <Card className="space-y-lg">
          {/* Completado */}
          {fase === 'completado' && escanActual && (
            <div className="space-y-md">
              <div className="flex items-center gap-sm text-success">
                <Icon name="verified" className="text-[22px]" fill />
                <p className="text-label-md font-semibold text-on-surface">DNI registrado</p>
              </div>
              <p className="text-label-sm text-on-surface-variant">
                Capturado el {formatearFecha(escanActual.fecha_captura)}.
                Tratado como dato sensible (Ley 25.326): cifrado, finalidad acotada,
                eliminado al egreso.
              </p>
              <Button variant="ghost" onClick={onOmitir} icon="arrow_forward" className="w-full">
                Continuar
              </Button>
            </div>
          )}

          {/* Inicio */}
          {fase === 'inicio' && (
            <div className="space-y-md">
              <p className="text-body-md text-on-surface-variant">
                Podés escanear tu DNI para reforzar la verificación de identidad documental.
                Este paso es <strong>opcional</strong> — podés omitirlo y completar el perfil igual.
              </p>

              {/* Nota legal prominente */}
              <div className="flex items-start gap-sm bg-surface-container-low rounded-xl p-md border border-outline-variant/30">
                <Icon name="privacy_tip" className="text-on-surface-variant text-[18px] shrink-0 mt-px" />
                <p className="text-label-sm text-on-surface-variant">
                  <strong>Dato sensible (Ley 25.326):</strong> El DNI se cifra at-rest y su uso queda
                  restringido exclusivamente a la verificación de tu identidad. Se elimina al egreso
                  de la institución (salvo hold disciplinario vigente).
                </p>
              </div>

              {errorCamara && (
                <p className="text-label-sm text-error">{errorCamara}</p>
              )}

              <div className="flex gap-sm flex-col sm:flex-row">
                <Button variant="secondary" icon="badge" onClick={iniciarCamara}>
                  Escanear DNI
                </Button>
                <Button variant="ghost" onClick={onOmitir} icon="skip_next">
                  Omitir este paso
                </Button>
              </div>
            </div>
          )}

          {/* Capturando */}
          {fase === 'capturando' && (
            <div className="space-y-md">
              <p className="text-label-md text-on-surface font-semibold">
                Apuntá la cámara al frente de tu DNI y asegurate que se lea con claridad.
              </p>
              <div className="relative w-full aspect-video rounded-xl overflow-hidden bg-inverse-surface">
                <video
                  ref={videoRef}
                  muted
                  playsInline
                  className="w-full h-full object-cover"
                  aria-label="Vista de cámara para escaneo de DNI"
                />
                <canvas ref={canvasRef} className="hidden" aria-hidden />
                <div className="absolute inset-4 border-2 border-dashed border-primary-container rounded-xl" />
              </div>
              {camaraLista && (
                <Button icon="camera" onClick={capturarDNI} className="w-full">
                  Capturar imagen del DNI
                </Button>
              )}
            </div>
          )}

          {/* Procesando */}
          {fase === 'procesando' && (
            <div className="text-center space-y-sm text-on-surface-variant py-lg">
              <Icon name="progress_activity" className="ae-spin text-primary text-[32px]" />
              <p className="text-body-md">Procesando imagen del DNI…</p>
              <p className="text-label-sm">Cifrado y almacenamiento seguro</p>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
