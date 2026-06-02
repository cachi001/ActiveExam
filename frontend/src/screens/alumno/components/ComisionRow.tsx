import { Icon } from '../../../ui/components';
import type { Comision, Examen, Inscripcion } from '../../../lib/types';
import { ExamenCard } from './ExamenCard';

interface ComisionRowProps {
  comision: Comision;
  activa: boolean;
  cargandoExamenes: boolean;
  examenes: Examen[];
  inscripciones: Inscripcion[];
  inscribiendoId: string | null;
  onSelect: () => void;
  onInscribir: (examenId: string) => void;
}

export function ComisionRow({
  comision,
  activa,
  cargandoExamenes,
  examenes,
  inscripciones,
  inscribiendoId,
  onSelect,
  onInscribir,
}: ComisionRowProps) {
  const estaInscripto = (examenId: string) =>
    inscripciones.some((i) => i.examen_id === examenId);

  return (
    <div>
      <button
        onClick={onSelect}
        className={`w-full flex items-center gap-md px-md py-sm rounded-xl border transition-colors text-left ${
          activa
            ? 'bg-secondary-container border-secondary/20'
            : 'bg-surface-container border-outline-variant/30 hover:bg-surface-container-high'
        }`}
      >
        <Icon name="groups" className="text-on-surface-variant shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-label-md font-semibold text-on-surface">{comision.nombre}</p>
          <p className="text-label-sm text-on-surface-variant">
            {comision.docente} · {comision.horario}
          </p>
        </div>
        <Icon name={activa ? 'expand_less' : 'expand_more'} className="text-[20px] text-on-surface-variant shrink-0" />
      </button>

      {activa && (
        <div className="mt-sm ml-lg space-y-sm">
          {cargandoExamenes ? (
            <div className="flex items-center gap-sm text-on-surface-variant px-md py-sm">
              <Icon name="progress_activity" className="ae-spin text-[18px]" />
              <span className="text-label-md">Cargando exámenes…</span>
            </div>
          ) : examenes.length === 0 ? (
            <p className="text-label-md text-on-surface-variant px-md py-sm">No hay exámenes en esta comisión.</p>
          ) : (
            examenes.map((examen) => (
              <ExamenCard
                key={examen.id}
                examen={examen}
                inscripto={estaInscripto(examen.id)}
                inscribiendo={inscribiendoId === examen.id}
                onInscribir={() => onInscribir(examen.id)}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}
