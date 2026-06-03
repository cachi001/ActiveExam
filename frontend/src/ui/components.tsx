// Primitivas de UI del design system ActiveExam (estilo "warm minimalism" de Stitch).
import { forwardRef } from 'react';
import type { ReactNode, ButtonHTMLAttributes } from 'react';
import type { Severidad } from '../lib/types';
import { SEVERIDAD_LABEL } from '../lib/api';

export function Icon({ name, className = '', fill = false, style }: {
  name: string; className?: string; fill?: boolean; style?: React.CSSProperties;
}) {
  return (
    <span className={`material-symbols-outlined ${fill ? 'ms-fill' : ''} ${className}`} style={style} aria-hidden>
      {name}
    </span>
  );
}

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline';
const VARIANTS: Record<Variant, string> = {
  primary: 'bg-primary text-on-primary hover:bg-primary-container shadow-sm hover:shadow-md',
  secondary: 'bg-primary-container text-on-primary hover:brightness-110 shadow-sm',
  ghost: 'bg-transparent text-on-surface-variant hover:bg-surface-container',
  outline: 'bg-surface-container-lowest text-on-surface border border-outline-variant hover:bg-surface-container',
  danger: 'bg-error text-on-error hover:brightness-110 shadow-sm',
};

type Size = 'sm' | 'md' | 'lg';
const SIZE_CLASSES: Record<Size, string> = {
  sm: 'h-9 px-md',
  md: 'h-12 px-lg',
  lg: 'h-14 px-xl',
};

export const Button = forwardRef<HTMLButtonElement, {
  variant?: Variant; size?: Size; icon?: string; iconRight?: string; children?: ReactNode;
} & ButtonHTMLAttributes<HTMLButtonElement>>(function Button(
  { variant = 'primary', size = 'md', icon, iconRight, children, className = '', ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      {...rest}
      className={`inline-flex items-center justify-center gap-xs ${SIZE_CLASSES[size]} rounded-xl font-label-md text-label-md
        transition-all duration-200 active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none ${VARIANTS[variant]} ${className}`}
    >
      {icon && <Icon name={icon} className="text-[20px]" />}
      {children}
      {iconRight && <Icon name={iconRight} className="text-[20px]" />}
    </button>
  );
});

export function Card({ children, className = '', padded = true }: { children: ReactNode; className?: string; padded?: boolean }) {
  return (
    <div className={`bg-surface-container-lowest rounded-xl border border-outline-variant/40 shadow-card ${padded ? 'p-lg' : ''} ${className}`}>
      {children}
    </div>
  );
}

export function SectionTitle({ children, sub, action }: { children: ReactNode; sub?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-md mb-md">
      <div>
        <h2 className="font-headline text-title-lg text-on-surface tracking-tight">{children}</h2>
        {sub && <p className="text-label-sm text-on-surface-variant mt-base">{sub}</p>}
      </div>
      {action}
    </div>
  );
}

const SEV_STYLES: Record<Severidad, string> = {
  baseline: 'bg-surface-container-high text-on-surface-variant',
  baja: 'bg-success-container text-success',
  media: 'bg-warning-container text-warning',
  alta: 'bg-error-container text-on-error-container',
  critica: 'bg-error text-on-error',
};

export function SeverityBadge({ severidad }: { severidad: Severidad }) {
  return (
    <span className={`inline-flex items-center gap-base px-sm py-base rounded-full text-label-sm font-semibold ${SEV_STYLES[severidad]}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-70" />
      {SEVERIDAD_LABEL[severidad]}
    </span>
  );
}

export function Badge({ children, tone = 'neutral', dot = false }: {
  children: ReactNode; tone?: 'neutral' | 'primary' | 'success' | 'warning' | 'error'; dot?: boolean;
}) {
  const tones = {
    neutral: 'bg-surface-container-high text-on-surface-variant',
    primary: 'bg-primary-fixed text-on-primary-fixed-variant',
    success: 'bg-success-container text-success',
    warning: 'bg-warning-container text-warning',
    error: 'bg-error-container text-on-error-container',
  } as const;
  return (
    <span className={`inline-flex items-center gap-base px-sm py-base rounded-full text-label-sm font-semibold ${tones[tone]}`}>
      {dot && <span className="w-1.5 h-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}

export function Stat({ label, value, sub, icon }: { label: string; value: ReactNode; sub?: ReactNode; icon?: string }) {
  return (
    <Card className="flex items-start gap-md">
      {icon && (
        <div className="w-11 h-11 rounded-xl bg-primary-fixed text-primary flex items-center justify-center shrink-0">
          <Icon name={icon} />
        </div>
      )}
      <div className="min-w-0">
        <p className="text-label-sm text-on-surface-variant uppercase tracking-wide">{label}</p>
        <p className="font-headline text-headline-md text-on-surface truncate">{value}</p>
        {sub && <p className="text-label-sm text-on-surface-variant mt-base">{sub}</p>}
      </div>
    </Card>
  );
}

export function Avatar({ src, alt, size = 44 }: { src: string; alt: string; size?: number }) {
  return (
    <img src={src} alt={alt} width={size} height={size}
      className="rounded-xl object-cover bg-surface-container" style={{ width: size, height: size }} />
  );
}

export function ProgressBar({ value, tone = 'primary' }: { value: number; tone?: 'primary' | 'error' | 'warning' | 'success' }) {
  const colors = { primary: 'bg-primary-container', error: 'bg-error', warning: 'bg-warning', success: 'bg-success' };
  return (
    <div className="w-full h-2 rounded-full bg-surface-container-high overflow-hidden">
      <div className={`h-full rounded-full transition-all duration-500 ${colors[tone]}`} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
    </div>
  );
}

export function ScoreChip({ score, umbral }: { score: number; umbral: number }) {
  const tone = score >= umbral ? 'bg-error text-on-error' : score >= umbral * 0.6 ? 'bg-warning-container text-warning' : 'bg-success-container text-success';
  return <span className={`px-sm py-base rounded-full text-label-sm font-bold ${tone}`}>Riesgo {score}%</span>;
}

// ── Primitivas de formulario ──────────────────────────────────────────────────

interface FormFieldProps {
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
  className?: string;
}

export function FormField({ label, hint, error, children, className = '' }: FormFieldProps) {
  return (
    <div className={`space-y-base ${className}`}>
      <label className="text-label-sm uppercase tracking-wide text-on-surface-variant font-semibold">
        {label}
      </label>
      {children}
      {hint && !error && <p className="text-label-sm text-on-surface-variant">{hint}</p>}
      {error && <p className="text-label-sm text-error">{error}</p>}
    </div>
  );
}

interface RangeInputProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  unit?: string;
  hint?: string;
  onChange: (v: number) => void;
}

export function RangeInput({ label, value, min, max, step = 1, unit = '', hint, onChange }: RangeInputProps) {
  return (
    <FormField label={`${label}: ${value}${unit ? ' ' + unit : ''}`} hint={hint}>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-primary"
      />
    </FormField>
  );
}
