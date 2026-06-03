/**
 * CaptureProgress — sección inferior de la captura biométrica (presentacional).
 *
 * Renderiza: texto del paso actual (éxito → reto actual), subtítulo de encuadre,
 * dots de progreso + contador, y la grilla de botones de retos del fallback manual.
 *
 * Sin lógica propia: recibe estado y callbacks por props desde BiometricCapture.
 * El cálculo de labels (getLabelForChallenge) vive en el padre y se reenvía como
 * `retoActualLabel` (paso actual) y `getLabel` (grilla manual).
 */

import { Icon } from '../components';
import type { ActiveChallenge } from '../../vision/liveness';

export interface CaptureProgressProps {
  enExito: boolean;
  fallbackManual: boolean;
  retoActualLabel: string;
  desafios: ActiveChallenge[];
  resueltos: string[];
  totalResueltos: number;
  totalDesafios: number;
  /** Resuelve el label visible de un reto (delegado al padre). */
  getLabel: (id: ActiveChallenge) => string;
  /** Callback del fallback manual al tocar un reto. */
  onResolverManual: (id: string) => void;
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
}: CaptureProgressProps) {
  return (
    // Sección inferior — paso actual + progreso. Oculta durante la carga.
    <div className="mt-8 text-center space-y-3 w-full max-w-xs">
      {/* Texto del paso actual: éxito → reto actual. */}
      <p className={`font-headline text-2xl font-bold ${
        enExito ? 'text-green-600' : 'text-neutral-900'
      }`}>
        {enExito ? 'Verificación completada' : retoActualLabel}
      </p>

      {/* Subtítulo de encuadre mientras el motor está listo pero aún sin completar */}
      {!enExito && !fallbackManual && (
        <p className="text-sm text-neutral-500">Buscá tu rostro en el óvalo y seguí las indicaciones.</p>
      )}

      {/* Dots de progreso + contador */}
      {!enExito && totalDesafios > 0 && (
        <div className="flex items-center justify-center gap-2">
          {desafios.map((id) => (
            <span
              key={id}
              className={`text-lg ${resueltos.includes(id) ? 'text-green-600' : 'text-neutral-300'}`}
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
