import { Icon, Button } from '../../ui/components';
import { CameraSnapshotCapture } from '../../ui/CameraSnapshotCapture';
import type { EstadoEnrollment } from '../../lib/types';

interface Props {
  fotoConfirmando: string | null;
  setFotoConfirmando: (v: string | null) => void;
  fotoError: string | null;
  enrollment: EstadoEnrollment | null;
  onAvanzar: () => void;
  onCapture: (dataUrl: string) => void;
  onCancel: () => void;
}

export function EnrollmentFotoPerfilStep({
  fotoConfirmando,
  setFotoConfirmando,
  fotoError,
  enrollment,
  onAvanzar,
  onCapture,
  onCancel,
}: Props) {
  if (fotoConfirmando) {
    return (
      <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant/70 shadow-card p-lg flex flex-col items-center text-center gap-md">
        <img src={fotoConfirmando} alt="Tu foto de perfil" className="w-36 h-36 rounded-full object-cover shadow-sm" />
        <div className="space-y-base">
          <p className="inline-flex items-center gap-xs font-headline text-title-lg text-on-surface">
            <Icon name="check_circle" className="text-success text-[24px]" fill /> ¡Foto lista!
          </p>
          <p className="text-body-md text-on-surface-variant max-w-md mx-auto">
            Esta es la foto que se va a mostrar en tu perfil. Si te gusta, continuá; si no, cambiala.
          </p>
        </div>
        <div className="flex flex-col sm:flex-row items-center gap-sm w-full sm:w-auto">
          <Button variant="outline" icon="refresh" onClick={() => setFotoConfirmando(null)} className="w-full sm:w-auto">
            Cambiar foto
          </Button>
          <Button onClick={() => { setFotoConfirmando(null); onAvanzar(); }} className="w-full sm:w-auto">
            {enrollment?.biometria?.captura_completada ? 'Guardar foto' : 'Continuar'}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="text-label-sm text-on-surface-variant bg-white rounded-xl p-sm border border-outline-variant/40">
        <span className="font-semibold">Privacidad:</span> Tu foto se usa solo como tu imagen en la plataforma.
      </div>

      {fotoError && (
        <div className="flex items-start gap-sm bg-error-container border border-error/30 rounded-xl p-md">
          <Icon name="error" className="text-error text-[18px] shrink-0 mt-px" />
          <div className="text-label-sm text-on-surface">
            <p className="font-semibold text-error">Error al guardar la foto</p>
            <p className="text-on-surface-variant mt-xs">{fotoError}</p>
            <p className="text-on-surface-variant mt-xs">
              Intentá capturar la foto nuevamente. Si el problema persiste, contactá al soporte.
            </p>
          </div>
        </div>
      )}

      <CameraSnapshotCapture
        shape="oval"
        requerido
        instruction="Posicioná tu cara dentro del óvalo y presioná Capturar"
        contextLabel="Foto de perfil"
        onCapture={onCapture}
        onCancel={onCancel}
      />
    </>
  );
}
