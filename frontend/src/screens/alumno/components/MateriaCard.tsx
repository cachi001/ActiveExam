import { Icon, LoadingSpinner } from '../../../ui/components';
import type { Materia, Comision, Examen, Inscripcion } from '../../../lib/types';
import { ComisionRow } from './ComisionRow';

interface MateriaCardProps {
  materia: Materia;
  activa: boolean;
  cargandoComisiones: boolean;
  comisiones: Comision[];
  comisionSeleccionada: Comision | null;
  cargandoExamenes: boolean;
  examenes: Examen[];
  inscripciones: Inscripcion[];
  inscribiendoId: string | null;
  onSelect: () => void;
  onSelectComision: (c: Comision) => void;
  onInscribir: (examenId: string) => void;
}

export function MateriaCard({
  materia,
  activa,
  cargandoComisiones,
  comisiones,
  comisionSeleccionada,
  cargandoExamenes,
  examenes,
  inscripciones,
  inscribiendoId,
  onSelect,
  onSelectComision,
  onInscribir,
}: MateriaCardProps) {
  return (
    <div>
      <button
        onClick={onSelect}
        className={`w-full flex items-center gap-md p-md rounded-xl border-2 transition-all text-left ${
          activa
            ? 'bg-surface-container-lowest border-primary ring-2 ring-primary/15 text-on-surface'
            : 'bg-surface-container-lowest border-outline-variant/40 hover:bg-surface-container-low hover:border-outline-variant text-on-surface'
        }`}
      >
        <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${activa ? 'bg-primary text-on-primary' : 'bg-secondary-container text-on-secondary'}`}>
          <Icon name="school" />
        </div>
        <div className="flex-1 min-w-0">
          <p className={`text-label-md font-semibold ${activa ? 'text-primary' : 'text-on-surface'}`}>
            {materia.nombre}
          </p>
          <p className="text-label-sm text-on-surface-variant">
            {materia.codigo} · {materia.descripcion}
          </p>
        </div>
        <Icon
          name={activa ? 'expand_less' : 'expand_more'}
          className={`text-[22px] shrink-0 ${activa ? 'text-primary' : 'text-on-surface-variant'}`}
        />
      </button>

      {activa && (
        <div className="mt-sm ml-lg space-y-sm">
          {cargandoComisiones ? (
            <LoadingSpinner size="sm" label="Cargando comisiones…" />
          ) : comisiones.length === 0 ? (
            <p className="text-label-md text-on-surface-variant px-md py-sm">No hay comisiones disponibles.</p>
          ) : (
            comisiones.map((comision) => (
              <ComisionRow
                key={comision.id}
                comision={comision}
                activa={comisionSeleccionada?.id === comision.id}
                cargandoExamenes={cargandoExamenes}
                examenes={examenes}
                inscripciones={inscripciones}
                inscribiendoId={inscribiendoId}
                onSelect={() => onSelectComision(comision)}
                onInscribir={onInscribir}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}
