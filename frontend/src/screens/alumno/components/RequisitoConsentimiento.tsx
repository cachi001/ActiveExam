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
}

/** Etiqueta clave/valor compacta para los metadatos del acuse. */
function MetaCampo({ label, children, className = '' }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={className}>
      <p className="text-on-surface-variant uppercase tracking-wide text-[10px] font-semibold mb-base">{label}</p>
      {children}
    </div>
  );
}

export function RequisitoConsentimiento({ consentimiento, viaAlternativa, onIniciar }: RequisitoConsentimientoProps) {
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
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-sm text-label-sm">
            <MetaCampo label="Versión">
              <p className="text-on-surface font-semibold">{consentimiento.version}</p>
            </MetaCampo>
            <MetaCampo label="Fecha de acuse">
              <p className="text-on-surface font-semibold">
                {new Date(consentimiento.timestamp).toLocaleDateString('es-AR', {
                  day: '2-digit', month: 'long', year: 'numeric',
                })}
              </p>
            </MetaCampo>
            <MetaCampo label="Hash de acuse" className="sm:col-span-2">
              <p className="text-on-surface font-mono text-[11px] break-all">{consentimiento.hash}</p>
            </MetaCampo>
          </div>
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
          <Button onClick={onIniciar} icon="gavel" iconRight="arrow_forward">
            Leer y consentir
          </Button>
        </div>
      )}
    </RequisitoCard>
  );
}
