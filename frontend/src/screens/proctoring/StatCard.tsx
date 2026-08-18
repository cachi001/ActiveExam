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

export type StatTono =
  | 'neutral'
  | 'success'
  | 'warning'
  | 'error'
  | 'primary'
  | 'info'
  | 'violet'
  | 'cyan'
  | 'rose';
export type StatSize = 'sm' | 'md';

/** Fondo en gradiente por tono. Paletas vivas tipo "dashboard moderno". `neutral`
 * usa slate-500/600 (gris medio legible) — el slate-900 anterior se sentía negro
 * pesado en el panel y no encaja con el resto de la paleta.
 *
 * `violet` / `cyan` / `rose` son gradientes vivos explícitos (hex) para las stat
 * cards del panel de estadísticas, donde hacía falta más color y variedad que la
 * que dan los tokens semánticos (evita dos cards con el mismo teal / un gris apagado). */
const TONO_BG: Record<StatTono, string> = {
  primary: 'bg-gradient-to-br from-[#2563eb] to-[#1e40af]',
  info: 'bg-gradient-to-br from-info-500 to-info-600',
  success: 'bg-gradient-to-br from-success-500 to-success-600',
  warning: 'bg-gradient-to-br from-warning-500 to-warning-600',
  error: 'bg-gradient-to-br from-error-500 to-error-600',
  neutral: 'bg-gradient-to-br from-surface-500 to-surface-600',
  violet: 'bg-gradient-to-br from-[#8b5cf6] to-[#6d28d9]',
  cyan: 'bg-gradient-to-br from-[#06b6d4] to-[#0e7490]',
  rose: 'bg-gradient-to-br from-[#f43f5e] to-[#be123c]',
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

/**
 * NeutralStatCard — variante SIN color fuerte (fondo blanco, borde sutil,
 * chip de ícono gris neutro). C-76 tarea 20.2: las stat cards de "Registro de
 * sesiones" (Auditoría/ResultadosExamenPanel usan el mismo criterio: sin
 * fondos de color — el color queda reservado a los badges chicos de riesgo
 * bajo/medio/alto, nunca a la card entera).
 */
export function NeutralStatCard({
  icon,
  label,
  value,
  sub,
}: {
  icon: string;
  label: string;
  value: ReactNode;
  sub?: ReactNode;
}) {
  return (
    <div className="relative overflow-hidden p-4 rounded-2xl shadow-lg h-full flex items-center gap-md bg-white border border-surface-200">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-surface-100 text-on-surface-variant">
        <Icon name={icon} className="text-[20px]" />
      </span>
      <div className="min-w-0">
        <p className="text-xs font-medium text-on-surface-variant">{label}</p>
        <p className="text-2xl font-bold tracking-tight text-on-surface leading-tight truncate">{value}</p>
        {sub && <p className="text-xs text-on-surface-variant mt-0.5 truncate">{sub}</p>}
      </div>
    </div>
  );
}

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
