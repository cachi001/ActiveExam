import { Card, Button } from '../../../ui/components';
import { useNavigate } from '../../../lib/router';
import type { NotaExamen } from '../../../lib/types';

export function NotaCard({ nota }: { nota: NotaExamen }) {
  const navigate = useNavigate();
  const enRevision = nota.en_cola_revision;
  // C-69: nota oculta hasta el cierre (nota_visible=false → nota=null).
  const notaPendiente = nota.nota_visible === false;
  const tieneNota = !notaPendiente && nota.nota !== null && nota.nota !== undefined;
  const aprobado = tieneNota && nota.aprobado === true;
  const fmtFecha = (iso?: string | null) =>
    iso ? new Date(iso).toLocaleString('es-AR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';

  const notaTxt = `Nota: ${nota.nota}${nota.nota_maxima != null ? ` / ${nota.nota_maxima}` : ''}`;

  return (
    <Card className="p-md space-y-sm">
      <div className="flex items-start justify-between gap-md">
        <p className="text-[14px] font-semibold text-on-surface leading-tight min-w-0">
          {nota.examen_titulo}
        </p>

        {/* Un SOLO chip: estado primero, luego la nota (o pendiente/en revisión). */}
        {notaPendiente ? (
          <span className="shrink-0 inline-flex items-center gap-xs text-[12px] font-medium rounded-full px-sm py-0.5 bg-warning-container text-warning">
            Disponible al cerrar{nota.cierre ? ` · ${fmtFecha(nota.cierre)}` : ''}
          </span>
        ) : tieneNota ? (
          <span
            className={`shrink-0 inline-flex items-center text-[12px] font-semibold rounded-full px-sm py-0.5 ${
              aprobado ? 'bg-success-container text-success' : 'bg-error-container text-on-error-container'
            }`}
          >
            {aprobado ? 'Aprobado' : 'Desaprobado'}{enRevision ? ' (preliminar)' : ''} · {notaTxt}
          </span>
        ) : (
          <span className="shrink-0 inline-flex items-center text-[12px] font-medium rounded-full px-sm py-0.5 bg-surface-container-high text-on-surface-variant">
            Nota pendiente
          </span>
        )}
      </div>

      {enRevision && (
        <p className="text-[12px] text-on-surface-variant">
          En cola de revisión por los eventos registrados durante la supervisión. Un docente la
          revisará y confirmará tu nota.
        </p>
      )}

      {nota.examen_id && nota.revision_disponible && (
        <Button
          variant="ghost"
          size="sm"
          icon="fact_check"
          onClick={() => navigate(`/alumno/revision/${nota.examen_id}`)}
          className="-ml-sm"
        >
          Revisar mis respuestas
        </Button>
      )}
    </Card>
  );
}
