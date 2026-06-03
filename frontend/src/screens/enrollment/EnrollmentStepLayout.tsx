/**
 * EnrollmentStepLayout — encabezado reutilizable de los pasos de enrollment.
 *
 * Encapsula el patrón repetido en cada paso del flujo (consentimiento, foto,
 * biometría, renovación, DNI): botón "Volver al perfil" + título + subtítulo +
 * contador de paso opcional. Presentación pura.
 */
import type { ReactNode } from 'react';
import { Icon } from '../../ui/components';

interface EnrollmentStepLayoutProps {
  title: string;
  /** Subtítulo descriptivo del paso. */
  subtitle: ReactNode;
  /** Ancho máximo del contenedor (varía entre pasos). */
  maxWidth?: 'xl' | '2xl' | '3xl';
  onBack: () => void;
  children: ReactNode;
}

const MAX_WIDTH: Record<NonNullable<EnrollmentStepLayoutProps['maxWidth']>, string> = {
  xl: 'max-w-xl',
  '2xl': 'max-w-2xl',
  '3xl': 'max-w-3xl',
};

export function EnrollmentStepLayout({
  title,
  subtitle,
  maxWidth = '2xl',
  onBack,
  children,
}: EnrollmentStepLayoutProps) {
  return (
    <div className={`${MAX_WIDTH[maxWidth]} mx-auto space-y-xl animate-in fade-in duration-300`}>
      <header>
        <button
          onClick={onBack}
          className="inline-flex items-center gap-xs text-label-md text-on-surface-variant hover:text-primary transition-colors mb-md"
        >
          <Icon name="arrow_back" className="text-[18px]" />
          Volver al perfil
        </button>
        <h1 className="font-headline text-headline-md text-on-surface tracking-tight">{title}</h1>
        <p className="text-body-md text-on-surface-variant mt-xs">{subtitle}</p>
      </header>
      {children}
    </div>
  );
}
