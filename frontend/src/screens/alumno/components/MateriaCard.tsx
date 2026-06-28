import { Icon, LoadingSpinner } from '../../../ui/components';
import type { Materia, Comision, ExamenContenidoResumen } from '../../../lib/types';
import { ComisionRow } from './ComisionRow';

interface MateriaCardProps {
  materia: Materia;
  activa: boolean;
  cargandoComisiones: boolean;
  comisiones: Comision[];
  comisionSeleccionada: Comision | null;
  cargandoExamenes: boolean;
  examenes: ExamenContenidoResumen[];
  rindiendoId: string | null;
  onSelect: () => void;
  onSelectComision: (c: Comision) => void;
  onRendir: (examenId: string) => void;
}

export function MateriaCard({
  materia,
  activa,
  cargandoComisiones,
  comisiones,
  comisionSeleccionada,
  cargandoExamenes,
  examenes,
  rindiendoId,
  onSelect,
  onSelectComision,
  onRendir,
}: MateriaCardProps) {
  return (
    <div>
      <button
        onClick={onSelect}
        className={`w-full flex items-center gap-4 px-4 py-4 rounded-lg border transition-colors text-left ${
          activa
            ? 'bg-white border-primary ring-1 ring-primary/15 text-on-surface'
            : 'bg-white border-surface-200 hover:bg-surface-50 hover:border-primary/40 text-on-surface'
        }`}
      >
        <div className={`w-11 h-11 rounded-lg flex items-center justify-center shrink-0 ${activa ? 'bg-primary text-on-primary' : 'bg-secondary-container text-on-secondary'}`}>
          <Icon name="school" className="text-[22px]" />
        </div>
        <div className="flex-1 min-w-0">
          <p className={`text-[15px] font-semibold leading-tight ${activa ? 'text-primary' : 'text-on-surface'}`}>
            {materia.nombre}
          </p>
          <p className="text-[13px] text-on-surface-variant leading-tight mt-1 truncate">
            {[materia.codigo, materia.descripcion].filter(Boolean).join(' · ')}
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
                rindiendoId={rindiendoId}
                onSelect={() => onSelectComision(comision)}
                onRendir={onRendir}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}
