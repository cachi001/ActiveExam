import { Card, Icon } from '../../../ui/components';
import type { NotaExamen } from '../../../lib/types';

export function NotaCard({ nota }: { nota: NotaExamen }) {
  const enRevision = nota.en_cola_revision;
  const tieneNota = nota.nota !== null && nota.nota !== undefined;
  return (
    <Card className={`flex items-start gap-md p-md ${enRevision ? 'bg-warning-container/30 border-warning-200' : ''}`}>
      <div className={`w-9 h-9 rounded-md flex items-center justify-center shrink-0 mt-0.5 ${enRevision ? 'bg-warning-container text-warning' : 'bg-success-container text-success'}`}>
        <Icon name={enRevision ? 'hourglass_top' : 'grade'} className="text-[18px]" fill />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[14px] font-semibold text-on-surface leading-tight">{nota.examen_titulo}</p>
        <div className="flex items-center gap-sm flex-wrap mt-0.5">
          <p className="text-[15px] text-on-surface">
            {tieneNota ? (
              <>
                {enRevision ? 'Nota preliminar: ' : 'Nota: '}
                <strong>
                  {nota.nota}
                  {nota.nota_maxima != null ? ` / ${nota.nota_maxima}` : ''}
                </strong>
              </>
            ) : (
              <span className="text-on-surface-variant">Nota pendiente de cálculo</span>
            )}
          </p>
          {tieneNota && nota.aprobado != null && (
            <span
              className={`inline-flex items-center gap-xs text-[12px] font-medium rounded-full px-sm py-0.5 ${
                nota.aprobado
                  ? 'bg-success-container text-success'
                  : 'bg-error-container text-on-error-container'
              }`}
            >
              <Icon name={nota.aprobado ? 'check_circle' : 'cancel'} className="text-[14px]" fill />
              {nota.aprobado ? 'Aprobado' : 'Desaprobado'}
            </span>
          )}
        </div>
        {enRevision ? (
          <div className="flex items-start gap-xs mt-xs">
            <span className="inline-flex items-center gap-xs bg-warning-container text-warning text-[12px] font-medium rounded-full px-sm py-0.5">
              <Icon name="gavel" className="text-[14px]" fill /> En revisión por eventos registrados
            </span>
          </div>
        ) : tieneNota ? (
          <p className="text-[12px] text-on-surface-variant mt-0.5">Esta es tu nota final.</p>
        ) : null}
        {enRevision && (
          <p className="text-[12px] text-on-surface-variant mt-xs">
            Tu examen quedó en cola de revisión por los eventos registrados durante la supervisión.
            Un docente la revisará y confirmará tu nota.
          </p>
        )}
      </div>
    </Card>
  );
}
