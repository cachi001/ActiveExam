/**
 * SesionCard — Tarjeta de una sesión grabada en la lista de proctoring.
 *
 * Estilo minimalista premium: superficie limpia, borde-izquierdo de color según
 * el riesgo (verde/ámbar/rojo según score), hover con elevación sutil. Toda la
 * tarjeta es clickable (teclado incluido) y abre el detalle. El botón eliminar
 * usa stopPropagation para no disparar la navegación.
 */
import { Icon, Badge } from '../../ui/components';
import type { SesionProctoringResumen } from '../../lib/types';
import {
  formatFechaRelativa,
  formatFecha,
  scoreAccentBorder,
  scoreTextColor,
  modoBadgeTone,
  modoLabel,
} from './helpers';

export function SesionCard({
  sesion,
  onAbrir,
  onEliminar,
}: {
  sesion: SesionProctoringResumen;
  onAbrir: (sesion: SesionProctoringResumen) => void;
  onEliminar: (sesion: SesionProctoringResumen) => void;
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
      className={`group relative cursor-pointer rounded-xl bg-surface-container-lowest
        border border-outline-variant/50 border-l-4 ${scoreAccentBorder(sesion.score)}
        p-md pr-12 shadow-card transition-all duration-200
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
          <p
            className="flex items-center gap-base text-label-sm text-on-surface-variant mt-base"
            title={formatFecha(sesion.creada_en, true)}
          >
            <Icon name="schedule" className="text-[15px]" />
            {formatFechaRelativa(sesion.creada_en)}
          </p>
        </div>
      </div>

      {/* Métricas con separadores */}
      <div className="flex items-center gap-sm flex-wrap text-label-md text-on-surface-variant mt-sm">
        <span className="inline-flex items-center gap-base">
          <Icon name="notifications" className="text-[16px]" />
          {sesion.total_eventos} eventos
        </span>
        <span className="text-outline-variant" aria-hidden>·</span>
        <span
          className={`inline-flex items-center gap-base ${
            sesion.total_discrepancias > 0 ? 'text-error font-semibold' : ''
          }`}
        >
          <Icon name="rule" className="text-[16px]" />
          {sesion.total_discrepancias} discrepancias
        </span>
        <span className="text-outline-variant" aria-hidden>·</span>
        <span className={`inline-flex items-center gap-base font-bold ${scoreTextColor(sesion.score)}`}>
          <Icon name="speed" className="text-[16px]" fill />
          Score {sesion.score}
        </span>
      </div>

      {/* Indicador de navegación */}
      <Icon
        name="chevron_right"
        className="absolute bottom-md right-sm text-[20px] text-on-surface-variant
          opacity-0 group-hover:opacity-100 transition-opacity"
      />

      {/* Eliminar (no dispara la navegación) */}
      <button
        type="button"
        aria-label="Eliminar sesión"
        title="Eliminar sesión"
        onClick={(e) => {
          e.stopPropagation();
          onEliminar(sesion);
        }}
        className="absolute top-sm right-sm rounded-lg p-base text-on-surface-variant
          hover:text-error hover:bg-error-container/40 transition-colors"
      >
        <Icon name="delete" className="text-[18px]" />
      </button>
    </div>
  );
}

export default SesionCard;
