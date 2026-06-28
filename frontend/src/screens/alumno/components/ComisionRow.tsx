import { Card, Button, Icon, LoadingSpinner } from '../../../ui/components';
import type { Comision, ExamenContenidoResumen } from '../../../lib/types';

interface ComisionRowProps {
  comision: Comision;
  activa: boolean;
  cargandoExamenes: boolean;
  examenes: ExamenContenidoResumen[];
  rindiendoId: string | null;
  onSelect: () => void;
  onRendir: (examenId: string) => void;
}

/** Subtítulo de la comisión: usa docente/horario (demo) o codigo/periodo/año (real, C-69). */
function subtituloComision(comision: Comision): string {
  if (comision.docente || comision.horario) {
    return [comision.docente, comision.horario].filter(Boolean).join(' · ');
  }
  const periodo = [comision.periodo, comision.anio].filter(Boolean).join(' ');
  return [comision.codigo, periodo].filter(Boolean).join(' · ');
}

export function ComisionRow({
  comision,
  activa,
  cargandoExamenes,
  examenes,
  rindiendoId,
  onSelect,
  onRendir,
}: ComisionRowProps) {
  const subtitulo = subtituloComision(comision);

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
          {subtitulo && (
            <p className="text-[12.5px] text-on-surface-variant leading-tight mt-0.5">
              {subtitulo}
            </p>
          )}
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
              <Card key={examen.id} className="flex items-center justify-between gap-md p-md">
                <div className="flex items-start gap-sm min-w-0">
                  <div className="w-9 h-9 rounded-md bg-primary-fixed text-primary flex items-center justify-center shrink-0 mt-0.5">
                    <Icon name="quiz" className="text-[18px]" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-[14px] font-medium text-on-surface leading-tight truncate">{examen.titulo}</p>
                    <p className="text-[12px] text-on-surface-variant mt-0.5">
                      {examen.cantidad_preguntas} {examen.cantidad_preguntas === 1 ? 'pregunta' : 'preguntas'}
                    </p>
                  </div>
                </div>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => onRendir(examen.id)}
                  disabled={rindiendoId === examen.id}
                  icon={rindiendoId === examen.id ? undefined : 'play_arrow'}
                >
                  {rindiendoId === examen.id ? 'Verificando…' : 'Rendir'}
                </Button>
              </Card>
            ))
          )}
        </div>
      )}
    </div>
  );
}
