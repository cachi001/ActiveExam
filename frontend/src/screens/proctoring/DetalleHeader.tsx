/**
 * DetalleHeader — Encabezado del detalle de sesión: metadata + stat-cards.
 *
 * Layout en 2 columnas: la IZQUIERDA concentra todo lo que no es el score
 * (quién rindió, qué examen/materia/comisión, eventos/discrepancias, barra de
 * priorización); la DERECHA es el score — el dato que más importa para
 * priorizar la revisión — ocupando todo el alto del sector, bien grande.
 */
import { Icon, Card } from '../../ui/components';
import type { SesionProctoringDetalle } from '../../lib/types';
import {
  formatFecha,
  scoreTextColor,
  gaugeFill,
  nivelRiesgo,
} from './helpers';

const NIVEL_LABEL = { bajo: 'Riesgo bajo', medio: 'Riesgo medio', alto: 'Riesgo alto' } as const;

const TONO_BG: Record<'error' | 'warning' | 'success', string> = {
  error: 'bg-gradient-to-br from-error-500 to-error-600',
  warning: 'bg-gradient-to-br from-warning-500 to-warning-600',
  success: 'bg-gradient-to-br from-success-500 to-success-600',
};

export function DetalleHeader({ detalle }: { detalle: SesionProctoringDetalle }) {
  const nivel = nivelRiesgo(detalle.score, detalle.umbral_cola_revision_efectivo);
  const totalEventos = detalle.eventos?.length ?? detalle.total_eventos ?? 0;
  const totalDiscrepancias =
    detalle.eventos?.filter((e) => e.veredicto_reinferencia === 'discrepancia').length ??
    detalle.total_discrepancias ??
    0;

  const scoreTono: 'error' | 'warning' | 'success' =
    nivel === 'alto' ? 'error' : nivel === 'medio' ? 'warning' : 'success';

  // Contexto académico resuelto server-side (examen_contenido → comisión →
  // materia). Puede faltar en sesiones de harness/test sin examen real.
  const tieneContexto = Boolean(detalle.examen_titulo || detalle.materia_nombre || detalle.comision_nombre);

  // Identidad del alumno: nombre resuelto server-side, con fallback a
  // idnumber/email crudos (sesiones legacy o usuario sin nombre cargado).
  const nombreAlumno = detalle.alumno_nombre?.trim() || detalle.alumno_idnumber || detalle.alumno_email;

  return (
    // Sin padding propio + overflow-hidden: el panel de score de la derecha
    // bordea el card entero (alto y ancho completos), no queda flotando con
    // aire alrededor.
    <Card padded={false} className="overflow-hidden">
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_200px] items-stretch">
        {/* ── IZQUIERDA: todo salvo el score ── */}
        <div className="p-lg space-y-md min-w-0">
          {/* Quién rindió — es el primer dato que el revisor necesita, grande.
              Sin badge de "modo" ni etiqueta interna: son metadata técnica de la
              sesión (no aporta al revisor) — lo que importa es quién + qué examen
              (la card de abajo) + cuándo. */}
          <div className="space-y-xs min-w-0">
            <h1 className="font-headline text-headline-lg text-on-surface tracking-tight truncate">
              {nombreAlumno || 'Alumno sin identificar'}
            </h1>
            <div className="flex items-center gap-md flex-wrap text-label-sm text-on-surface-variant">
              <span className="inline-flex items-center gap-base">
                <Icon name="schedule" className="text-[14px]" />
                {formatFecha(detalle.creada_en, true)}
              </span>
              <span className="text-outline-variant" aria-hidden>·</span>
              <span className="inline-flex items-center gap-base font-mono text-[11px]" title={detalle.id}>
                <Icon name="fingerprint" className="text-[14px]" />
                {detalle.id.slice(0, 20)}…
              </span>
            </div>
          </div>

          {/* Qué examen rindió y de qué materia/comisión — el contexto académico
              es lo primero que el revisor necesita saber, junto con quién es. */}
          {tieneContexto && (
            <div className="flex items-center gap-sm rounded-xl border border-primary/20 bg-primary-fixed/15 px-md py-sm flex-wrap">
              <div className="w-9 h-9 rounded-lg bg-primary/15 flex items-center justify-center shrink-0">
                <Icon name="assignment" className="text-[18px] text-primary" fill />
              </div>
              <div className="min-w-0">
                <p className="text-label-md font-semibold text-on-surface truncate">
                  {detalle.examen_titulo?.trim() || 'Examen sin título'}
                </p>
                <p className="text-label-sm text-on-surface-variant truncate">
                  {[detalle.materia_nombre, detalle.comision_nombre].filter(Boolean).join(' · ') || 'Sin materia/comisión asignada'}
                </p>
              </div>
            </div>
          )}

          {/* Stats: eventos y discrepancias — ARRIBA de la barra de score, mismo
              tratamiento visual (borde-2) para que pesen igual. */}
          <div className="grid grid-cols-2 gap-md">
            <div className="rounded-xl border-2 border-info/40 bg-info/5 px-md py-sm flex items-center gap-sm">
              <div className="w-9 h-9 rounded-lg bg-info/15 flex items-center justify-center shrink-0">
                <Icon name="notifications" className="text-[18px] text-info" fill />
              </div>
              <div className="min-w-0">
                <p className="text-2xl font-bold text-on-surface leading-tight tabular-nums">{totalEventos}</p>
                <p className="text-[11px] font-semibold text-on-surface-variant">Eventos</p>
              </div>
            </div>
            {/* Discrepancias — color sólido y saturado SIEMPRE (no solo cuando > 0):
                es una de las dos señales principales del expediente junto con
                Eventos, tiene que destacar igual de fuerte aunque el conteo sea 0. */}
            <div className={`rounded-xl border-2 px-md py-sm flex items-center gap-sm ${
              totalDiscrepancias > 0
                ? 'border-error/50 bg-error/10'
                : 'border-warning/50 bg-warning/10'
            }`}>
              <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${
                totalDiscrepancias > 0 ? 'bg-error/20' : 'bg-warning/20'
              }`}>
                <Icon name="rule" className={`text-[18px] ${totalDiscrepancias > 0 ? 'text-error' : 'text-warning-700'}`} fill />
              </div>
              <div className="min-w-0">
                <p className={`text-2xl font-bold leading-tight tabular-nums ${totalDiscrepancias > 0 ? 'text-error' : 'text-warning-700'}`}>
                  {totalDiscrepancias}
                </p>
                <p className="text-[11px] font-semibold text-on-surface-variant">Discrepancias</p>
              </div>
            </div>
          </div>

          {/* Barra de score */}
          <div className="space-y-xs">
            <div className="flex items-center justify-between text-label-sm">
              <span className="text-on-surface-variant">Score de riesgo</span>
              <span className={`font-semibold ${scoreTextColor(detalle.score, detalle.umbral_cola_revision_efectivo)}`}>{detalle.score} / 100 pts</span>
            </div>
            <div className="bg-surface-container-high rounded-full h-2 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${gaugeFill(detalle.score)}`}
                style={{ width: `${Math.min(100, Math.max(0, detalle.score))}%` }}
                role="progressbar"
                aria-valuenow={detalle.score}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Score de riesgo"
              />
            </div>
          </div>
        </div>

        {/* ── DERECHA: score, ocupa TODO el sector (alto y ancho completos) ── */}
        <div className={`flex flex-col items-center justify-center text-white text-center p-lg ${TONO_BG[scoreTono]}`}>
          <p className="text-[13px] font-semibold text-white/85 uppercase tracking-wider">Score</p>
          <p className="text-7xl font-bold leading-none mt-sm tabular-nums">{detalle.score}</p>
          <p className="text-[15px] font-medium text-white/90 mt-sm">{NIVEL_LABEL[nivel]}</p>
        </div>
      </div>
    </Card>
  );
}

export default DetalleHeader;
