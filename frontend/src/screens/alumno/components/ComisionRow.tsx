import { Icon, LoadingSpinner } from '../../../ui/components';
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
        className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg border transition-colors text-left ${
          activa
            ? 'bg-white border-primary ring-1 ring-primary/15'
            : 'bg-white border-surface-200 hover:bg-surface-50 hover:border-primary/40'
        }`}
      >
        <Icon
          name="groups"
          className={`shrink-0 text-[20px] ${activa ? 'text-primary' : 'text-on-surface-variant'}`}
        />
        <div className="flex-1 min-w-0">
          <p className={`text-[14px] font-semibold leading-tight ${activa ? 'text-primary' : 'text-on-surface'}`}>
            {comision.nombre}
          </p>
          <p className="text-[12.5px] text-on-surface-variant leading-tight mt-0.5">
            {comision.docente} · {comision.horario}
          </p>
        </div>
        <Icon
          name={activa ? 'expand_less' : 'expand_more'}
          className={`text-[20px] shrink-0 ${activa ? 'text-primary' : 'text-on-surface-variant'}`}
        />
      </button>

      {activa && (
        <div className="mt-sm ml-lg space-y-sm">
          {cargandoExamenes ? (
            <LoadingSpinner size="sm" label="Cargando exámenes…" />
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
