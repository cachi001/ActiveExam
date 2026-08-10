import { Card, Button, Icon } from '../../../ui/components';
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
            {/* "(preliminar)" solo mientras la revisión está PENDIENTE. Con el
                caso resuelto la nota es definitiva — seguir diciendo preliminar
                le hace creer al alumno que todavía puede cambiar. */}
            {aprobado ? 'Aprobado' : 'Desaprobado'}
            {enRevision && !nota.nota_anulada ? ' (preliminar)' : ''} · {notaTxt}
          </span>
        ) : (
          <span className="shrink-0 inline-flex items-center text-[12px] font-medium rounded-full px-sm py-0.5 bg-surface-container-high text-on-surface-variant">
            Nota pendiente
          </span>
        )}
      </div>

      {/* El aviso de "en cola" y el de anulación son EXCLUYENTES: si el caso ya
          se resolvió no puede seguir diciendo que falta revisarlo. El backend ya
          apaga `en_cola_revision` al haber decisión; esta guarda es la red por si
          llegara un dato viejo cacheado. */}
      {enRevision && !nota.nota_anulada && (
        <p className="text-[12px] text-on-surface-variant">
          En cola de revisión por los eventos registrados durante la supervisión. Un tutor la
          revisará y confirmará tu nota.
        </p>
      )}

      {/* Anulación: bloque propio con fondo y borde, no un renglón suelto. Antes
          era un <p> pegado al botón de abajo y se leía como un error de la
          pantalla. Es la peor noticia que da esta card: necesita su espacio. */}
      {nota.nota_anulada && (
        <div className="flex items-start gap-sm rounded-lg border border-error-200 bg-error-50 px-sm py-sm">
          <Icon name="block" className="text-[18px] text-error-600 shrink-0 mt-0.5" fill />
          <div className="min-w-0">
            <p className="text-[13px] font-semibold text-error-700 leading-tight">
              Nota anulada por fraude
            </p>
            <p className="text-[12px] text-on-surface-variant leading-snug mt-0.5">
              La decisión la tomó una persona tras revisar tu sesión. Podés ver el motivo
              en el informe de devolución.
            </p>
          </div>
        </div>
      )}

      {/* Acciones agrupadas y separadas del contenido: sin esto el botón quedaba
          pegado al texto de arriba. */}
      {((nota.examen_id && nota.revision_disponible) ||
        (nota.informe_disponible && nota.session_id)) && (
        <div className="flex flex-wrap items-center gap-xs pt-xs">
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

          {nota.informe_disponible && nota.session_id && (
            <Button
              variant="ghost"
              size="sm"
              icon="gavel"
              onClick={() => navigate(`/alumno/informe/${nota.session_id}`)}
              className="text-error"
            >
              Ver informe de devolución
            </Button>
          )}
        </div>
      )}
    </Card>
  );
}
