/**
 * EnrollmentStepLayout — encabezado reutilizable de los pasos de enrollment.
 *
 * Encapsula el patrón repetido en cada paso del flujo (consentimiento, foto,
 * biometría, renovación, DNI): botón "Volver al perfil" + título + subtítulo +
 * contador de paso opcional. Presentación pura.
 */
import type { ReactNode } from 'react';
import { BackButton } from '../../ui/components';

interface EnrollmentStepLayoutProps {
  title: string;
  /** Subtítulo descriptivo del paso. */
  subtitle: ReactNode;
  /** Ancho máximo del contenedor (varía entre pasos). */
  maxWidth?: 'xl' | '2xl' | '3xl';
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
      {children}
    </div>
  );
}
