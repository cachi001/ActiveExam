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
import { useMemo, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Card, Icon } from '../ui/components';
import { STAFF_NAV } from '../ui/nav';
import { HelpButton } from '../ui/HelpButton';
import SeccionProctoring from './configuracion/SeccionProctoring';
import SeccionScoring from './configuracion/SeccionScoring';
import SeccionDeteccion from './configuracion/SeccionDeteccion';
import SeccionConsentimiento from './configuracion/SeccionConsentimiento';
import SeccionMoodle from './configuracion/SeccionMoodle';
import MiCuentaCampus from './configuracion/MiCuentaCampus';
import { useAuth } from '../lib/authStore';

type TabId = 'proctoring' | 'scoring' | 'deteccion' | 'consentimiento' | 'moodle';

// `soloAdmin: true` = define CÓMO se detecta el fraude. El docente no entra ahí:
// quien dicta la materia no debe poder aflojar la detección de su propio examen
// (misma razón por la que la capacidad `configurar_sistema` no incluye a DOCENTE).
// La pestaña del campus SÍ la ve, porque su cuenta personal vive ahí y es lo que
// hace que sus notas puedan viajar.
const TABS: { id: TabId; label: string; icon: string; soloAdmin: boolean }[] = [
  { id: 'proctoring', label: 'Parámetros generales', icon: 'tune', soloAdmin: true },
  { id: 'scoring', label: 'Scoring', icon: 'speed', soloAdmin: true },
  { id: 'deteccion', label: 'Detección', icon: 'visibility', soloAdmin: true },
  { id: 'consentimiento', label: 'Consentimiento', icon: 'gavel', soloAdmin: true },
  { id: 'moodle', label: 'Campus (Moodle)', icon: 'sync_alt', soloAdmin: false },
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
  const hasRole = useAuth((s) => s.hasRole);
  const esAdmin = hasRole(['admin_sistema']);
  const tabs = useMemo(() => TABS.filter((t) => esAdmin || !t.soloAdmin), [esAdmin]);
  const [tab, setTab] = useState<TabId>(esAdmin ? 'proctoring' : 'moodle');

  return (
    <StaffShell
      nav={STAFF_NAV}
      title="Configuración del sistema"
      subtitle={
        esAdmin
          ? 'Ajustes globales del proctoring. Los cambios se aplican a partir del próximo examen.'
          : 'Conectá tu cuenta del campus para que las notas de tus comisiones puedan viajar.'
      }
      help={AYUDA}
    >
      <div className="animate-in fade-in duration-500">
        {/* Tabs de sección — una sola fila; scroll horizontal en mobile */}
        <div className="border-b border-outline-variant/60 flex overflow-x-auto no-scrollbar">
          {tabs.map((t) => {
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`inline-flex items-center gap-1.5 px-4 first:pl-0 py-2.5 text-[13px] font-medium border-b-2 -mb-px whitespace-nowrap shrink-0 transition-colors ${
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
          {esAdmin && tab === 'proctoring' && <SeccionProctoring />}
          {esAdmin && tab === 'scoring' && <SeccionScoring />}
          {esAdmin && tab === 'deteccion' && <SeccionDeteccion />}
          {esAdmin && tab === 'consentimiento' && <SeccionConsentimiento />}
          {tab === 'moodle' && (
            /* UNA sola tarjeta. Antes eran dos, y las dos decían "configurá el campus":
               el usuario no sabía cuál usar, y encima tenían anchos distintos. Ahora es
               un bloque con la cuenta personal arriba y, para el admin, la configuración
               institucional debajo de un separador. */
            <div className="space-y-lg">
              {/* Encabezado editorial, igual que el resto de las pestañas. Sin esto
                  la sección arrancaba con un h2 chico y todo se leía hundido. */}
              <div className="pb-4 border-b border-outline-variant/40">
                <h2 className="font-headline text-[24px] font-bold text-on-surface tracking-tight leading-tight">
                  Campus (Moodle)
                </h2>
                <p className="text-[13.5px] text-on-surface-variant leading-relaxed max-w-2xl mt-2">
                  {esAdmin
                    ? 'Conectá tu cuenta para que tus notas viajen con tu nombre, y definí a qué campus se conecta la institución.'
                    : 'Conectá tu cuenta del campus para que las notas de tus comisiones puedan viajar.'}
                </p>
              </div>
              <Card>
                {/* Al admin no se le repite la dirección del campus: la edita abajo. */}
                <MiCuentaCampus mostrarCampus={!esAdmin} />
                {esAdmin && (
                  <>
                    <hr className="my-lg border-t border-outline-variant" />
                    <SeccionMoodle />
                  </>
                )}
              </Card>
            </div>
          )}
        </div>
      </div>
    </StaffShell>
  );
}
