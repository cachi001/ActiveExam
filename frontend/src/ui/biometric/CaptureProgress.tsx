/**
 * CaptureProgress — sección inferior de la captura biométrica (presentacional).
 *
 * Renderiza, en orden de prioridad:
 *  1. Hint de encuadre (lejos, oscuro, descentrado, etc.) si hay uno.
 *  2. Confirmación de paso completado durante el cooldown.
 *  3. Reto actual + sub-instrucción explicativa.
 *  4. Dots de progreso + contador.
 *
 * Sin lógica propia. La heurística de hints vive en `framingGuide.ts`; aquí
 * sólo elegimos qué mostrar según los props ya resueltos por el padre.
 */

import { Icon } from '../components';
import type { SequentialChallenge } from '../../vision/liveness';
import type { FramingHint } from './framingGuide';
import { FRAMING_COPY } from './framingGuide';

/**
 * Sub-instrucción explicativa que acompaña el título del reto. Le da contexto al
 * alumno para que la acción sea lenta y deliberada (parte de la mejora de UX).
 */
const SUB_INSTRUCCION_RETO: Record<SequentialChallenge, string> = {
  parpadear:
    'Cerrá los ojos y mantenelos cerrados, sin apurarte, hasta que la barra se complete. Recién ahí abrílos.',
  girar_cabeza:
    'Girá la cabeza despacio hacia el lado indicado, manteniendo el rostro dentro del óvalo. Quedate quieto así hasta que la barra se complete.',
  sonreír:
    'Sonreí despacio, marcando bien la sonrisa (mostrando los dientes está bien) y sostenela quieta hasta que la barra se complete.',
};

export interface CaptureProgressProps {
  enExito: boolean;
  fallbackManual: boolean;
  retoActualLabel: string;
  /** ID crudo del reto actual (para resolver la sub-instrucción explicativa). */
  retoActualId: SequentialChallenge | null;
  desafios: SequentialChallenge[];
  resueltos: string[];
  totalResueltos: number;
  totalDesafios: number;
  getLabel: (id: SequentialChallenge) => string;
  onResolverManual: (id: string) => void;
  /** True cuando el cooldown entre pasos está activo. */
  cooldownActivo: boolean;
  /** Label del reto recién resuelto (para mostrar en cooldown). null si no hay. */
  retoRecienResueltoLabel: string | null;
  /** Hint de encuadre vigente — gana prioridad si está presente y no estamos en cooldown/éxito. */
  framingHint: FramingHint | null;
  /** Pista de "no detectamos el gesto" cuando el reto no avanza durante varios segundos. */
  stallTip: string | null;
}

export function CaptureProgress({
  enExito,
  fallbackManual,
  retoActualLabel,
  retoActualId,
  desafios,
  resueltos,
  totalResueltos,
  totalDesafios,
  getLabel,
  onResolverManual,
  cooldownActivo,
  retoRecienResueltoLabel,
  framingHint,
  stallTip,
}: CaptureProgressProps) {
  // Prioridad: éxito > cooldown > hint de encuadre > reto activo.
  const mostrarHint = !enExito && !cooldownActivo && framingHint !== null;
  const subInstruccion =
    !enExito && !cooldownActivo && retoActualId ? SUB_INSTRUCCION_RETO[retoActualId] : null;

  return (
    <div className="mt-3 text-center space-y-3 w-full max-w-xs" role="status" aria-live="polite">
      {/* Confirmación visual del paso completado durante el cooldown */}
      {!enExito && cooldownActivo && retoRecienResueltoLabel && (
        <div className="flex flex-col items-center gap-1 animate-in fade-in duration-200">
          <span className="text-green-600 text-[32px]" aria-hidden>✓</span>
          <p className="font-headline text-lg font-bold text-green-600">¡Bien! {retoRecienResueltoLabel} listo</p>
        </div>
      )}

      {/* Hint de encuadre: tiene prioridad sobre el texto del reto para que el
          alumno arregle el setup antes de seguir intentando. */}
      {mostrarHint && framingHint && (
        <div className="flex flex-col items-center gap-1 animate-in fade-in duration-150">
          <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-amber-100 text-amber-700">
            <Icon name="lightbulb" className="text-[20px]" fill />
          </span>
          <p className="font-headline text-lg font-bold text-amber-700">
            {FRAMING_COPY[framingHint].titulo}
          </p>
          <p className="text-sm text-neutral-600 leading-relaxed">
            {FRAMING_COPY[framingHint].sub}
          </p>
        </div>
      )}

      {/* Texto del paso actual + sub-instrucción explicativa.
          Sólo se ve si: hay éxito (mensaje final) o si no hay cooldown ni hint. */}
      {(enExito || (!cooldownActivo && !mostrarHint)) && (
        <>
          <p
            className={`font-headline text-2xl font-bold ${
              enExito ? 'text-green-600' : 'text-neutral-900'
            }`}
          >
            {enExito ? 'Verificación completada' : retoActualLabel}
          </p>
          {!enExito && subInstruccion && (
            <p className="text-sm text-neutral-600 leading-relaxed">{subInstruccion}</p>
          )}
          {/* Pista de gesto estancado — sólo si no hay hint de encuadre y el alumno
              lleva varios segundos sin progresar. La idea es romper el silencio. */}
          {!enExito && stallTip && (
            <div className="mt-2 inline-flex items-start gap-2 text-left bg-amber-50 border border-amber-300 text-amber-900 rounded-xl px-3 py-2">
              <Icon name="tips_and_updates" className="text-[18px] text-amber-700 shrink-0 mt-px" fill />
              <p className="text-sm leading-relaxed">{stallTip}</p>
            </div>
          )}
        </>
      )}

      {/* Subtítulo genérico de encuadre cuando arrancamos sin reto identificado. */}
      {!enExito && !fallbackManual && !cooldownActivo && !mostrarHint && !subInstruccion && (
        <p className="text-sm text-neutral-500">
          Buscá tu rostro en el óvalo y seguí las indicaciones.
        </p>
      )}

      {/* Dots de progreso (un punto por paso; lleno = completado). C-67: se quitó el
          contador "N / total" — los dots ya comunican el avance y quedaba cargado. */}
      {!enExito && totalDesafios > 0 && (
        <div className="flex items-center justify-center gap-2 pt-1" role="status" aria-label={`${totalResueltos} de ${totalDesafios} pasos`}>
          {desafios.map((id) => (
            <span
              key={id}
              className={`text-lg transition-colors duration-300 ${
                resueltos.includes(id) ? 'text-green-600' : 'text-neutral-300'
              }`}
              aria-hidden
            >
              {resueltos.includes(id) ? '●' : '○'}
            </span>
          ))}
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
