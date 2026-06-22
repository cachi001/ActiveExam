/**
 * BiometriaCard — Sección de verificación biométrica del detalle de sesión.
 *
 * Muestra el resultado de liveness, los retos resueltos (como chips) y el
 * resultado textual. Si no hubo verificación, muestra un estado vacío sobrio.
 */
import { Icon, Card, SectionTitle } from '../../ui/components';
import type { BiometriaDetalle } from '../../lib/types';

export function BiometriaCard({ biometria }: { biometria: BiometriaDetalle | null }) {
  return (
    <Card className="space-y-md">
      <SectionTitle sub="Liveness híbrido y retos de verificación de identidad">
        Verificación biométrica
      </SectionTitle>

      {biometria === null ? (
        <div className="flex items-center gap-sm text-body-md text-on-surface-variant py-sm">
          <Icon name="fingerprint" className="text-[22px]" />
          Sin verificación biométrica registrada en esta sesión.
        </div>
      ) : (
        (() => {
          // El estado lo decide el RESULTADO de la verificación (verificado / rechazado),
          // no el flag de liveness pasivo (que es un sub-detalle y puede confundir:
          // antes mostraba "Liveness no superado" aunque la verificación fuese OK).
          const ok = biometria.resultado === 'verificado';
          const titulo = ok
            ? 'Identidad verificada'
            : biometria.resultado === 'camara_virtual_detectada'
              ? 'Cámara virtual detectada'
              : 'Verificación no superada';
          return (
            <div
              className={`flex items-center gap-sm p-md rounded-xl border ${
                ok ? 'bg-success-container/40 border-success/30' : 'bg-error-container/40 border-error/30'
              }`}
            >
              <Icon
                name={ok ? 'verified' : 'gpp_bad'}
                className={`text-[24px] ${ok ? 'text-success' : 'text-error'}`}
                fill
              />
              <p className={`font-semibold ${ok ? 'text-success' : 'text-error'}`}>{titulo}</p>
            </div>
          );
        })()
      )}
    </Card>
  );
}

export default BiometriaCard;
