/**
 * SesionVivoCard — Tarjeta de una sesión en la vista de supervisión EN VIVO.
 *
 * Variante de SesionCard orientada al monitoreo en tiempo real: resalta el riesgo
 * (borde-izquierdo + chip de score) y destaca con un badge "Atención" las sesiones
 * que superan el umbral de riesgo alto. Toda la tarjeta es clickable (teclado
 * incluido) y abre el detalle de la sesión. No incluye acción de borrado: en vivo
 * no se eliminan sesiones, solo se observan.
 *
 * L2.5: el score es un indicador de PRIORIDAD para revisión humana, nunca un
 * veredicto. La tarjeta no sanciona; solo prioriza visualmente.
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
  nivelRiesgo,
  type ExamInfo,
} from './helpers';

export function SesionVivoCard({
  sesion,
  onAbrir,
  examInfo,
}: {
  sesion: SesionProctoringResumen;
  onAbrir: (sesion: SesionProctoringResumen) => void;
  examInfo?: ExamInfo | null;
}) {
  const riesgoAlto = nivelRiesgo(sesion.score) === 'alto';

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
        p-md pr-10 shadow-card transition-all duration-200
        hover:shadow-card-lg hover:-translate-y-px
        focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40
        ${riesgoAlto ? 'ring-1 ring-error/30 bg-error-container/10' : ''}`}
    >
      {/* Header: etiqueta + modo + badge de atención + fecha relativa */}
      <div className="flex items-start justify-between gap-sm">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-sm flex-wrap">
            <h3 className="font-headline text-title-lg text-on-surface tracking-tight truncate">
              {sesion.etiqueta?.trim() || 'Sesión sin etiqueta'}
            </h3>
            <Badge tone={modoBadgeTone(sesion.modo)}>{modoLabel(sesion.modo)}</Badge>
            {riesgoAlto && (
              <Badge tone="error" dot>
                Atención
              </Badge>
            )}
          </div>
          {examInfo && (
            <p className="flex items-center gap-base text-label-sm text-on-surface-variant mt-base truncate">
              <Icon name="menu_book" className="text-[15px]" />
              {examInfo.materiaNombre} · {examInfo.docente}
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
    </div>
  );
}

export default SesionVivoCard;
