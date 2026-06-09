/**
 * LeyendaSeveridad — referencia visual de los 5 niveles de severidad y el peso
 * de score que aporta cada uno al riesgo acumulado.
 *
 * Pensado para que un revisor tecnico (o un nuevo proctor) entienda de un vistazo
 * cuanto suma cada evento sin tener que abrir codigo o documentacion.
 */

import { Card, SectionTitle } from '../../ui/components';
import { SEVERITY_ORDER, SEVERITY_BADGE_COLORS, SEVERITY_RANGES } from './helpers';

export default function LeyendaSeveridad() {
  return (
    <Card className="space-y-md">
      <SectionTitle sub="Cuanto pesa cada nivel en el score acumulado (0–100)">
        Leyenda de severidad
      </SectionTitle>
      <ul className="space-y-base">
        {SEVERITY_ORDER.map((sev) => {
          const info = SEVERITY_RANGES[sev];
          return (
            <li
              key={sev}
              className="flex items-center gap-sm px-sm py-base rounded-lg border border-outline-variant/40 bg-white"
            >
              <span
                className={`inline-flex items-center justify-center min-w-[64px] px-sm py-base rounded-full text-label-sm font-bold ${SEVERITY_BADGE_COLORS[sev]}`}
              >
                {info.label}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-[13px] text-on-surface leading-tight">{info.descripcion}</p>
                <p className="text-[11px] text-on-surface-variant mt-0.5">
                  Suma <span className="font-mono font-bold">+{info.peso}</span> al score acumulado por evento.
                </p>
              </div>
            </li>
          );
        })}
      </ul>
      <p className="text-[11px] text-on-surface-variant">
        El score se acumula con tope en 100.
      </p>
    </Card>
  );
}
