/**
 * StatCard — Tarjeta de métrica con PRESENCIA DE COLOR.
 *
 * Fondo de color en gradiente + texto blanco + ícono en un nido translúcido
 * (estética formal inspirada en el sistema de reservas). El color comunica el
 * estado de la métrica de un vistazo; nada de cards blancas/grises apagadas.
 *
 * Reutilizada en el resumen de la lista en vivo, el dashboard y el header del detalle.
 */
import type { ReactNode } from 'react';
import { Icon } from '../../ui/components';

export type StatTono = 'neutral' | 'success' | 'warning' | 'error' | 'primary' | 'info';

/** Fondo en gradiente por tono (oscuro→más oscuro, para que el blanco se lea siempre). */
const TONO_BG: Record<StatTono, string> = {
  primary: 'bg-gradient-to-br from-primary to-primary-700',
  info: 'bg-gradient-to-br from-info-500 to-info-600',
  success: 'bg-gradient-to-br from-success-500 to-success-600',
  warning: 'bg-gradient-to-br from-warning-500 to-warning-600',
  error: 'bg-gradient-to-br from-error-500 to-error-600',
  neutral: 'bg-gradient-to-br from-tertiary to-tertiary-container',
};

export function StatCard({
  icon,
  label,
  value,
  sub,
  tono = 'neutral',
}: {
  icon: string;
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tono?: StatTono;
}) {
  return (
    <div
      className={`relative overflow-hidden flex items-center gap-md p-md rounded-2xl
        shadow-card text-white ${TONO_BG[tono]}`}
    >
      {/* Círculo decorativo translúcido (sutil, da profundidad sin ruido) */}
      <span className="pointer-events-none absolute -top-6 -right-6 w-24 h-24 rounded-full bg-white/10" aria-hidden />

      <div className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 bg-white/20">
        <Icon name={icon} className="text-[24px]" fill />
      </div>
      <div className="min-w-0 relative">
        <p className="text-label-sm uppercase tracking-wide text-white/80">{label}</p>
        <p className="font-headline text-headline-md font-bold leading-tight truncate">{value}</p>
        {sub && <p className="text-label-sm text-white/70 mt-px">{sub}</p>}
      </div>
    </div>
  );
}

export default StatCard;
