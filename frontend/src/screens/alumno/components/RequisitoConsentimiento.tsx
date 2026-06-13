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
  viaAlternativa: boolean;
  onIniciar: () => void;
  /** Abrir el consentimiento en modo lectura (volver a leerlo). */
  onLeer: () => void;
}

export function RequisitoConsentimiento({ consentimiento, viaAlternativa, onIniciar, onLeer }: RequisitoConsentimientoProps) {
  const ok = Boolean(consentimiento);

  return (
    <RequisitoCard
      icon="gavel"
      title="Consentimiento informado"
      badge={{
        tone: ok ? 'success' : 'warning',
        label: ok ? (viaAlternativa ? 'Vía alternativa' : 'Completado') : 'Pendiente',
      }}
    >
      {ok && consentimiento ? (
        <div className="space-y-sm">
          <div className="flex items-start gap-sm">
            <Icon name="check_circle" className="text-success text-[20px] shrink-0 mt-px" fill />
            <p className="text-label-sm text-on-surface">
              Aceptaste el consentimiento el{' '}
              <strong>
                {new Date(consentimiento.timestamp).toLocaleDateString('es-AR', { day: '2-digit', month: 'long', year: 'numeric' })}
              </strong>.
            </p>
          </div>
          <Button variant="outline" size="sm" icon="description" onClick={onLeer}>
            Leer el consentimiento
          </Button>
          {viaAlternativa && (
            <div className="flex items-start gap-sm bg-white border border-outline-variant/40 rounded-xl p-sm">
              <Icon name="support_agent" className="text-[16px] text-on-surface-variant shrink-0 mt-px" />
              <p className="text-label-sm text-on-surface-variant">
                Elegiste la <strong>vía alternativa sin biometría</strong>. Un proctor humano supervisará
                tu verificación de identidad en cada examen.
              </p>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-md">
          <p className="text-label-sm text-on-surface-variant">
            Para enrollarte y poder rendir exámenes, necesitás leer y aceptar el uso de tus datos
            biométricos. El acuse es inmutable e incluye la versión del texto que firmaste.
          </p>
          <Button onClick={onIniciar} iconRight="arrow_forward">
            Leer y consentir
          </Button>
        </div>
      )}
    </RequisitoCard>
  );
}
