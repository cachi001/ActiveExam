/**
 * Configuracion — página de ajustes globales del sistema (settings).
 *
 * Vista tabbed full-width que concentra TODO lo configurable del proctoring en un
 * solo lugar: parámetros de proctoring (umbral/detectores/retención), pesos de
 * scoring por evento, umbrales del motor de detección y el texto del
 * consentimiento que confirman los alumnos.
 *
 * El título vive en el contenido (lo renderiza StaffShell). Solo admin_sistema.
 */
import { useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon } from '../ui/components';
import { STAFF_NAV } from '../ui/nav';
import { HelpButton } from '../ui/HelpButton';
import SeccionProctoring from './configuracion/SeccionProctoring';
import SeccionScoring from './configuracion/SeccionScoring';
import SeccionDeteccion from './configuracion/SeccionDeteccion';
import SeccionConsentimiento from './configuracion/SeccionConsentimiento';

type TabId = 'proctoring' | 'scoring' | 'deteccion' | 'consentimiento';

const TABS: { id: TabId; label: string; icon: string }[] = [
  { id: 'proctoring', label: 'Proctoring', icon: 'tune' },
  { id: 'scoring', label: 'Scoring', icon: 'speed' },
  { id: 'deteccion', label: 'Detección', icon: 'visibility' },
  { id: 'consentimiento', label: 'Consentimiento', icon: 'gavel' },
];

const AYUDA = (
  <HelpButton title="Configuración del sistema">
    <p>
      Acá ajustás todo lo que define cómo se comporta el proctoring por defecto:
      el <strong>umbral</strong> que manda una sesión a revisión, qué <strong>detectores</strong> se
      vigilan, cuánto <strong>pesa</strong> cada evento en el score, qué tan tolerante es el
      <strong> motor de detección</strong> y el <strong>texto del consentimiento</strong> que firman los alumnos.
    </p>
    <p>Los cambios aplican a partir del próximo examen que arranque.</p>
  </HelpButton>
);

export default function Configuracion() {
  const [tab, setTab] = useState<TabId>('proctoring');

  return (
    <StaffShell
      nav={STAFF_NAV}
      title="Configuración del sistema"
      subtitle="Ajustes globales del proctoring. Los cambios se aplican a partir del próximo examen."
      help={AYUDA}
    >
      <div className="animate-in fade-in duration-500">
        {/* Tabs de sección */}
        <div className="border-b border-outline-variant/60 flex gap-1 overflow-x-auto">
          {TABS.map((t) => {
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`inline-flex items-center gap-1.5 px-4 py-2.5 text-[13px] font-medium border-b-2 -mb-px whitespace-nowrap transition-colors ${
                  active
                    ? 'border-primary text-primary'
                    : 'border-transparent text-on-surface-variant hover:text-on-surface'
                }`}
              >
                <Icon name={t.icon} className="text-[16px]" />
                {t.label}
              </button>
            );
          })}
        </div>

        {/* Contenido de la sección activa */}
        <div className="pt-lg">
          {tab === 'proctoring' && <SeccionProctoring />}
          {tab === 'scoring' && <SeccionScoring />}
          {tab === 'deteccion' && <SeccionDeteccion />}
          {tab === 'consentimiento' && <SeccionConsentimiento />}
        </div>
      </div>
    </StaffShell>
  );
}
