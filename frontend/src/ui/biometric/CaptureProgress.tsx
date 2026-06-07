/**
 * CaptureProgress — sección inferior de la captura biométrica (presentacional).
 *
 * Renderiza: texto del paso actual (éxito → reto actual), subtítulo de encuadre,
 * dots de progreso + contador, y la grilla de botones de retos del fallback manual.
 *
 * Sin lógica propia: recibe estado y callbacks por props desde BiometricCapture.
 * El cálculo de labels (getLabelForChallenge) vive en el padre y se reenvía como
 * `retoActualLabel` (paso actual) y `getLabel` (grilla manual).
 *
 * C-54: agrega props `cooldownActivo` y `retoRecienResueltoLabel`
 * para mostrar confirmación visual de paso completado.
 * C-58 D4: se eliminó `turnDirection` — la flecha direccional era chrome redundante.
 */

import { Icon } from '../components';
import type { SequentialChallenge } from '../../vision/liveness';

export interface CaptureProgressProps {
  enExito: boolean;
  fallbackManual: boolean;
  retoActualLabel: string;
  desafios: SequentialChallenge[];
  resueltos: string[];
  totalResueltos: number;
  totalDesafios: number;
  /** Resuelve el label visible de un reto (delegado al padre). */
  getLabel: (id: SequentialChallenge) => string;
  /** Callback del fallback manual al tocar un reto. */
  onResolverManual: (id: string) => void;
  /** C-54 (Task 8.1): true cuando el cooldown de 350ms entre pasos está activo. */
  cooldownActivo: boolean;
  /** C-54 (Task 8.2): label del reto recién resuelto (para mostrar en cooldown). null si no hay. */
  retoRecienResueltoLabel: string | null;
}

export function CaptureProgress({
  enExito,
  fallbackManual,
  retoActualLabel,
  desafios,
  resueltos,
  totalResueltos,
  totalDesafios,
  getLabel,
  onResolverManual,
  cooldownActivo,
  retoRecienResueltoLabel,
}: CaptureProgressProps) {
  return (
    // Sección inferior — paso actual + progreso. Oculta durante la carga.
    <div className="mt-8 text-center space-y-3 w-full max-w-xs">

      {/* C-54 Task 8.4: Confirmación visual del paso completado durante el cooldown */}
      {!enExito && cooldownActivo && retoRecienResueltoLabel && (
        <div className="flex flex-col items-center gap-1 animate-in fade-in duration-200">
          <span className="text-green-600 text-[32px]">✓</span>
          <p className="font-headline text-lg font-bold text-green-600">
            {retoActualLabel}
          </p>
          <p className="text-sm text-neutral-500">{retoRecienResueltoLabel}</p>
        </div>
      )}

      {/* Texto del paso actual: éxito → reto actual. */}
      {/* Durante cooldown se muestra arriba; aquí solo mostramos si NO hay cooldown o si es éxito */}
      {(enExito || !cooldownActivo) && (
        <p className={`font-headline text-2xl font-bold ${
          enExito ? 'text-green-600' : 'text-neutral-900'
        }`}>
          {enExito ? 'Verificación completada' : retoActualLabel}
        </p>
      )}

      {/* Subtítulo de encuadre mientras el motor está listo pero aún sin completar */}
      {!enExito && !fallbackManual && !cooldownActivo && (
        <p className="text-sm text-neutral-500">Buscá tu rostro en el óvalo y seguí las indicaciones.</p>
      )}

      {/* Dots de progreso + contador */}
      {!enExito && totalDesafios > 0 && (
        <div className="flex items-center justify-center gap-2">
          {desafios.map((id) => (
            <span
              key={id}
              className={`text-lg transition-colors duration-300 ${resueltos.includes(id) ? 'text-green-600' : 'text-neutral-300'}`}
            >
              {resueltos.includes(id) ? '●' : '○'}
            </span>
          ))}
          <span className="text-sm text-neutral-500 ml-1">
            {totalResueltos} / {totalDesafios}
          </span>
        </div>
      )}

      {/* Grilla de botones de retos en fallback manual */}
      {!enExito && fallbackManual && totalDesafios > 0 && (
        <div className="grid grid-cols-1 gap-2 mt-2">
          {desafios.map((id) => {
            const hecho = resueltos.includes(id);
            return (
              <button
                key={id}
                disabled={hecho}
                onClick={() => onResolverManual(id)}
                className={`flex items-center gap-2 p-2 rounded-xl border transition-all ${
                  hecho
                    ? 'bg-green-50 border-green-300 text-green-700 cursor-default'
                    : 'bg-neutral-50 border-neutral-300 text-neutral-800 hover:bg-neutral-100 cursor-pointer'
                }`}
              >
                <Icon name={hecho ? 'check_circle' : 'gesture'} fill={hecho} />
                <span className="text-sm font-semibold">{getLabel(id)}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
