/**
 * CaptureError — contenido del estado de error de cámara (presentacional).
 *
 * Renderiza el botón Cancelar discreto + el mensaje de "Sin acceso a la cámara".
 * El contenedor raíz del overlay (con `containerRef`) y el `createPortal` quedan
 * en BiometricCapture; este componente solo provee el contenido interno.
 *
 * Sin lógica propia: recibe el mensaje y el callback de cancelar por props.
 */

import { Icon } from '../components';

export interface CaptureErrorProps {
  errorMsg: string | null;
  onCancel: () => void;
}

export function CaptureError({ errorMsg, onCancel }: CaptureErrorProps) {
  return (
    <>
      {/* Cancelar discreto */}
      <button
        onClick={onCancel}
        className="absolute top-4 right-4 inline-flex items-center gap-1 text-sm text-neutral-500 hover:text-neutral-900 transition-colors px-3 py-1.5 rounded-full"
      >
        Cancelar <Icon name="close" className="text-[18px]" />
      </button>
      <div className="text-center space-y-md px-lg max-w-xs">
        <Icon name="videocam_off" className="text-error text-[48px]" fill />
        <p className="font-headline text-title-lg text-neutral-900">Sin acceso a la cámara</p>
        <p className="text-body-sm text-neutral-600">{errorMsg}</p>
        <p className="text-label-sm text-neutral-500">
          Habilitá el permiso de cámara en tu navegador y volvé a intentarlo.
        </p>
      </div>
    </>
  );
}
