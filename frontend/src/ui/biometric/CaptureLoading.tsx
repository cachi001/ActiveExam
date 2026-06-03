/**
 * CaptureLoading — estado de carga LIMPIO de la captura biométrica (presentacional).
 *
 * Bug 1: solo un spinner centrado, sin óvalo, sin frame de cámara, sin jerga
 * técnica. Se muestra mientras !listoParaMostrar && !motorError. El <video> sigue
 * montado por el padre (opacity-0) para que el stream se inicialice; este componente
 * no lo renderiza.
 *
 * Sin lógica propia: recibe todo por props desde BiometricCapture.
 */

import { Icon } from '../components';

export function CaptureLoading() {
  return (
    <div className="flex flex-col items-center justify-center gap-3">
      <Icon name="progress_activity" className="ae-spin text-primary text-[40px]" />
      <span className="text-sm text-neutral-500">Preparando cámara…</span>
    </div>
  );
}
