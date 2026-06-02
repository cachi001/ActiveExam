/**
 * PerfilBannerEstado — banners contextuales del estado del perfil del alumno.
 *
 * Renderiza condicionalmente uno de tres banners mutuamente excluyentes:
 *   1. biometriaCaducada → banner rojo (prioridad máxima)
 *   2. biometriaRenovacionRequerida && !caducada → banner amarillo
 *   3. perfilCompleto && !caducada && !renovacion → banner verde
 *   4. ninguna condición → null (sin banner)
 *
 * Presentación pura: recibe callbacks; no accede al store ni llama APIs.
 *
 * Spec: profile-banner-estado (C-42)
 */
import { Button, Icon } from '../../../ui/components';
import { Term } from '../../../ui/Term';

interface PerfilBannerEstadoProps {
  perfilCompleto: boolean;
  biometriaCaducada: boolean;
  biometriaRenovacionRequerida: boolean;
  viaAlternativa: boolean;
  onIrAExamenes: () => void;
  onRenovarBiometria: () => void;
}

export function PerfilBannerEstado({
  perfilCompleto,
  biometriaCaducada,
  biometriaRenovacionRequerida,
  viaAlternativa,
  onIrAExamenes,
  onRenovarBiometria,
}: PerfilBannerEstadoProps) {
  /* 1. Banner rojo — biometría caducada (prioridad máxima) */
  if (biometriaCaducada) {
    return (
      <div className="flex items-start gap-md bg-error-container border border-error/30 rounded-xl p-md">
        <Icon name="cancel" className="text-error text-[22px] shrink-0 mt-base" fill />
        <div className="flex-1">
          <p className="text-label-md font-semibold text-on-surface">
            Referencia biométrica caducada — no podés rendir
          </p>
          <p className="text-label-sm text-on-surface-variant mt-base">
            Tu referencia biométrica venció. Renovála para volver a poder rendir tus exámenes.
          </p>
        </div>
        <Button variant="danger" size="sm" onClick={onRenovarBiometria} className="shrink-0 text-label-sm" icon="refresh">
          Renovar
        </Button>
      </div>
    );
  }

  /* 2. Banner amarillo — renovación requerida (sin caducar) */
  if (biometriaRenovacionRequerida) {
    return (
      <div className="flex items-start gap-md bg-warning-container border border-warning/30 rounded-xl p-md">
        <Icon name="refresh" className="text-warning text-[22px] shrink-0 mt-base" />
        <div className="flex-1">
          <p className="text-label-md font-semibold text-on-surface">
            Renovación biométrica requerida
          </p>
          <p className="text-label-sm text-on-surface-variant mt-base">
            Las verificaciones silenciosas detectaron deriva del <Term termKey="embedding" />. Se requiere renovar la referencia.
            Las rendiciones en curso no se ven afectadas (decisión disciplinaria siempre humana — <Term termKey="l2_5" />).
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={onRenovarBiometria} className="shrink-0 text-label-sm" icon="refresh">
          Renovar
        </Button>
      </div>
    );
  }

  /* 3. Banner verde — perfil completo y sin alertas */
  if (perfilCompleto) {
    return (
      <div className="flex items-center gap-md bg-success-container border border-success/30 rounded-xl p-md">
        <Icon name="verified" className="text-success text-[24px] shrink-0" fill />
        <div className="flex-1">
          <p className="text-label-md font-semibold text-on-surface">
            Perfil completo — podés rendir tus exámenes
          </p>
          <p className="text-label-sm text-on-surface-variant mt-base">
            {viaAlternativa
              ? 'Elegiste la vía alternativa. Un proctor supervisará tu verificación de identidad.'
              : 'Consentimiento y referencia biométrica vigentes.'}
          </p>
        </div>
        <Button
          variant="secondary"
          onClick={onIrAExamenes}
          className="shrink-0 h-9 px-md text-label-sm"
        >
          Mis exámenes
        </Button>
      </div>
    );
  }

  /* 4. Sin banner — perfil incompleto sin alertas críticas */
  return null;
}
