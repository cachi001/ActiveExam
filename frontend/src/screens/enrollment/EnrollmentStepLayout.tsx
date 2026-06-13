/**
 * EnrollmentStepLayout — encabezado reutilizable de los pasos de enrollment.
 *
 * Encapsula el patrón repetido en cada paso del flujo (consentimiento, foto,
 * biometría, renovación, DNI): botón "Volver al perfil" + título + subtítulo +
 * contador de paso opcional. Presentación pura.
 */
import type { ReactNode } from 'react';
import { BackButton, Icon } from '../../ui/components';

export interface WizardPaso {
  label: string;
  estado: 'completado' | 'actual' | 'pendiente';
}

interface EnrollmentStepLayoutProps {
  title: string;
  /** Subtítulo descriptivo del paso. */
  subtitle: ReactNode;
  /** Ancho máximo del contenedor (varía entre pasos). */
  maxWidth?: 'xl' | '2xl' | '3xl';
  /** Pasos del wizard a mostrar como stepper (verde = completado). */
  pasos?: WizardPaso[];
  onBack: () => void;
  children: ReactNode;
}

// c-66: max-width responsive desktop (lg:/xl:) para aprovechar el ancho en pantallas grandes.
const MAX_WIDTH: Record<NonNullable<EnrollmentStepLayoutProps['maxWidth']>, string> = {
  xl: 'max-w-xl lg:max-w-3xl xl:max-w-4xl',
  '2xl': 'max-w-2xl lg:max-w-4xl xl:max-w-5xl',
  '3xl': 'max-w-3xl lg:max-w-5xl xl:max-w-6xl',
};

export function EnrollmentStepLayout({
  title,
  subtitle,
  maxWidth = '2xl',
  pasos,
  onBack,
  children,
}: EnrollmentStepLayoutProps) {
  return (
    <div className={`${MAX_WIDTH[maxWidth]} mx-auto space-y-xl animate-in fade-in duration-300`}>
      <header>
        <BackButton onClick={onBack} label="Volver al perfil" className="mb-md" />
        <h1 className="font-headline text-headline-md text-on-surface tracking-tight">{title}</h1>
        <p className="text-body-md text-on-surface-variant mt-xs">{subtitle}</p>
      </header>

      {pasos && pasos.length > 0 && <WizardStepper pasos={pasos} />}

      {children}
    </div>
  );
}

/** Stepper horizontal del wizard de enrollment. Verde al completar, índigo el actual. */
function WizardStepper({ pasos }: { pasos: WizardPaso[] }) {
  return (
    <div className="flex">
      {pasos.map((p, i) => (
        <div key={p.label} className="flex-1 flex flex-col items-center relative min-w-0">
          {/* Línea conectora hacia el siguiente paso (centrada en el círculo) */}
          {i < pasos.length - 1 && (
            <div
              className={`absolute top-[18px] left-1/2 w-full h-0.5 ${
                p.estado === 'completado' ? 'bg-success' : 'bg-outline-variant'
              }`}
            />
          )}
          {/* Círculo (por encima de la línea) */}
          <div
            className={`relative z-10 w-9 h-9 rounded-full flex items-center justify-center text-label-sm font-semibold transition-colors ${
              p.estado === 'completado'
                ? 'bg-success text-white'
                : p.estado === 'actual'
                  ? 'bg-primary text-on-primary ring-4 ring-primary/15'
                  : 'bg-surface-container text-on-surface-variant'
            }`}
          >
            {p.estado === 'completado' ? <Icon name="check" className="text-[20px]" /> : i + 1}
          </div>
          <span
            className={`text-[11px] font-medium text-center leading-tight mt-base px-base truncate max-w-full ${
              p.estado === 'pendiente' ? 'text-on-surface-variant' : 'text-on-surface'
            }`}
          >
            {p.label}
          </span>
        </div>
      ))}
    </div>
  );
}
