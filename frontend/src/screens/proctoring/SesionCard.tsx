/**
 * SesionCard — Tarjeta de una sesión grabada en la lista de proctoring.
 *
 * Estilo minimalista premium: superficie limpia, borde-izquierdo de color según
 * el riesgo (verde/ámbar/rojo según score), hover con elevación sutil. Toda la
 * tarjeta es clickable (teclado incluido) y abre el detalle.
 *
 * NO tiene acción de eliminar (c-76 tarea 16): la evidencia de proctoring no se
 * borra, se preserva con cadena de custodia (regla dura #6/#7).
 */
import { Icon, Badge } from '../../ui/components';
import type { SesionProctoringResumen } from '../../lib/types';
import {
  formatFechaRelativa,
  formatFecha,
  scoreCardAcento,
  scoreTextColor,
  modoBadgeTone,
  modoLabel,
  type ExamInfo,
} from './helpers';

export function SesionCard({
  sesion,
  onAbrir,
  examInfo,
}: {
  sesion: SesionProctoringResumen;
  onAbrir: (sesion: SesionProctoringResumen) => void;
  examInfo?: ExamInfo | null;
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onAbrir(sesion)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onAbrir(sesion);
        }
      }}
      className={`group relative cursor-pointer rounded-xl border ${scoreCardAcento(sesion.score, sesion.umbral_cola_revision_efectivo)}
        p-md shadow-card transition-all duration-200
        hover:shadow-card-lg hover:-translate-y-px
        focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40`}
    >
      {/* Header: etiqueta + modo + fecha relativa */}
      <div className="flex items-start justify-between gap-sm">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-sm flex-wrap">
            <h3 className="font-headline text-title-lg text-on-surface tracking-tight truncate">
              {sesion.etiqueta?.trim() || 'Sesión sin etiqueta'}
            </h3>
            <Badge tone={modoBadgeTone(sesion.modo)}>{modoLabel(sesion.modo)}</Badge>
          </div>
          {examInfo && (
            <p className="text-label-sm text-on-surface-variant mt-base truncate">
              {examInfo.materiaNombre} · {examInfo.comisionNombre}
            </p>
          )}
          <p
            className="flex items-center gap-base text-label-sm text-on-surface-variant mt-base"
            title={formatFecha(sesion.creada_en, true)}
          >
            <Icon name="schedule" className="text-[15px]" />
            {formatFechaRelativa(sesion.creada_en)}
          </p>
        </div>
      </div>

      {/* Métricas con separadores. Usamos ?? 0 porque algunos endpoints (mock,
          versiones viejas del backend o respuestas degradadas) pueden no traer
          los conteos: mostrar "0" es preferible a un hueco visual ambiguo. */}
      <div className="flex items-center gap-sm flex-wrap text-label-md text-on-surface-variant mt-sm">
        <span className="inline-flex items-center gap-base">
          <Icon name="notifications" className="text-[16px]" />
          {sesion.total_eventos ?? 0} eventos
        </span>
        <span className="text-outline-variant" aria-hidden>·</span>
        <span
          className={`inline-flex items-center gap-base ${
            (sesion.total_discrepancias ?? 0) > 0 ? 'text-error font-semibold' : ''
          }`}
        >
          <Icon name="rule" className="text-[16px]" />
          {sesion.total_discrepancias ?? 0} discrepancias
        </span>
        <span className="text-outline-variant" aria-hidden>·</span>
        <span className={`inline-flex items-center gap-base font-bold ${scoreTextColor(sesion.score ?? 0, sesion.umbral_cola_revision_efectivo)}`}>
          <Icon name="speed" className="text-[16px]" fill />
          Score {sesion.score ?? 0}
        </span>
      </div>

      {/* Indicador de navegación */}
      <Icon
        name="chevron_right"
        className="absolute bottom-md right-sm text-[20px] text-on-surface-variant
          opacity-0 group-hover:opacity-100 transition-opacity"
      />
    </div>
  );
}

export default SesionCard;
