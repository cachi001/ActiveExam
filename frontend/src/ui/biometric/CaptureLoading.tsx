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
  // Solo el spinner, sin texto (pedido del usuario): el óvalo aparece al cargar.
  // Capa propia `absolute inset-0` centrada → el spinner queda PERFECTAMENTE centrado
  // (vertical + horizontal) sin que el <video>/óvalo oculto desplace el layout.
  return (
    <div className="absolute inset-0 flex items-center justify-center">
      <Icon name="progress_activity" className="ae-spin text-primary text-[44px]" />
    </div>
  );
}
