/**
 * Paso opcional de escaneo de DNI en el enrollment del perfil (C-22, C-38).
 *
 * Captura FRENTE + DORSO reutilizando el componente compartido CameraSnapshotCapture
 * (marco escáner rectangular ID-1, cámara trasera en móvil). Opcional: su ausencia
 * NO bloquea el perfil completo. No hay análisis client-side: la verificación del
 * documento se realiza server-side (cliente = sensor no confiable, RN-GLB-01).
 *
 * DATO SENSIBLE (Ley 25.326):
 * Server-side: cifrado AES-256-GCM, finalidad acotada a verificación de identidad,
 * eliminado al egreso del estudiante, holds legales difieren la eliminación.
 *
 * Spec: optional-dni-scan (C-22) + dni-scanner-dual-side (C-38)
 */
import { useState } from 'react';
import { Icon, Button, Card } from '../../ui/components';
import { CameraSnapshotCapture } from '../../ui/CameraSnapshotCapture';
import { api, ENABLE_DNI_SCAN } from '../../lib/api';
import type { EscaneDNI } from '../../lib/types';

interface Props {
  escanActual: EscaneDNI | null;
  onEscaneado: (escan: EscaneDNI) => void;
  onOmitir: () => void;
}

type Fase = 'inicio' | 'completado';

/** Aspecto de la tarjeta ID-1 (DNI argentino): 85.6 × 54 mm. */
const DNI_ASPECT = 85.6 / 54;

export function EnrollmentDniStep({ escanActual, onEscaneado, onOmitir }: Props) {
  const [fase, setFase] = useState<Fase>(escanActual?.captura_completada ? 'completado' : 'inicio');
  const [escanGuardado, setEscanGuardado] = useState<EscaneDNI | null>(escanActual);
  // Lado activo de la captura ('frente' | 'dorso'); null = overlay cerrado.
  const [lado, setLado] = useState<'frente' | 'dorso' | null>(null);
  const [imagenFrente, setImagenFrente] = useState<string | null>(null);

  const handleFrenteCapturado = (dataUrl: string) => {
    setImagenFrente(dataUrl);
    setLado('dorso'); // key={lado} re-monta CameraSnapshotCapture para el dorso
  };

  const handleDorsoCapturado = async (dataUrl: string) => {
    setLado(null);
    const escan = await api.guardarEscaneDNI(imagenFrente ?? '', dataUrl);
    setEscanGuardado(escan);
    setFase('completado');
    onEscaneado(escan);
  };

  // Cierra el overlay sin perder el frente ya capturado.
  const handleCancelarCaptura = () => setLado(null);

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
            Escaneo de DNI (frente y dorso) · No bloquea el perfil completo
          </p>
        </div>
      </div>

      {/* Overlay inmersivo de captura (frente o dorso). key={lado} fuerza el re-montaje. */}
      {lado !== null && (
        <CameraSnapshotCapture
          key={lado}
          shape="rect"
          scannerCorners
          aspectRatio={DNI_ASPECT}
          facingMode="environment"
          jpegQuality={0.9}
          contextLabel={lado === 'frente' ? 'Paso 1 de 2 — Frente del DNI' : 'Paso 2 de 2 — Dorso del DNI'}
          instruction={
            lado === 'frente'
              ? 'Colocá el FRENTE del DNI dentro del marco y que se lea con claridad.'
              : 'Ahora dá vuelta el DNI y colocá el DORSO dentro del marco.'
          }
          onCapture={lado === 'frente' ? handleFrenteCapturado : handleDorsoCapturado}
          onCancel={handleCancelarCaptura}
        />
      )}

      {!ENABLE_DNI_SCAN ? (
        /* Flag explícitamente desactivado (VITE_ENABLE_DNI_SCAN=0) */
        <Card className="border-outline-variant/30">
          <div className="flex items-start gap-sm">
            <Icon name="upcoming" className="text-on-surface-variant text-[22px] shrink-0 mt-px" />
            <div className="space-y-xs">
              <p className="text-label-md font-semibold text-on-surface">Verificación documental — Desactivada</p>
              <p className="text-label-sm text-on-surface-variant">
                El escaneo del DNI está desactivado en esta instancia. Este paso es
                <strong> completamente opcional</strong> y su ausencia no afecta tu habilitación.
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
        <Card className="space-y-lg">
          {/* Completado */}
          {fase === 'completado' && escanGuardado && (
            <div className="space-y-md">
              <div className="flex items-center gap-sm text-success">
                <Icon name="verified" className="text-[22px]" fill />
                <p className="text-label-md font-semibold text-on-surface">DNI registrado (frente y dorso)</p>
              </div>
              <p className="text-label-sm text-on-surface-variant">
                Capturado el {formatearFecha(escanGuardado.fecha_captura)}. Se guarda cifrado y protegido,
                y se usa solo para verificar tu identidad.
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
                Podés escanear el <strong>frente y el dorso</strong> de tu DNI para reforzar la
                verificación de identidad. Este paso es <strong>opcional</strong> — podés omitirlo
                y completar el perfil igual.
              </p>

              {/* Nota legal prominente */}
              <div className="flex items-start gap-sm bg-white rounded-xl p-md border border-outline-variant/40">
                <Icon name="privacy_tip" className="text-on-surface-variant text-[18px] shrink-0 mt-px" />
                <p className="text-label-sm text-on-surface-variant">
                  <strong>Protegido:</strong> el frente y el dorso de tu DNI se guardan cifrados y
                  se usan solo para verificar tu identidad.
                </p>
              </div>

              {imagenFrente && (
                <p className="text-label-sm text-success inline-flex items-center gap-base">
                  <Icon name="check_circle" className="text-[16px]" fill /> Frente capturado — falta el dorso.
                </p>
              )}

              <div className="flex gap-sm flex-col sm:flex-row">
                <Button variant="secondary" icon="badge" onClick={() => setLado(imagenFrente ? 'dorso' : 'frente')}>
                  {imagenFrente ? 'Capturar dorso' : 'Escanear DNI'}
                </Button>
                <Button variant="ghost" onClick={onOmitir} icon="skip_next">
                  Omitir este paso
                </Button>
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
