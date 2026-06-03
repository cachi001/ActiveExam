/**
 * Revisor — Cola de revisión humana (conectada al backend slim).
 *
 * Ruta: /revisor. Lista las sesiones de proctoring REALES
 * (api.listarSesionesProctoring(), dual real/mock) filtradas por ALTO RIESGO
 * (score ≥ UMBRAL_COLA_REVISION) y priorizadas para decisión humana. Cada ítem
 * se enriquece con el contexto académico (materia/comisión/docente) joineado
 * desde el catálogo local via exam_id.
 *
 * El sistema NUNCA sanciona automáticamente: el score solo prioriza para revisión.
 * La decisión disciplinaria es siempre del revisor humano; la plataforma registra
 * esa decisión localmente (el backend slim no tiene tabla de decisiones).
 * Ley 25.326: la cola no lista screenshots; el detalle sensible vive en
 * ProctoringSessionDetail.
 */
import { useEffect, useMemo, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Card, Badge, Button, SectionTitle } from '../ui/components';
import { api } from '../lib/api';
import { useApp } from '../lib/store';
import { useNavigate } from '../lib/router';
import { STAFF_NAV } from '../ui/nav';
import { useToast } from '../ui/toast';
import type { SesionProctoringResumen, DecisionRevisor } from '../lib/types';
import {
  joinExamInfo,
  scoreTextColor,
  formatFechaRelativa,
  type ExamInfo,
} from './proctoring/helpers';

export const REVISOR_NAV = STAFF_NAV;

/** Score mínimo para que una sesión aparezca en la cola de revisión priorizada. */
const UMBRAL_COLA_REVISION = 60;
const PROCTORING_DETAIL_ROUTE = '/admin/proctoring-session-detail';

/** Etiqueta legible de cada decisión humana (para el toast de confirmación). */
const DECISION_LABEL: Record<DecisionRevisor, string> = {
  sin_hallazgos: 'Sin hallazgos',
  aprobado: 'Aprobado con observación',
  flaggeado_para_sumario: 'Flaggeado para sumario',
  pendiente: 'Pendiente',
};

/** Ordena por score desc (mayor riesgo primero); desempata por más discrepancias. */
function ordenarPorRiesgo(sesiones: SesionProctoringResumen[]): SesionProctoringResumen[] {
  return [...sesiones].sort(
    (a, b) => b.score - a.score || b.total_discrepancias - a.total_discrepancias,
  );
}

export default function Revisor() {
  const navigate = useNavigate();
  const toast = useToast();
  const setProctoringSessionId = useApp((s) => s.setProctoringSessionId);
  const setDecisionRevisor = useApp((s) => s.setDecisionRevisor);

  const [cola, setCola] = useState<SesionProctoringResumen[]>([]);
  const [selId, setSelId] = useState<string | null>(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    setCargando(true);
    api
      .listarSesionesProctoring()
      .then((data) => {
        const altoRiesgo = ordenarPorRiesgo(
          data.filter((s) => s.score >= UMBRAL_COLA_REVISION),
        );
        setCola(altoRiesgo);
        setSelId((cur) => cur ?? altoRiesgo[0]?.id ?? null);
      })
      .catch(() => setCola([]))
      .finally(() => setCargando(false));
  }, []);

  const sel = useMemo(() => cola.find((s) => s.id === selId) ?? null, [cola, selId]);
  const examInfo = useMemo<ExamInfo | null>(
    () => (sel ? joinExamInfo(sel.exam_id) : null),
    [sel],
  );

  const resolver = (decision: DecisionRevisor) => {
    if (!sel) return;
    setDecisionRevisor(sel.id, decision);
    toast.success(
      `Decisión registrada: ${DECISION_LABEL[decision]}. El score prioriza; el revisor decide.`,
    );
    const restantes = cola.filter((s) => s.id !== sel.id);
    setCola(restantes);
    setSelId(restantes[0]?.id ?? null);
  };

  const verDetalle = (sesion: SesionProctoringResumen) => {
    setProctoringSessionId(sesion.id);
    navigate(PROCTORING_DETAIL_ROUTE);
  };

  return (
    <StaffShell nav={REVISOR_NAV} title="Cola de revisión">
      <div className="space-y-lg animate-in fade-in duration-500">
        {/* Header */}
        <div className="flex items-start justify-between gap-md flex-wrap">
          <div>
            <h1 className="font-headline text-headline-md text-on-surface tracking-tight">
              Cola de revisión humana
            </h1>
            <p className="text-body-md text-on-surface-variant mt-base">
              Sesiones de alto riesgo (score ≥ {UMBRAL_COLA_REVISION}) priorizadas para
              revisión. El sistema nunca sanciona: la decisión es siempre tuya.
            </p>
          </div>
          <div className="flex items-center gap-base px-sm py-base rounded-lg bg-primary-fixed/50
            border border-primary/20 text-label-sm text-on-primary-fixed-variant">
            <Icon name="shield" className="text-[16px] shrink-0" fill />
            <span>Decisión humana</span>
          </div>
        </div>

        <div className="grid lg:grid-cols-3 gap-lg">
          {/* Cola */}
          <Card className="space-y-base">
            <SectionTitle action={<Badge tone="error" dot>{cola.length} pendientes</Badge>}>
              Cola de sesiones
            </SectionTitle>

            {cargando && (
              <div className="text-center py-xl text-on-surface-variant">
                <Icon name="hourglass_empty" className="text-[32px] animate-pulse" />
                <p className="text-label-md mt-base">Cargando cola…</p>
              </div>
            )}

            {!cargando && cola.length === 0 && (
              <div className="text-center py-xl text-on-surface-variant space-y-base">
                <Icon name="inbox" className="text-[40px]" />
                <p className="text-label-md">
                  ¡Cola limpia! No hay sesiones con score ≥ {UMBRAL_COLA_REVISION} pendientes
                  de revisión.
                </p>
              </div>
            )}

            {!cargando &&
              cola.map((s) => (
                <ColaItem
                  key={s.id}
                  sesion={s}
                  examInfo={joinExamInfo(s.exam_id)}
                  selected={selId === s.id}
                  onClick={() => setSelId(s.id)}
                />
              ))}
          </Card>

          {/* Detalle + decisión */}
          <div className="lg:col-span-2">
            {sel ? (
              <ColaPanelDecision
                sesion={sel}
                examInfo={examInfo}
                onResolver={resolver}
                onVerDetalle={() => verDetalle(sel)}
              />
            ) : (
              <Card className="text-center py-xl space-y-base">
                <Icon name="task_alt" className="text-success text-[48px]" fill />
                <h3 className="font-headline text-title-lg text-on-surface">¡Cola limpia!</h3>
                <p className="text-body-md text-on-surface-variant">
                  No hay sesiones de alto riesgo pendientes de revisión.
                </p>
              </Card>
            )}
          </div>
        </div>
      </div>
    </StaffShell>
  );
}

/** Ítem de la cola lateral: score, eventos, contexto académico (si lo hay). */
function ColaItem({
  sesion,
  examInfo,
  selected,
  onClick,
}: {
  sesion: SesionProctoringResumen;
  examInfo: ExamInfo | null;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full text-left p-sm rounded-xl border transition-all ${
        selected
          ? 'bg-primary-fixed/40 border-primary-container'
          : 'border-outline-variant/40 hover:bg-surface-container-low'
      }`}
    >
      <div className="flex items-center justify-between gap-base">
        <span className="text-label-md font-semibold text-on-surface truncate">
          {sesion.etiqueta?.trim() || 'Sesión sin etiqueta'}
        </span>
        <Badge tone="error">Score {sesion.score}</Badge>
      </div>
      {examInfo && (
        <p className="text-label-sm text-on-surface-variant truncate">
          {examInfo.materiaNombre} · {examInfo.comisionNombre}
        </p>
      )}
      <p className="text-label-sm text-on-surface-variant mt-base">
        {sesion.id} · {sesion.total_eventos} eventos · {sesion.total_discrepancias} discrepancias
      </p>
    </button>
  );
}

/** Panel de detalle + decisión humana de la sesión seleccionada. */
function ColaPanelDecision({
  sesion,
  examInfo,
  onResolver,
  onVerDetalle,
}: {
  sesion: SesionProctoringResumen;
  examInfo: ExamInfo | null;
  onResolver: (decision: DecisionRevisor) => void;
  onVerDetalle: () => void;
}) {
  return (
    <Card className="space-y-lg">
      {/* Encabezado de la sesión */}
      <div className="flex items-start justify-between border-b border-outline-variant/40 pb-md gap-md flex-wrap">
        <div className="min-w-0">
          <h2 className="font-headline text-headline-md text-on-surface truncate">
            {sesion.etiqueta?.trim() || 'Sesión sin etiqueta'}
          </h2>
          {examInfo ? (
            <p className="text-label-sm text-on-surface-variant mt-base">
              {examInfo.examNombre} · {examInfo.comisionNombre} · {examInfo.docente}
            </p>
          ) : (
            <p className="text-label-sm text-on-surface-variant mt-base">
              Sesión sin examen del catálogo asociado
            </p>
          )}
        </div>
        <div className="text-right shrink-0">
          <p className="text-label-sm uppercase tracking-wide text-on-surface-variant">ID sesión</p>
          <p className="font-mono text-label-md font-bold text-on-surface">{sesion.id}</p>
        </div>
      </div>

      {/* Métricas de priorización */}
      <div className="grid grid-cols-3 gap-sm">
        <Metrica label="Score" valor={String(sesion.score)} clase={scoreTextColor(sesion.score)} />
        <Metrica label="Eventos" valor={String(sesion.total_eventos)} />
        <Metrica
          label="Discrepancias"
          valor={String(sesion.total_discrepancias)}
          clase={sesion.total_discrepancias > 0 ? 'text-error' : 'text-on-surface'}
        />
      </div>

      <p className="text-label-sm text-on-surface-variant inline-flex items-center gap-base">
        <Icon name="schedule" className="text-[15px]" />
        {formatFechaRelativa(sesion.creada_en)}
      </p>

      {/* Link al detalle completo (evidencia + cadena de custodia real) */}
      <button
        type="button"
        onClick={onVerDetalle}
        className="inline-flex items-center gap-base text-label-md font-semibold text-primary
          hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 rounded"
      >
        Ver detalle completo
        <Icon name="arrow_forward" className="text-[18px]" />
      </button>

      {/* Decisión humana */}
      <div className="border-t border-outline-variant/40 pt-md space-y-md">
        <SectionTitle sub="El sistema nunca sanciona. La decisión es tuya.">
          Resolución del revisor
        </SectionTitle>
        <div className="flex flex-wrap gap-sm">
          <Button variant="outline" icon="done" onClick={() => onResolver('sin_hallazgos')}>
            Sin hallazgos
          </Button>
          <Button variant="secondary" icon="flag" onClick={() => onResolver('aprobado')}>
            Aprobar con observación
          </Button>
          <Button variant="danger" icon="gavel" onClick={() => onResolver('flaggeado_para_sumario')}>
            Flaggear para sumario
          </Button>
        </div>
        <p className="text-label-sm text-on-surface-variant">
          La decisión disciplinaria es siempre humana; la plataforma solo la registra. El score
          prioriza la cola, no emite veredicto.
        </p>
      </div>
    </Card>
  );
}

function Metrica({ label, valor, clase = 'text-on-surface' }: { label: string; valor: string; clase?: string }) {
  return (
    <div className="rounded-xl bg-surface-container-low border border-outline-variant/40 p-sm text-center">
      <p className="text-label-sm uppercase tracking-wide text-on-surface-variant">{label}</p>
      <p className={`font-headline text-title-lg font-bold ${clase}`}>{valor}</p>
    </div>
  );
}
