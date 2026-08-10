import { BackButton } from '../../../ui/components';
import { HelpButton } from '../../../ui/HelpButton';
import { ENABLE_DNI_SCAN } from '../../../lib/api';
import { PerfilHeaderCard } from './PerfilHeaderCard';
import { PerfilBannerEstado } from './PerfilBannerEstado';
import { RequisitoConsentimiento } from './RequisitoConsentimiento';
import { RequisitoBiometria } from './RequisitoBiometria';
import { RequisitoDni } from './RequisitoDni';
import type { EstadoEnrollment, Principal } from '../../../lib/types';

interface Props {
  principal: Principal | null;
  enrollment: EstadoEnrollment | null;
  versionVigente: string | null;
  consentimientoOk: boolean;
  biometriaOk: boolean;
  biometriaCaducada: boolean;
  biometriaRenovacionRequerida: boolean;
  dniOk: boolean;
  perfilCompleto: boolean;
  onNavigate: (path: string) => void;
  onIniciarConsentimiento: () => void;
  onLeerConsentimiento: () => void;
  onIniciarEnrollment: () => void;
  onRenovarBiometria: () => void;
  onSimularDeriva: () => void;
  onRehacerFoto: () => void;
  onEscanearDni: () => void;
}

export function PerfilVistaGeneral({
  principal,
  enrollment,
  versionVigente,
  consentimientoOk,
  biometriaOk,
  biometriaCaducada,
  biometriaRenovacionRequerida,
  dniOk,
  perfilCompleto,
  onNavigate,
  onIniciarConsentimiento,
  onLeerConsentimiento,
  onIniciarEnrollment,
  onRenovarBiometria,
  onSimularDeriva,
  onRehacerFoto,
  onEscanearDni,
}: Props) {
  return (
    <div className="max-w-4xl mx-auto space-y-4 sm:space-y-6 animate-in fade-in duration-300">
      <BackButton onClick={() => onNavigate('/alumno')} />
      <header>
        <div className="flex items-center gap-sm">
          <h1 className="font-headline text-headline-md text-on-surface tracking-tight">Mi perfil</h1>
          <HelpButton title="Mi perfil">
            <p>
              Desde acá completás los <strong>requisitos para rendir</strong>: consentimiento
              informado, foto de perfil, verificación facial y (opcional) escaneo de DNI.
            </p>
            <p>
              La <em>captura biométrica</em> se hace una sola vez y queda vigente por 24 meses
              para todos tus exámenes. Si se vence o el sistema detecta deriva, te pediremos
              renovarla.
            </p>
            <p>
              Tus datos biométricos (foto y embedding) son <strong>datos sensibles</strong> bajo
              Ley 25.326: viajan cifrados, se usan solo para verificar tu identidad y se eliminan
              al egresar de la institución.
            </p>
          </HelpButton>
        </div>
        <p className="text-body-md text-on-surface-variant mt-xs">
          Datos personales y requisitos para rendir exámenes.
        </p>
      </header>

      <PerfilHeaderCard
        principal={principal}
        onRehacerFoto={consentimientoOk ? onRehacerFoto : undefined}
      />

      <PerfilBannerEstado
        perfilCompleto={perfilCompleto}
        biometriaCaducada={biometriaCaducada}
        biometriaRenovacionRequerida={biometriaRenovacionRequerida}
        onIrAExamenes={() => onNavigate('/alumno/mis-examenes')}
        onRenovarBiometria={onRenovarBiometria}
      />

      <RequisitoConsentimiento
        consentimiento={enrollment?.consentimiento ?? null}
        versionVigente={versionVigente}
        onIniciar={onIniciarConsentimiento}
        onLeer={onLeerConsentimiento}
      />

      <RequisitoBiometria
        biometria={enrollment?.biometria ?? null}
        biometriaOk={biometriaOk}
        biometriaCaducada={biometriaCaducada}
        biometriaRenovacionRequerida={biometriaRenovacionRequerida}
        consentimientoOk={consentimientoOk}
        devToolsEnabled={false}
        onCapturar={onIniciarEnrollment}
        onRenovar={onRenovarBiometria}
        onSimularDeriva={onSimularDeriva}
      />

      <RequisitoDni
        dni={enrollment?.dni ?? null}
        dniOk={dniOk}
        dniScanHabilitado={ENABLE_DNI_SCAN}
        onEscanear={onEscanearDni}
      />
    </div>
  );
}
