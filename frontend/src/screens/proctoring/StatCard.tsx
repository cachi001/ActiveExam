/**
 * StatCard — Tarjeta de métrica con PRESENCIA DE COLOR.
 *
 * Layout horizontal: texto a la IZQUIERDA (label + valor grande + sub),
 * ícono cuadrado redondeado a la DERECHA en un nido translúcido. El fondo es
 * un gradiente del color del tono (texto blanco) y un círculo decorativo
 * arriba-derecha da profundidad sin ruido.
 *
 * Reutilizada en el resumen de la lista en vivo, el dashboard y el header del detalle.
 */
import type { ReactNode } from 'react';
import { Icon } from '../../ui/components';

export type StatTono = 'neutral' | 'success' | 'warning' | 'error' | 'primary' | 'info';
export type StatSize = 'sm' | 'md';

/** Fondo en gradiente por tono. Paletas vivas tipo "dashboard moderno". `neutral`
 * usa slate-500/600 (gris medio legible) — el slate-900 anterior se sentía negro
 * pesado en el panel y no encaja con el resto de la paleta. */
const TONO_BG: Record<StatTono, string> = {
  primary: 'bg-gradient-to-br from-primary-500 to-primary-700',
  info: 'bg-gradient-to-br from-info-500 to-info-600',
  success: 'bg-gradient-to-br from-success-500 to-success-600',
  warning: 'bg-gradient-to-br from-warning-500 to-warning-600',
  error: 'bg-gradient-to-br from-error-500 to-error-600',
  neutral: 'bg-gradient-to-br from-surface-500 to-surface-600',
};

/** Tamaños: `md` (Dashboard) prominente; `sm` (default) para sub-páginas de
 * gestión (cuando la stat es contexto, no protagonista).
 *
 * `iconWrap` usa width/height fijos + flex centrado para mantener el cuadrado
 * exacto — los íconos Material Symbols son texto y sin tamaño fijo el line-height
 * deforma el wrap (queda más alto que ancho).
 */
const SIZE: Record<StatSize, {
  padding: string;
  circulo: string;
  label: string;
  value: string;
  sub: string;
  iconWrap: string;
  iconSize: string;
}> = {
  md: {
    padding: 'p-5',
    circulo: 'w-24 h-24',
    label: 'text-sm font-medium',
    value: 'text-3xl font-bold tracking-tight',
    sub: 'text-sm',
    iconWrap: 'w-12 h-12 rounded-xl flex items-center justify-center',
    iconSize: 'text-[24px] leading-none',
  },
  sm: {
    padding: 'p-4',
    circulo: 'w-16 h-16',
    label: 'text-xs font-medium',
    value: 'text-2xl font-bold tracking-tight',
    sub: 'text-xs',
    iconWrap: 'w-8 h-8 rounded-xl flex items-center justify-center',
    iconSize: 'text-[16px] leading-none',
  },
};

export function StatCard({
  icon,
  label,
  value,
  sub,
  tono = 'neutral',
  size = 'sm',
}: {
  icon: string;
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tono?: StatTono;
  size?: StatSize;
}) {
  const s = SIZE[size];
  return (
    <div
      className={`relative overflow-hidden ${s.padding} rounded-2xl shadow-lg
        h-full flex flex-col justify-center
        transition-shadow hover:shadow-xl text-white ${TONO_BG[tono]}`}
    >
      {/* Círculo decorativo translúcido arriba-derecha */}
      <span
        className={`pointer-events-none absolute top-0 right-0 rounded-full bg-white/10 -translate-y-1/3 translate-x-1/3 ${s.circulo}`}
        aria-hidden
      />

      {/* Layout horizontal: texto a la IZQUIERDA, ícono a la DERECHA */}
      <div className="relative flex items-center justify-between gap-md">
        <div className="min-w-0">
          <p className={`${s.label} text-white/85`}>{label}</p>
          <p className={`${s.value} text-white leading-tight truncate mt-0.5`}>{value}</p>
          {sub && <p className={`${s.sub} text-white/85 mt-0.5 truncate`}>{sub}</p>}
        </div>
        <div className={`${s.iconWrap} bg-white/20 shrink-0`}>
          <Icon name={icon} className={s.iconSize} fill />
        </div>
      </div>
    </div>
  );
}

export default StatCard;
