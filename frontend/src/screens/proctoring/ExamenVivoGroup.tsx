/**
 * ExamenVivoGroup — Agrupa las sesiones EN VIVO de UN examen concreto.
 *
 * Arquitectura de información correcta: primero el examen (qué se está rindiendo),
 * y DENTRO sus personas (quién lo rinde, en filas compactas). Antes la pantalla
 * listaba personas sueltas sin el contexto del examen.
 *
 * Estilo minimalista: card contenedora plana (borde fino, sombra sutil), header
 * con el contexto académico + métricas agregadas, y filas de persona densas pero
 * respiradas. El acento de color lo da el RIESGO, no la marca.
 *
 * L2.5: el score PRIORIZA para revisión humana, nunca sanciona.
 */
import { Icon } from '../../ui/components';
import type { SesionProctoringResumen } from '../../lib/types';
import {
  formatFechaRelativa,
  scoreAccentBorder,
  scoreTextColor,
  nivelRiesgo,
  SCORE_UMBRAL_ALTO,
  type ExamInfo,
} from './helpers';

export function ExamenVivoGroup({
  examInfo,
  sesiones,
  onAbrir,
  onAbrirExamen,
}: {
  examInfo: ExamInfo | null;
  sesiones: SesionProctoringResumen[];
  onAbrir: (sesion: SesionProctoringResumen) => void;
  onAbrirExamen?: (examId: string) => void;
}) {
  const personas = sesiones.length;
  const eventos = sesiones.reduce((acc, s) => acc + s.total_eventos, 0);
  const riesgoAlto = sesiones.filter((s) => nivelRiesgo(s.score) === 'alto').length;
  const examId = sesiones[0]?.exam_id;
  const navegable = Boolean(examId && onAbrirExamen);

  // Escala: con muchas personas mostramos solo las de mayor riesgo y derivamos al
  // grid completo del examen. Evita renderizar cientos de filas en el panel en vivo.
  const MAX_VISIBLE = 6;
  const ordenadas = [...sesiones].sort((a, b) => b.score - a.score);
  const visibles = ordenadas.slice(0, MAX_VISIBLE);
  const ocultas = personas - visibles.length;

  return (
    <section className="rounded-2xl border border-outline-variant/70 bg-surface-container-lowest shadow-card overflow-hidden">
      {/* Header del examen: clickable → grid de personas de ESE examen */}
      <header
        {...(navegable
          ? {
              role: 'button',
              tabIndex: 0,
              onClick: () => onAbrirExamen!(examId!),
              onKeyDown: (e: React.KeyboardEvent) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onAbrirExamen!(examId!);
                }
              },
            }
          : {})}
        className={`group flex items-center justify-between gap-md p-md border-b border-outline-variant/50 bg-white
          ${navegable ? 'cursor-pointer hover:bg-surface-container-low focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40' : ''}`}
      >
        <div className="min-w-0">
          <div className="flex items-center gap-sm">
            <Icon name="menu_book" className="text-[18px] text-on-surface-variant shrink-0" />
            <h3 className="font-headline text-title-lg text-on-surface tracking-tight truncate">
              {examInfo?.examNombre ?? 'Sesiones sin examen asignado'}
            </h3>
          </div>
          {examInfo && (
            <p className="text-label-sm text-on-surface-variant mt-base truncate pl-[26px]">
              {examInfo.comisionNombre} · {examInfo.docente}
            </p>
          )}
        </div>
        {navegable && (
          <span className="inline-flex items-center gap-base text-label-md font-semibold text-primary shrink-0">
            <span className="hidden sm:inline">Ver personas</span>
            <Icon name="arrow_forward" className="text-[20px]" />
          </span>
        )}
      </header>

      {/* Métricas agregadas del examen */}
      <div className="flex items-center gap-lg px-md py-sm text-label-sm text-on-surface-variant border-b border-outline-variant/40">
        <span className="inline-flex items-center gap-base">
          <Icon name="group" className="text-[16px]" />
          <strong className="font-semibold text-on-surface">{personas}</strong>
          {personas === 1 ? 'persona' : 'personas'}
        </span>
        <span className="inline-flex items-center gap-base">
          <Icon name="notifications" className="text-[16px]" />
          <strong className="font-semibold text-on-surface">{eventos}</strong>
          {eventos === 1 ? 'evento' : 'eventos'}
        </span>
        {riesgoAlto > 0 && (
          <span className="inline-flex items-center gap-base text-error font-semibold">
            <Icon name="priority_high" className="text-[16px]" />
            {riesgoAlto} en riesgo alto (≥{SCORE_UMBRAL_ALTO})
          </span>
        )}
      </div>

      {/* Filas de persona (solo las de mayor riesgo; el resto en el grid del examen) */}
      <ul className="divide-y divide-outline-variant/40">
        {visibles.map((s) => (
          <PersonaVivoRow key={s.id} sesion={s} onAbrir={onAbrir} />
        ))}
      </ul>

      {ocultas > 0 && (
        <button
          type="button"
          onClick={() => examId && onAbrirExamen?.(examId)}
          className="w-full flex items-center justify-center gap-base px-md py-sm border-t border-outline-variant/40
            text-label-md font-semibold text-primary hover:bg-surface-container-low/60 transition-colors"
        >
          Ver las {personas} personas
          <Icon name="arrow_forward" className="text-[18px]" />
        </button>
      )}
    </section>
  );
}

/** Fila compacta de una persona rindiendo, dentro del grupo de examen. */
function PersonaVivoRow({
  sesion,
  onAbrir,
}: {
  sesion: SesionProctoringResumen;
  onAbrir: (sesion: SesionProctoringResumen) => void;
}) {
  const alto = nivelRiesgo(sesion.score) === 'alto';

  return (
    <li>
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
        className={`group flex items-center gap-md pl-sm pr-md py-sm cursor-pointer
          border-l-[3px] ${scoreAccentBorder(sesion.score)}
          transition-colors hover:bg-surface-container-low/60
          focus:outline-none focus-visible:bg-surface-container-low`}
      >
        {/* Identidad de la persona */}
        <div className="min-w-0 flex-1">
          <p className="text-body-md font-semibold text-on-surface truncate">
            {sesion.etiqueta?.trim() || 'Persona sin etiqueta'}
          </p>
          <p className="text-label-sm text-on-surface-variant">
            {formatFechaRelativa(sesion.creada_en)}
          </p>
        </div>

        {/* Métricas inline. ?? 0 evita huecos cuando el backend no envía el campo. */}
        <div className="hidden sm:flex items-center gap-md text-label-sm text-on-surface-variant shrink-0">
          <span className="inline-flex items-center gap-base tabular-nums">
            <Icon name="notifications" className="text-[15px]" />
            {sesion.total_eventos ?? 0}
          </span>
          <span
            className={`inline-flex items-center gap-base tabular-nums ${
              (sesion.total_discrepancias ?? 0) > 0 ? 'text-error font-semibold' : ''
            }`}
          >
            <Icon name="rule" className="text-[15px]" />
            {sesion.total_discrepancias ?? 0}
          </span>
        </div>

        {/* Score chip */}
        <span
          className={`inline-flex items-center justify-center min-w-[44px] px-sm py-base rounded-full
            text-label-sm font-bold tabular-nums shrink-0
            ${alto ? 'bg-error-container text-on-error-container' : 'bg-surface-container-high'} ${scoreTextColor(sesion.score ?? 0)}`}
        >
          {sesion.score ?? 0}
        </span>

        <Icon
          name="chevron_right"
          className="text-[20px] text-on-surface-variant opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
        />
      </div>
    </li>
  );
}

export default ExamenVivoGroup;
