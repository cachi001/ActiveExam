/**
 * ExamenPersonasGrid — Drill-down de un examen en supervisión en vivo.
 *
 * Al clickear un examen en /proctor, se entra acá: un GRID con todas las personas
 * que lo están rindiendo, cada una con su situación de un vistazo (score, eventos,
 * discrepancias, riesgo). Click en una persona → detalle completo de su sesión.
 *
 * Tiempo real por polling (igual que Proctor). L2.5: el score PRIORIZA, nunca sanciona.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Card, Icon, SectionTitle } from '../ui/components';
import { StatCard } from './proctoring/StatCard';
import { STAFF_NAV } from '../ui/nav';
import { useToast } from '../ui/toast';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import type { SesionProctoringResumen } from '../lib/types';
import {
  formatFechaRelativa,
  scoreAccentBorder,
  scoreTextColor,
  nivelRiesgo,
  SCORE_UMBRAL_ALTO,
  joinExamInfo,
} from './proctoring/helpers';

const POLL_MS = 4000;
const DETALLE_ROUTE = '/admin/proctoring-session-detail';

export default function ExamenPersonasGrid() {
  const navigate = useNavigate();
  const toast = useToast();
  const examId = useApp((s) => s.proctoringExamId);
  const setProctoringSessionId = useApp((s) => s.setProctoringSessionId);

  const [personas, setPersonas] = useState<SesionProctoringResumen[]>([]);
  const [cargaInicial, setCargaInicial] = useState(true);
  const enVuelo = useRef(false);
  const toastRef = useRef(toast);
  toastRef.current = toast;

  const examInfo = useMemo(() => joinExamInfo(examId), [examId]);

  const refrescar = useCallback(async () => {
    if (enVuelo.current) return;
    enVuelo.current = true;
    try {
      const data = await api.listarSesionesProctoring();
      // Drill-down de supervisión EN VIVO: solo personas con sesión sin finalizar.
      const delExamen = data
        .filter((s) => s.exam_id === examId && !s.finalizada_en)
        .sort((a, b) => b.score - a.score || b.total_eventos - a.total_eventos);
      setPersonas(delExamen);
    } catch {
      toastRef.current.error('No se pudieron actualizar las personas');
    } finally {
      enVuelo.current = false;
      setCargaInicial(false);
    }
  }, [examId]);

  useEffect(() => {
    if (!examId) return;
    void refrescar();
    const id = setInterval(() => void refrescar(), POLL_MS);
    return () => clearInterval(id);
  }, [examId, refrescar]);

  const abrir = (s: SesionProctoringResumen) => {
    setProctoringSessionId(s.id);
    navigate(DETALLE_ROUTE);
  };

  const eventos = personas.reduce((acc, s) => acc + s.total_eventos, 0);
  const riesgoAlto = personas.filter((s) => nivelRiesgo(s.score) === 'alto').length;

  return (
    <StaffShell nav={STAFF_NAV} title="Supervisión en vivo">
      <div className="space-y-lg animate-in fade-in duration-500">
        {/* Volver + título del examen */}
        <div className="space-y-sm">
          <button
            onClick={() => navigate('/proctor')}
            className="inline-flex items-center gap-base text-label-md font-semibold text-primary hover:underline"
          >
            <Icon name="arrow_back" className="text-[18px]" />
            Volver a supervisión
          </button>
          <div className="flex items-start justify-between gap-md flex-wrap">
            <div className="min-w-0">
              <h1 className="font-headline text-headline-md text-on-surface tracking-tight truncate">
                {examInfo?.examNombre ?? 'Examen en curso'}
              </h1>
              {examInfo && (
                <p className="text-body-md text-on-surface-variant mt-base">
                  {examInfo.comisionNombre} · {examInfo.docente}
                </p>
              )}
            </div>
            <span className="inline-flex items-center gap-base text-label-sm font-semibold text-success">
              <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
              En vivo
            </span>
          </div>
        </div>

        {/* Resumen del examen */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-md">
          <StatCard icon="group" label="Personas" value={personas.length} tono="primary" />
          <StatCard icon="notifications" label="Eventos" value={eventos} tono="info" />
          <StatCard
            icon="priority_high"
            label={`Riesgo alto (≥${SCORE_UMBRAL_ALTO})`}
            value={riesgoAlto}
            tono={riesgoAlto > 0 ? 'error' : 'success'}
          />
        </div>

        {/* Grid de personas */}
        {cargaInicial ? (
          <Card className="flex items-center justify-center gap-sm py-xl text-on-surface-variant">
            <Icon name="progress_activity" className="ae-spin text-[22px]" />
            <span className="text-label-md">Cargando personas…</span>
          </Card>
        ) : personas.length === 0 ? (
          <Card className="flex flex-col items-center justify-center text-center gap-md py-xxl">
            <div className="w-14 h-14 rounded-2xl bg-surface-container-high text-on-surface-variant flex items-center justify-center">
              <Icon name="group_off" className="text-[28px]" />
            </div>
            <p className="text-body-md text-on-surface-variant max-w-sm">
              No hay personas rindiendo este examen en este momento.
            </p>
          </Card>
        ) : (
          <div>
            <SectionTitle sub={`${personas.length} ${personas.length === 1 ? 'persona' : 'personas'} · actualiza cada ${POLL_MS / 1000}s`}>
              Personas en curso
            </SectionTitle>
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-md">
              {personas.map((s) => (
                <PersonaCard key={s.id} sesion={s} onAbrir={abrir} />
              ))}
            </div>
          </div>
        )}
      </div>
    </StaffShell>
  );
}

function PersonaCard({
  sesion,
  onAbrir,
}: {
  sesion: SesionProctoringResumen;
  onAbrir: (s: SesionProctoringResumen) => void;
}) {
  const alto = nivelRiesgo(sesion.score) === 'alto';
  const etiqueta = sesion.etiqueta?.trim() || 'Persona sin etiqueta';

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
      className={`group cursor-pointer rounded-2xl bg-surface-container-lowest border border-outline-variant/70
        border-l-4 ${scoreAccentBorder(sesion.score)} p-md shadow-card transition-all duration-200
        hover:shadow-card-lg hover:-translate-y-px focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40
        ${alto ? 'ring-1 ring-error/30' : ''}`}
    >
      <div className="flex items-start justify-between gap-sm">
        <div className="flex items-center gap-sm min-w-0">
          <div className="w-10 h-10 rounded-full bg-primary-fixed text-primary flex items-center justify-center font-semibold shrink-0">
            {etiqueta.charAt(0).toUpperCase()}
          </div>
          <div className="min-w-0">
            <p className="text-body-md font-semibold text-on-surface truncate">{etiqueta}</p>
            <p className="text-label-sm text-on-surface-variant">{formatFechaRelativa(sesion.creada_en)}</p>
          </div>
        </div>
        <span
          className={`inline-flex items-center justify-center min-w-[44px] px-sm py-base rounded-full
            text-label-sm font-bold tabular-nums shrink-0
            ${alto ? 'bg-error-container text-on-error-container' : 'bg-surface-container-high'} ${scoreTextColor(sesion.score)}`}
        >
          {sesion.score}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-sm mt-md">
        <Metrica icon="notifications" label="Eventos" valor={sesion.total_eventos ?? 0} />
        <Metrica
          icon="rule"
          label="Discrepancias"
          valor={sesion.total_discrepancias ?? 0}
          alerta={(sesion.total_discrepancias ?? 0) > 0}
        />
      </div>

      <div className="flex items-center justify-end gap-base mt-md text-label-md font-semibold text-primary opacity-0 group-hover:opacity-100 transition-opacity">
        Ver detalle
        <Icon name="arrow_forward" className="text-[18px]" />
      </div>
    </div>
  );
}

function Metrica({ icon, label, valor, alerta = false }: { icon: string; label: string; valor: number; alerta?: boolean }) {
  return (
    <div className="rounded-xl bg-surface-container-low border border-outline-variant/40 p-sm">
      <p className="inline-flex items-center gap-base text-label-sm text-on-surface-variant">
        <Icon name={icon} className="text-[15px]" /> {label}
      </p>
      <p className={`font-headline text-title-lg font-bold tabular-nums ${alerta ? 'text-error' : 'text-on-surface'}`}>{valor}</p>
    </div>
  );
}
