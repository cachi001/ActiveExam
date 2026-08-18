/**
 * RiesgoBanner — Banner de estado de riesgo del detalle de sesión (C-76 bloque 9.1).
 *
 * Distingue visualmente los dos estados que pide el rediseño: SIN riesgo (score bajo,
 * banner discreto de confirmación) vs CON riesgo (medio/alto, banner que llama la
 * atención del revisor antes de decidir). Reusa `nivelRiesgo`/`scoreSoftBg`/
 * `scoreSoftBorder` — la misma fuente de verdad de color que ya usan las listas
 * (SesionCard, SesionVivoCard): no se inventa una paleta nueva para el detalle.
 *
 * L2.5: el texto es siempre descriptivo ("presenta señales"), nunca un veredicto
 * ("es sospechoso") — el score prioriza, la decisión queda para el humano.
 */
import { Icon } from '../../ui/components';
import { nivelRiesgo, scoreSoftBg, scoreSoftBorder } from './helpers';

const CONTENIDO = {
  bajo: {
    icon: 'check_circle',
    iconTone: 'text-success',
    titulo: 'Sin señales de riesgo relevantes',
    detalle: 'El score y los eventos registrados no ameritan atención especial.',
  },
  medio: {
    icon: 'warning',
    iconTone: 'text-warning',
    titulo: 'Esta sesión presenta señales a revisar',
    detalle: 'Repasá los eventos y la evidencia antes de tomar una decisión.',
  },
  alto: {
    icon: 'report',
    iconTone: 'text-error',
    titulo: 'Esta sesión concentra múltiples señales de riesgo',
    detalle: 'Revisá con atención la evidencia — eventos, discrepancias y biometría — antes de decidir.',
  },
} as const;

export function RiesgoBanner({ score }: { score: number }) {
  const nivel = nivelRiesgo(score);
  const c = CONTENIDO[nivel];
  return (
    <div
      className={`flex items-start gap-md rounded-xl border px-md py-md ${scoreSoftBg(score)} ${scoreSoftBorder(score)}`}
      role={nivel === 'alto' ? 'alert' : undefined}
    >
      <Icon name={c.icon} className={`text-[22px] shrink-0 mt-px ${c.iconTone}`} fill />
      <div className="min-w-0 space-y-xs">
        <p className="text-label-md font-bold text-on-surface">{c.titulo}</p>
        <p className="text-label-sm text-on-surface-variant">{c.detalle}</p>
      </div>
    </div>
  );
}

export default RiesgoBanner;
