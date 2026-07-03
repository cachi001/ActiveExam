/**
 * RequisitoConsentimiento — sección de consentimiento informado dentro del perfil.
 *
 * Extraída de StudentProfile (C-42) para mantener el contenedor ≤ 400 líneas.
 * Presentación pura: muestra el acuse existente o el CTA para iniciarlo.
 */
import { Button, Icon } from '../../../ui/components';
import { RequisitoCard } from './RequisitoCard';
import type { AcuseConsentimiento } from '../../../lib/types';

interface RequisitoConsentimientoProps {
  consentimiento: AcuseConsentimiento | null;
  /** Versión de consentimiento VIGENTE según la config del sistema. Si no
   * coincide con la versión aceptada por el alumno, se requiere re-aceptación. */
  versionVigente?: string | null;
  onIniciar: () => void;
  /** Abrir el consentimiento en modo lectura (volver a leerlo). */
  onLeer: () => void;
}

export function RequisitoConsentimiento({ consentimiento, versionVigente, onIniciar, onLeer }: RequisitoConsentimientoProps) {
  const ok = Boolean(consentimiento);
  const desactualizado = Boolean(
    ok && consentimiento && versionVigente && consentimiento.version !== versionVigente
  );

  const badge = !ok
    ? { tone: 'warning' as const, label: 'Pendiente' }
    : desactualizado
      ? { tone: 'warning' as const, label: 'Renovación requerida' }
      : { tone: 'success' as const, label: 'Completado' };

  return (
    <RequisitoCard
      icon="gavel"
      title="Consentimiento informado"
      badge={badge}
    >
      {ok && consentimiento ? (
        <div className="space-y-sm">
          <div className="flex items-center gap-sm">
            <Icon
              name={desactualizado ? 'update' : 'check_circle'}
              className={`${desactualizado ? 'text-warning' : 'text-success'} text-[20px] shrink-0`}
              fill
            />
            <p className="text-label-sm text-on-surface">
              Aceptaste la <strong>versión {consentimiento.version}</strong> del consentimiento el{' '}
              <strong>
                {new Date(consentimiento.timestamp).toLocaleDateString('es-AR', { day: '2-digit', month: 'long', year: 'numeric' })}
              </strong>.
            </p>
          </div>
          {desactualizado && (
            <div className="flex items-start gap-sm bg-warning-container border border-warning-200 rounded-xl p-sm">
              <Icon name="info" className="text-warning text-[18px] shrink-0 mt-px" fill />
              <p className="text-label-sm text-on-surface">
                Hay una nueva versión del consentimiento (<strong>{versionVigente}</strong>) vigente.
                Necesitás leerla y aceptarla para poder rendir exámenes.
              </p>
            </div>
          )}
          <div className="flex flex-wrap gap-sm justify-end">
            {desactualizado ? (
              <Button size="sm" onClick={onIniciar}>
                Leer y aceptar versión {versionVigente}
              </Button>
            ) : (
              <Button size="sm" icon="description" onClick={onLeer}>
                Leer el consentimiento
              </Button>
            )}
          </div>
        </div>
      ) : (
        <div className="space-y-md">
          <p className="text-label-sm text-on-surface-variant">
            Para enrollarte y poder rendir exámenes, necesitás leer y aceptar el uso de tus datos
            biométricos. El acuse es inmutable e incluye la versión del texto que firmaste.
          </p>
          <Button onClick={onIniciar} size="sm">
            Leer y consentir
          </Button>
        </div>
      )}
    </RequisitoCard>
  );
}
