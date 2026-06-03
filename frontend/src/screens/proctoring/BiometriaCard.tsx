/**
 * BiometriaCard — Sección de verificación biométrica del detalle de sesión.
 *
 * Muestra el resultado de liveness, los retos resueltos (como chips) y el
 * resultado textual. Si no hubo verificación, muestra un estado vacío sobrio.
 */
import { Icon, Card, Badge, SectionTitle } from '../../ui/components';
import type { BiometriaDetalle } from '../../lib/types';

const RETO_LABEL: Record<string, string> = {
  girar_izquierda: 'Girar izquierda',
  girar_derecha: 'Girar derecha',
  parpadear: 'Parpadear',
  acercarse: 'Acercarse',
  sonreir: 'Sonreír',
};

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
        <div className="space-y-md">
          {/* Liveness */}
          <div
            className={`flex items-center gap-sm p-md rounded-xl border ${
              biometria.liveness_ok
                ? 'bg-success-container/40 border-success/30'
                : 'bg-error-container/40 border-error/30'
            }`}
          >
            <Icon
              name={biometria.liveness_ok ? 'verified' : 'gpp_bad'}
              className={`text-[24px] ${biometria.liveness_ok ? 'text-success' : 'text-error'}`}
              fill
            />
            <div>
              <p className={`font-semibold ${biometria.liveness_ok ? 'text-success' : 'text-error'}`}>
                Liveness {biometria.liveness_ok ? 'verificado' : 'no superado'}
              </p>
              <p className="text-label-sm text-on-surface-variant">
                Resultado: <span className="font-semibold text-on-surface">{biometria.resultado}</span>
              </p>
            </div>
          </div>

          {/* Retos resueltos */}
          <div className="space-y-sm">
            <p className="text-label-sm text-on-surface-variant">Retos resueltos</p>
            {biometria.retos_resueltos.length === 0 ? (
              <span className="text-body-md text-on-surface-variant italic">Ninguno registrado</span>
            ) : (
              <div className="flex gap-base flex-wrap">
                {biometria.retos_resueltos.map((reto) => (
                  <Badge key={reto} tone="success" dot>
                    {RETO_LABEL[reto] ?? reto}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}

export default BiometriaCard;
