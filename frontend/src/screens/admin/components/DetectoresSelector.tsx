/**
 * DetectoresSelector — selector de detectores activos.
 *
 * C-68 UX (D): cards con gap correcto, padding interno cómodo, switch alineado
 * a la derecha, nombre+descripción a la izquierda. Que respiren.
 */
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
  'corte_conectividad_prolongado',
];

// Descripciones cortas y claras (para NO técnicos) de qué vigila cada detector.
const DETECTOR_DESC: Record<string, string> = {
  rostro_ausente: 'No se ve ningún rostro frente a la cámara.',
  multiples_rostros: 'Aparece más de una persona en cámara.',
  mirada_desviada_sostenida: 'La mirada se va de la pantalla por un rato.',
  perdida_de_foco: 'La ventana del examen deja de estar activa.',
  monitor_adicional: 'Se detecta una segunda pantalla conectada.',
  cambio_pestana: 'El alumno cambia a otra pestaña o ventana.',
  salida_pantalla_completa: 'Se sale del modo pantalla completa.',
  copiar_pegar: 'Se usa copiar o pegar durante el examen.',
  corte_conectividad_prolongado: 'Se corta la conexión por un tiempo prolongado.',
};

interface DetectoresSelectorProps {
  value: TipoEvento[];
  onChange: (detectores: TipoEvento[]) => void;
}

export default function DetectoresSelector({ value, onChange }: DetectoresSelectorProps) {
  const toggle = (d: TipoEvento) => {
    onChange(value.includes(d) ? value.filter((x) => x !== d) : [...value, d]);
  };

  return (
    <div className="space-y-3 min-w-0">
      <p className="text-label-sm text-on-surface-variant">
        <span className="font-semibold text-on-surface">{value.length}</span> de {DETECTORES.length} detectores activos
      </p>
      <div className="flex flex-col gap-2">
        {DETECTORES.map((d) => {
          const on = value.includes(d);
          return (
            <button
              key={d}
              type="button"
              role="switch"
              aria-checked={on}
              aria-label={`${TIPO_EVENTO_LABEL[d]} — ${on ? 'activado' : 'desactivado'}`}
              onClick={() => toggle(d)}
              className={`group flex items-center gap-3 px-4 py-3 rounded-xl border text-left transition-colors min-w-0 focus:outline-none focus:ring-2 focus:ring-outline-variant ${
                on
                  ? 'bg-success-container/40 border-success/40'
                  : 'bg-error-container/30 border-error/30'
              }`}
            >
              {/* Nombre + descripción a la izquierda */}
              <div className="flex-1 min-w-0">
                <p className="text-label-md font-semibold text-on-surface truncate">
                  {TIPO_EVENTO_LABEL[d]}
                </p>
                <p className="text-[11px] text-on-surface-variant leading-snug mt-0.5">
                  {DETECTOR_DESC[d] ?? ''}
                </p>
              </div>
              {/* Switch a la derecha (presentacional; el click es del botón contenedor) */}
              <span
                className={`relative shrink-0 inline-flex h-6 w-11 rounded-full border-2 border-transparent transition-colors duration-200 ${
                  on ? 'bg-success-600' : 'bg-error-600'
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transition-transform duration-200 ${
                    on ? 'translate-x-5' : 'translate-x-0'
                  }`}
                />
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
