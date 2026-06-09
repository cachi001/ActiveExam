import { TIPO_EVENTO_LABEL } from '../../../lib/api';
import type { TipoEvento } from '../../../lib/types';

const DETECTORES: TipoEvento[] = [
  'rostro_ausente',
  'multiples_rostros',
  'mirada_desviada_sostenida',
  'perdida_de_foco',
  'monitor_adicional',
  'cambio_pestana',
  'salida_pantalla_completa',
  'copiar_pegar',
];

interface DetectoresSelectorProps {
  value: TipoEvento[];
  onChange: (detectores: TipoEvento[]) => void;
}

export default function DetectoresSelector({ value, onChange }: DetectoresSelectorProps) {
  const toggle = (d: TipoEvento) => {
    onChange(value.includes(d) ? value.filter((x) => x !== d) : [...value, d]);
  };

  return (
    <div className="space-y-sm">
      <p className="text-label-sm text-on-surface-variant">
        <span className="font-semibold text-on-surface">{value.length}</span> de {DETECTORES.length} detectores activos
      </p>
      <div className="grid sm:grid-cols-2 gap-base">
        {DETECTORES.map((d) => {
          const on = value.includes(d);
          return (
            <label
              key={d}
              className={`flex items-center gap-base p-sm rounded-xl border cursor-pointer transition-colors ${
                on
                  ? 'bg-primary-fixed/40 border-primary-container'
                  : 'bg-white border-outline-variant/40'
              }`}
            >
              <input
                type="checkbox"
                checked={on}
                onChange={() => toggle(d)}
                className="accent-primary w-4 h-4"
              />
              <span className="text-label-md font-semibold text-on-surface">
                {TIPO_EVENTO_LABEL[d]}
              </span>
            </label>
          );
        })}
      </div>
    </div>
  );
}
