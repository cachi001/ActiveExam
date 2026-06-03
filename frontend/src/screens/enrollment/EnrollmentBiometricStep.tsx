/**
 * Paso de captura de referencia biométrica en el enrollment del perfil (C-22).
 *
 * C-36: refactorizado para delegar la captura a `BiometricCapture` (componente
 * compartido). EnrollmentBiometricStep retiene:
 * - Encabezado contextual (renovación, vigencia, nota de referencia anterior).
 * - Fase `instrucciones` con el botón "Iniciar captura de referencia".
 * - Nota de privacidad Ley 25.326 (fases instrucciones y completado).
 * - Callback `onCapturada` con la referencia biométrica calculada.
 * - Fases `instrucciones`, `procesando`, `completado`, `error` sin cambios funcionales.
 *
 * El cálculo del embedding (embeddingFromLandmarks) ocurre en handleComplete,
 * en el caller, para que el dato sensible no circule por BiometricCapture.
 *
 * DATOS SENSIBLES (Ley 25.326):
 * - Imagen de referencia: cifrada at-rest server-side; finalidad acotada a verificación
 *   de identidad y revisión humana; eliminada al egreso; holds legales difieren.
 * - Embedding: cifrado at-rest server-side; finalidad acotada a verificación 1:1;
 *   marcado para eliminación al egreso; holds legales difieren (RN-BIO-07/08).
 * El cliente es SENSOR NO CONFIABLE (RN-GLB-01): el backend re-infiere y firma (C-12).
 * L2.5 intacto: el sistema nunca sanciona automáticamente.
 */
import { useCallback, useState } from 'react';
import { Icon, Button, Card } from '../../ui/components';
import { api, BIOMETRIC_VALIDITY_MONTHS } from '../../lib/api';
import { Term } from '../../ui/Term';
import { BiometricCapture } from '../../ui/BiometricCapture';
import { computeFaceDescriptor } from '../../vision/faceEmbedding';
import { useApp } from '../../lib/store';
import type { ReferenciasBiometrica } from '../../lib/types';
import type { FaceLandmark } from '../../vision/VisionEngine';

// ---------------------------------------------------------------------------
// Tipos locales
// ---------------------------------------------------------------------------

type Fase =
  | 'instrucciones'   // Pantalla inicial con instrucciones
  | 'capturando'      // BiometricCapture activo (overlay inmersivo)
  | 'procesando'      // Calculando embedding y guardando referencia
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
// Componente
// ---------------------------------------------------------------------------

export function EnrollmentBiometricStep({ referenciaActual, onCapturada, esRenovacion = false }: Props) {

  // ── Estado de UI ────────────────────────────────────────────────────────
  const [fase, setFase]       = useState<Fase>('instrucciones');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [refRegistrada, setRefRegistrada] = useState(false);
  const setBiometriaReferencia = useApp((s) => s.setBiometriaReferencia);

  // ---------------------------------------------------------------------------
  // handleComplete — computar el descriptor 128-d REAL (face-api) sobre el frame
  // capturado y guardarlo como REFERENCIA para la verificación 1:1 posterior.
  // ---------------------------------------------------------------------------
  const handleComplete = useCallback(async (_landmarks: FaceLandmark[], frame: HTMLCanvasElement | null) => {
    setFase('procesando');
    setRefRegistrada(false);

    try {
      // Descriptor real de 128-d con face-api sobre el frame del video.
      // Dato sensible (Ley 25.326): no se loguea.
      const descriptor = frame ? await computeFaceDescriptor(frame) : null;

      // Persistir la referencia en el enrollment (mock/real) + en el store/localStorage
      // para la verificación 1:1. El backend re-infiere y cifra server-side (C-12).
      const referencia = await api.guardarReferenciaBiometrica({
        imagen: null,
        embedding: descriptor,
      });

      if (descriptor) {
        setBiometriaReferencia(descriptor);
        setRefRegistrada(true);
      }

      setFase('completado');
      onCapturada(referencia);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(msg);
      setFase('error');
    }
  }, [onCapturada, setBiometriaReferencia]);

  // ---------------------------------------------------------------------------
  // Task 8.4: cancelarCaptura — vuelve a instrucciones
  // ---------------------------------------------------------------------------
  const cancelarCaptura = useCallback(() => {
    setFase('instrucciones');
  }, []);

  // ---------------------------------------------------------------------------
  // Formatear fecha
  // ---------------------------------------------------------------------------
  const formatearFecha = (iso: string) =>
    new Date(iso).toLocaleDateString('es-AR', { day: '2-digit', month: 'long', year: 'numeric' });

  // ---------------------------------------------------------------------------
  // Task 8.5: fase capturando → delegar a BiometricCapture (overlay toma la pantalla)
  // ---------------------------------------------------------------------------
  if (fase === 'capturando') {
    return (
      <BiometricCapture
        onComplete={(landmarks, frame) => { void handleComplete(landmarks, frame); }}
        onCancel={cancelarCaptura}
        contextLabel="Captura de referencia biométrica"
      />
    );
  }

  // ---------------------------------------------------------------------------
  // Render para fases instrucciones, procesando, completado, error
  // ---------------------------------------------------------------------------
  return (
    <div className="space-y-lg animate-in fade-in duration-400">

      {/* Task 8.6: Encabezado contextual — solo en fases fuera del overlay */}
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

      {/* Contenedor principal */}
      <Card className="flex flex-col items-center gap-lg">
        {/* Visor de cámara (estático en instrucciones/completado/error) */}
        <div className="relative w-[260px] h-[320px] rounded-[36px] overflow-hidden bg-inverse-surface flex items-center justify-center">
          <div className={`relative w-[160px] h-[210px] rounded-[50%] border-2 border-dashed transition-colors duration-300 ${
            fase === 'completado'  ? 'border-success' :
            fase === 'procesando' ? 'border-warning animate-pulse' :
            'border-primary-container'
          }`} />
        </div>

        {/* ── Task 8.8: Estado: instrucciones iniciales ── */}
        {fase === 'instrucciones' && (
          <div className="text-center space-y-md w-full">
            <p className="text-body-md text-on-surface-variant">
              Encuadrá tu rostro dentro del óvalo con buena iluminación y sin objetos que lo cubran.
              La captura dura 3–5 segundos y requiere dos gestos anti-suplantación.
            </p>
            {/* Botón iniciar — activa la fase capturando con el overlay BiometricCapture */}
            <Button icon="photo_camera" onClick={() => setFase('capturando')}>
              Iniciar captura de referencia
            </Button>
          </div>
        )}

        {/* ── Task 8.8: Estado: procesando ── */}
        {fase === 'procesando' && (
          <div className="text-center space-y-sm text-on-surface-variant">
            <Icon name="progress_activity" className="ae-spin text-primary text-[32px]" />
            <p className="text-body-md">
              Calculando <Term termKey="embedding">embedding</Term> de referencia (descriptor facial de 128 dimensiones)…
            </p>
            <p className="text-label-sm">Re-inferencia server-side y firma (C-12)</p>
          </div>
        )}

        {/* ── Task 8.8: Estado: completado ── */}
        {fase === 'completado' && (
          <div className="text-center space-y-sm">
            <Icon name="verified_user" className="text-success text-[40px]" fill />
            <p className="font-headline text-title-lg text-on-surface">¡Referencia capturada!</p>
            <p className="text-label-sm text-on-surface-variant">
              Vigencia: {BIOMETRIC_VALIDITY_MONTHS} meses desde hoy.
            </p>
            {refRegistrada ? (
              <p className="inline-flex items-center gap-xs text-label-sm text-success">
                <Icon name="fingerprint" className="text-[16px]" />
                Referencia biométrica registrada para la verificación 1:1.
              </p>
            ) : (
              <p className="text-label-sm text-warning">
                No se pudo extraer el descriptor facial del último frame. Podés reintentar
                la captura para habilitar la verificación 1:1.
              </p>
            )}
          </div>
        )}

        {/* ── Task 8.8: Estado: error ── */}
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

      {/* Task 8.7: nota de privacidad Ley 25.326 — visible en instrucciones y completado */}
      {(fase === 'instrucciones' || fase === 'completado') && (
        <div className="text-label-sm text-on-surface-variant bg-surface-container-low rounded-xl p-md border border-outline-variant/30 space-y-xs">
          <p className="font-semibold text-on-surface flex items-center gap-xs">
            <Icon name="lock" className="text-[16px]" />
            Privacidad y custodia de datos (Ley 25.326)
          </p>
          <p>
            La imagen de referencia y el <Term termKey="embedding">embedding</Term> se tratan como <strong>datos sensibles</strong>:
            cifrados at-rest, con finalidad acotada exclusivamente a la verificación de tu identidad
            y la revisión humana (la decisión es siempre humana). Se eliminan al egreso de la institución (salvo hold disciplinario vigente).
            El cliente es sensor no confiable: el backend re-infiere y firma toda evidencia.
          </p>
        </div>
      )}
    </div>
  );
}
