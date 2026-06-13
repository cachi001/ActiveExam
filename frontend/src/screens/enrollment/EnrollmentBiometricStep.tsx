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
  const setBiometricoReferenciaId = useApp((s) => s.setBiometricoReferenciaId);

  // ---------------------------------------------------------------------------
  // handleComplete — computar el descriptor 128-d REAL (face-api) sobre el frame
  // capturado y guardarlo como REFERENCIA para la verificación 1:1 posterior.
  // ---------------------------------------------------------------------------
  // D3 (C-49): firma ampliada — el enrollment ignora passiveOk/virtualCameraDetected
  // con `_` (su liveness se evalúa durante los retos de la captura de referencia,
  // no condiciona el guardado del descriptor). Ver design D3 / Open Questions.
  const handleComplete = useCallback(async (
    _landmarks: FaceLandmark[],
    frame: HTMLCanvasElement | null,
    _passiveOk: boolean,
    _retosResueltos: string[],
    _virtualCameraDetected: boolean,
  ) => {
    setFase('procesando');
    setRefRegistrada(false);

    try {
      // Descriptor real de 128-d con face-api sobre el frame del video.
      // Dato sensible (Ley 25.326): no se loguea.
      const descriptor = frame ? await computeFaceDescriptor(frame) : null;

      // C-56: POST al backend real cuando USE_REAL_BACKEND=1.
      // El backend cifra at-rest y devuelve un referencia_id opaco.
      // En modo demo: guarda in-memory (comportamiento anterior).
      // Si el backend falla: propagar el error (no avanzar la fase).
      const referencia = await api.guardarReferenciaBiometrica({
        imagen: null,
        embedding: descriptor,
      });

      if (descriptor) {
        // C-56: en modo demo, el embedding se guarda en memoria para la verificación 1:1.
        // En modo real, el embedding queda en el backend; el store recibe solo el referencia_id.
        if (referencia.referencia_id) {
          // Modo real: persistir el referencia_id opaco, descartar el embedding crudo.
          setBiometricoReferenciaId(referencia.referencia_id);
          setBiometriaReferencia(null);
        } else {
          // Modo demo: guardar el descriptor en el store (sin localStorage).
          setBiometriaReferencia(descriptor);
        }
        setRefRegistrada(true);
      }

      setFase('completado');
      onCapturada(referencia);
    } catch (err) {
      // Errores de backend (4xx/5xx/red) o de cámara: mostrar en fase 'error'.
      // La fase NO avanza: el alumno ve el error y puede reintentar (task 11.3).
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(msg);
      setFase('error');
    }
  }, [onCapturada, setBiometriaReferencia, setBiometricoReferenciaId]);

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
        onComplete={(landmarks, frame, passiveOk, retosResueltos, virtualCameraDetected) => {
          void handleComplete(landmarks, frame, passiveOk, retosResueltos, virtualCameraDetected);
        }}
        onCancel={cancelarCaptura}
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
            Vigencia {BIOMETRIC_VALIDITY_MONTHS} meses
          </p>
        </div>
      </div>

      {/* Estado actual (si hay referencia previa caducada o por renovar) */}
      {referenciaActual && esRenovacion && (
        <div className="flex items-start gap-sm bg-warning-container border border-warning/30 rounded-xl p-md">
          <Icon name="refresh" className="text-warning text-[18px] shrink-0 mt-px" />
          <div className="text-label-sm text-on-surface">
            <p><strong>Referencia anterior:</strong> capturada el {formatearFecha(referenciaActual.fecha_captura)}.</p>
            <p className="text-on-surface-variant mt-base">
              {referenciaActual.vigencia === 'caducada'
                ? 'La referencia venció. La nueva captura reemplazará la anterior.'
                : referenciaActual.renovacion_anticipada_requerida
                  ? 'Detectamos cambios en tu rostro. La nueva captura reemplazará la anterior.'
                  : 'La nueva captura reemplazará la referencia anterior.'}
            </p>
          </div>
        </div>
      )}

      {/* Contenedor principal */}
      <Card className="flex flex-col items-center gap-lg">
        {/* Óvalo guía estático — SOLO en instrucciones (antes de la captura). En
            procesando/éxito/error se oculta: mostrar el óvalo vacío titilando mientras
            se guarda no aporta y confunde (el alumno ya hizo la captura). */}
        {fase === 'instrucciones' && (
          <div
            className="relative"
            style={{ width: 'min(70vw, 220px)', filter: 'drop-shadow(0 8px 20px rgba(16,24,40,0.08))' }}
          >
            <div
              className="w-full rounded-[50%] border-2 border-dashed bg-surface-container-high border-outline-variant transition-colors duration-300"
              style={{ aspectRatio: '3 / 4' }}
            />
          </div>
        )}

        {/* ── Task 8.8: Estado: instrucciones iniciales ── */}
        {fase === 'instrucciones' && (
          <div className="text-center space-y-md w-full">
            <p className="text-body-md text-on-surface-variant leading-relaxed">
              Ubicá tu rostro dentro del óvalo, con buena luz y sin nada que lo tape (gorra,
              anteojos oscuros, barbijo). Dura unos segundos e incluye <strong>tres gestos rápidos</strong>
              {' '}para confirmar que sos una persona real.
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
            <p className="text-body-md">Procesando tu referencia facial…</p>
            <p className="text-label-sm">La estamos guardando de forma segura. Tarda unos segundos.</p>
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
                No pudimos procesar bien tu rostro en esta toma. Volvé a intentar la captura.
              </p>
            )}
          </div>
        )}

        {/* ── Task 8.8 / 11.3 (C-56): Estado: error ── */}
        {fase === 'error' && (
          <div className="text-center space-y-sm">
            <Icon name="videocam_off" className="text-error text-[40px]" fill />
            <p className="font-headline text-title-md text-on-surface">Error en la captura</p>
            <p className="text-label-sm text-on-surface-variant">{errorMsg}</p>
            <p className="text-label-sm text-on-surface-variant">
              Si el error persiste, verificá tu cámara y conexión, y contactá al soporte.
            </p>
            {/* C-56: botón de reintentar para errores de backend (task 11.3) */}
            <Button icon="refresh" onClick={() => { setErrorMsg(null); setFase('instrucciones'); }}>
              Reintentar captura
            </Button>
          </div>
        )}
      </Card>

      {/* Task 8.7: nota de privacidad Ley 25.326 — visible en instrucciones y completado */}
      {(fase === 'instrucciones' || fase === 'completado') && (
        <div className="text-label-sm text-on-surface-variant bg-white rounded-xl p-md border border-outline-variant/40 space-y-xs">
          <p className="font-semibold text-on-surface flex items-center gap-xs">
            <Icon name="lock" className="text-[16px]" />
            Tu privacidad
          </p>
          <p>
            Tu foto y los datos de tu rostro se guardan <strong>cifrados y protegidos</strong>, y se usan
            <strong> solo</strong> para confirmar que sos vos en tus exámenes. Ninguna decisión la toma una máquina:
            siempre la revisa una persona del equipo académico.
          </p>
        </div>
      )}
    </div>
  );
}
