/**
 * RequisitoBiometria — sección de referencia biométrica dentro del perfil.
 *
 * Extraída de StudentProfile (C-42) para mantener el contenedor ≤ 400 líneas.
 * Presentación pura: muestra el estado de vigencia, el CTA de captura o el
 * tool de dev para simular deriva del embedding.
 */
import { Button, Icon } from '../../../ui/components';
import { Term } from '../../../ui/Term';
import { RequisitoCard } from './RequisitoCard';
import { BiometricRenewalStatus } from '../../enrollment/BiometricRenewalStatus';
import type { ReferenciasBiometrica } from '../../../lib/types';

interface RequisitoBiometriaProps {
  biometria: ReferenciasBiometrica | null;
  biometriaOk: boolean;
  biometriaCaducada: boolean;
  biometriaRenovacionRequerida: boolean;
  consentimientoOk: boolean;
  devToolsEnabled: boolean;
  onCapturar: () => void;
  onRenovar: () => void;
  onSimularDeriva: () => void;
}

export function RequisitoBiometria({
  biometria,
  biometriaOk,
  biometriaCaducada,
  biometriaRenovacionRequerida,
  consentimientoOk,
  devToolsEnabled,
  onCapturar,
  onRenovar,
  onSimularDeriva,
}: RequisitoBiometriaProps) {
  const tone =
    !biometriaOk ? 'warning'
    : biometriaCaducada ? 'error'
    : biometria?.vigencia === 'por_vencer' ? 'warning'
    : biometriaRenovacionRequerida ? 'warning'
    : 'success';
  const label =
    !biometriaOk ? 'Pendiente'
    : biometriaCaducada ? 'Caducada'
    : biometria?.vigencia === 'por_vencer' ? 'Por vencer'
    : biometriaRenovacionRequerida ? 'Renovación requerida'
    : 'Vigente';

  const mostrarDevTool = devToolsEnabled && biometriaOk && !biometriaCaducada && !biometriaRenovacionRequerida;

  return (
    <RequisitoCard icon="face" title="Referencia biométrica" badge={{ tone, label }}>
      {biometriaOk && biometria ? (
        <BiometricRenewalStatus referencia={biometria} onRenovar={onRenovar} />
      ) : (
        <div className="space-y-md">
          <p className="text-label-sm text-on-surface-variant">
            La referencia biométrica se captura UNA sola vez en el perfil y es reutilizable en
            todos tus exámenes. Tiene vigencia de{' '}
            <strong>{biometria?.vigencia_meses ?? 24} meses</strong>.
          </p>

          <div className="text-label-sm text-on-surface-variant bg-surface-container-low rounded-xl p-sm border border-outline-variant/30">
            <span className="font-semibold">Privacidad:</span> La imagen y el <Term termKey="embedding" />
            biométrico son <strong>datos sensibles</strong>: cifrados at-rest, con finalidad acotada
            a la verificación de identidad. Se eliminan al egreso (salvo hold disciplinario).
          </div>

          <Button onClick={onCapturar} disabled={!consentimientoOk} icon="face" iconRight="arrow_forward">
            {!consentimientoOk ? 'Primero completá el consentimiento' : 'Capturar referencia biométrica'}
          </Button>
        </div>
      )}

      {mostrarDevTool && (
        <div className="flex items-center justify-between gap-md pt-sm border-t border-outline-variant/40">
          <div className="flex items-center gap-xs text-on-surface-variant">
            <Icon name="science" className="text-[16px]" />
            <span className="text-label-sm">Herramientas de desarrollo</span>
          </div>
          <Button variant="ghost" size="sm" onClick={onSimularDeriva} className="text-label-sm text-on-surface-variant">
            Simular deriva embedding
          </Button>
        </div>
      )}
    </RequisitoCard>
  );
}
