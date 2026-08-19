/**
 * Configuracion — página de ajustes globales del sistema (settings).
 *
 * Vista tabbed full-width que concentra TODO lo configurable del proctoring en un
 * solo lugar: parámetros generales (umbral de revisión + detectores), pesos de
 * scoring por evento, umbrales del motor de detección y el texto del
 * consentimiento que confirman los alumnos.
 *
 * El título vive en el contenido (lo renderiza StaffShell). Solo admin_sistema.
 */
import { useState } from 'react';
import { StaffShell } from '../ui/shells';
import { STAFF_NAV } from '../ui/nav';
import { HelpButton } from '../ui/HelpButton';
import { Card } from '../ui/components';
import SeccionProctoring from './configuracion/SeccionProctoring';
import SeccionScoring from './configuracion/SeccionScoring';
import SeccionDeteccion from './configuracion/SeccionDeteccion';
import SeccionConsentimiento from './configuracion/SeccionConsentimiento';
type TabId = 'proctoring' | 'scoring' | 'deteccion' | 'consentimiento';

const TABS: { id: TabId; label: string; icon: string }[] = [
  { id: 'proctoring',    label: 'Parámetros generales', icon: 'tune' },
  { id: 'scoring',       label: 'Scoring',              icon: 'speed' },
  { id: 'deteccion',     label: 'Detección',            icon: 'visibility' },
  { id: 'consentimiento', label: 'Consentimiento',      icon: 'gavel' },
];

const AYUDA = (
  <HelpButton title="Configuración del sistema">
    <p>
      Acá ajustás todo lo que define cómo se comporta el proctoring por defecto:
      el <strong>umbral</strong> que manda una sesión a revisión, qué <strong>detectores</strong> se
      vigilan, cuánto <strong>impacta</strong> cada evento en el puntaje de riesgo, qué tan tolerante es el
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
        {/* Una sola card contiene tabs + contenido: antes las pestañas quedaban
            sueltas sobre el fondo gris y cada tab tenía su propia card separada. */}
        <Card padded={false} className="overflow-hidden">
          {/* relative + degradado a la derecha: en mobile las pestañas desbordan
              (overflow-x-auto) y sin esta pista visual "Consentimiento" parecía
              no existir — el usuario no tenía forma de saber que hay que scrollear. */}
          <div className="relative border-b border-outline-variant/60 px-lg pt-lg">
            <div className="flex overflow-x-auto no-scrollbar">
              {TABS.map((t) => {
                const active = tab === t.id;
                return (
                  <button
                    key={t.id}
                    onClick={() => setTab(t.id)}
                    className={`px-4 first:pl-0 py-2.5 text-[13px] font-medium border-b-2 -mb-px whitespace-nowrap shrink-0 transition-colors ${
                      active
                        ? 'border-primary text-primary'
                        : 'border-transparent text-on-surface-variant hover:text-on-surface'
                    }`}
                  >
                    {t.label}
                  </button>
                );
              })}
            </div>
            <div className="pointer-events-none absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-surface to-transparent sm:hidden" />
          </div>

          <div className="p-lg">
            {tab === 'proctoring'    && <SeccionProctoring />}
            {tab === 'scoring'       && <SeccionScoring />}
            {tab === 'deteccion'     && <SeccionDeteccion />}
            {tab === 'consentimiento' && <SeccionConsentimiento />}
          </div>
        </Card>
      </div>
    </StaffShell>
  );
}
