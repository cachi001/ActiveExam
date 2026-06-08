/**
 * Proctor — Supervisión EN VIVO de sesiones de proctoring (conectada al backend).
 *
 * Ruta: /proctor (nav: "Supervisión en vivo"). Sondea el backend slim cada
 * POLL_MS vía api.listarSesionesProctoring() (dual real/mock) y muestra las
 * sesiones ordenadas por score descendente: las de mayor riesgo, arriba.
 *
 * Tiempo real por polling: setInterval con cleanup en el unmount (sin acumular
 * timers). Degradación silenciosa: si un refresh falla, se muestra un toast pero
 * el loop sigue vivo y se mantiene la última data visible.
 *
 * L2.5: el score PRIORIZA para revisión humana, nunca sanciona. Click en una
 * sesión abre su detalle para la decisión humana asíncrona.
 * Ley 25.326: este panel solo lista metadatos agregados; no toca screenshots.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Card, Button, Icon, SectionTitle } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { STAFF_NAV } from '../ui/nav';
import { useToast } from '../ui/toast';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import type { SesionProctoringResumen } from '../lib/types';
import { SesionVivoCard } from './proctoring/SesionVivoCard';
import { ExamenVivoGroup } from './proctoring/ExamenVivoGroup';
import { ResumenVivo } from './proctoring/ResumenVivo';
import { ListaSkeleton, ListaVaciaVivo } from './proctoring/ListaEstados';
import { IndicadorVivo } from './proctoring/IndicadorVivo';
import { joinExamInfo, type ExamInfo } from './proctoring/helpers';

export const PROCTOR_NAV = STAFF_NAV;

/** Intervalo de polling del panel en vivo (ms). */
const POLL_MS = 4000;
const PROCTORING_DETAIL_ROUTE = '/admin/proctoring-session-detail';

/** Ordena por score desc (mayor riesgo arriba); desempata por más eventos. */
function ordenarPorRiesgo(sesiones: SesionProctoringResumen[]): SesionProctoringResumen[] {
  return [...sesiones].sort(
    (a, b) => b.score - a.score || b.total_eventos - a.total_eventos,
  );
}

export default function Proctor() {
  const navigate = useNavigate();
  const toast = useToast();
  const setProctoringSessionId = useApp((s) => s.setProctoringSessionId);
  const setProctoringExamId = useApp((s) => s.setProctoringExamId);

  const [sesiones, setSesiones] = useState<SesionProctoringResumen[]>([]);
  const [cargaInicial, setCargaInicial] = useState(true);
  const [refrescando, setRefrescando] = useState(false);
  const [ultimoRefresh, setUltimoRefresh] = useState<number | null>(null);

  // Evita refrescos solapados (el manual y el del intervalo) y stale closures.
  const enVuelo = useRef(false);
  const toastRef = useRef(toast);
  toastRef.current = toast;

  const refrescar = useCallback(async (manual: boolean) => {
    if (enVuelo.current) return;
    enVuelo.current = true;
    if (manual) setRefrescando(true);
    try {
      const data = await api.listarSesionesProctoring();
      // Supervisión EN VIVO: solo sesiones que todavía no fueron finalizadas.
      // Las cerradas (finalizada_en != null) viven en /admin/proctoring-sessions.
      const enVivo = data.filter((s) => !s.finalizada_en);
      setSesiones(ordenarPorRiesgo(enVivo));
      setUltimoRefresh(Date.now());
    } catch {
      // Degradación silenciosa: avisamos pero NO rompemos el loop ni borramos
      // la última data visible. El próximo tick reintenta solo.
      toastRef.current.error('No se pudieron actualizar las sesiones en vivo');
    } finally {
      enVuelo.current = false;
      if (manual) setRefrescando(false);
      setCargaInicial(false);
    }
  }, []);

  // Polling con cleanup: una sola carga inicial + un único intervalo que se
  // limpia en el unmount (sin acumular timers entre renders).
  useEffect(() => {
    void refrescar(false);
    const id = setInterval(() => void refrescar(false), POLL_MS);
    return () => clearInterval(id);
  }, [refrescar]);

  const handleAbrir = (sesion: SesionProctoringResumen) => {
    setProctoringSessionId(sesion.id);
    navigate(PROCTORING_DETAIL_ROUTE);
  };

  const handleAbrirExamen = (examId: string) => {
    setProctoringExamId(examId);
    navigate('/proctor/examen');
  };

  // Particiona por modo y AGRUPA los exámenes por exam_id: primero el examen
  // concreto que se está rindiendo, y dentro sus personas (arquitectura correcta).
  const { gruposExamen, diagnostico, otras } = useMemo(() => {
    const examen: SesionProctoringResumen[] = [];
    const diagnostico: SesionProctoringResumen[] = [];
    const otras: SesionProctoringResumen[] = [];
    for (const s of sesiones) {
      if (s.modo === 'examen') examen.push(s);
      else if (s.modo === 'diagnostico') diagnostico.push(s);
      else otras.push(s);
    }

    // Agrupa las sesiones de examen por exam_id (las sin id caen en un grupo aparte).
    const porExamen = new Map<string, { examInfo: ExamInfo | null; sesiones: SesionProctoringResumen[] }>();
    for (const s of examen) {
      const key = s.exam_id ?? '__sin_examen__';
      if (!porExamen.has(key)) porExamen.set(key, { examInfo: joinExamInfo(s.exam_id), sesiones: [] });
      porExamen.get(key)!.sesiones.push(s);
    }
    // Ordena los grupos por su riesgo máximo (el examen más caliente, arriba).
    const gruposExamen = [...porExamen.entries()]
      .map(([examId, g]) => ({ examId, ...g, riesgoMax: Math.max(...g.sesiones.map((s) => s.score)) }))
      .sort((a, b) => b.riesgoMax - a.riesgoMax);

    return { gruposExamen, diagnostico, otras };
  }, [sesiones]);

  const examenesActivos = gruposExamen.length;

  return (
    <StaffShell nav={PROCTOR_NAV} title="Supervisión en vivo">
      <div className="space-y-lg animate-in fade-in duration-500">
        {/* Header: título + indicador en vivo + refresco manual */}
        <div className="flex items-start justify-between gap-md flex-wrap">
          <div>
            <div className="flex items-center gap-sm">
              <h1 className="font-headline text-headline-md text-on-surface tracking-tight">
                Supervisión en vivo
              </h1>
              <HelpButton title="Supervisión en vivo">
                <p>
                  Acá ves las sesiones de proctoring <strong>en curso</strong> agrupadas por examen.
                  Las sesiones que ya finalizaron viven en <em>Sesiones grabadas</em>.
                </p>
                <p>
                  Los exámenes con mayor riesgo aparecen arriba. Click en un examen para ver el grid
                  de personas; click en una persona para abrir su detalle y revisar evidencia.
                </p>
                <p>
                  El panel <strong>nunca sanciona automáticamente</strong>: el score solo prioriza la
                  revisión humana. La decisión disciplinaria siempre es del revisor.
                </p>
              </HelpButton>
            </div>
            <p className="text-body-md text-on-surface-variant mt-base">
              Los exámenes con mayor riesgo se muestran primero.
            </p>
          </div>
          <div className="flex items-center gap-sm">
            <IndicadorVivo ultimoRefresh={ultimoRefresh} activo={!refrescando} />
            <Button
              variant="outline"
              size="sm"
              icon="refresh"
              onClick={() => void refrescar(true)}
              disabled={refrescando}
            >
              {refrescando ? 'Actualizando…' : 'Actualizar'}
            </Button>
          </div>
        </div>

        {/* Resumen agregado del lote actual */}
        {!cargaInicial && sesiones.length > 0 && <ResumenVivo sesiones={sesiones} />}

        {/* Secciones diferenciadas por modo */}
        <Card className="space-y-lg">
          <div className="flex items-center justify-between gap-md text-label-sm text-on-surface-variant border-b border-outline-variant/40 pb-sm">
            <span>
              {cargaInicial
                ? 'Conectando…'
                : `${sesiones.length} sesión${sesiones.length !== 1 ? 'es' : ''} en vivo`}
            </span>
            <span className="inline-flex items-center gap-base">
              <Icon name="bolt" className="text-[16px]" />
              actualiza cada {POLL_MS / 1000}s
            </span>
          </div>

          {cargaInicial && <ListaSkeleton />}

          {!cargaInicial && sesiones.length === 0 && <ListaVaciaVivo />}

          {!cargaInicial && sesiones.length > 0 && (
            <div className="space-y-lg">
              {gruposExamen.length > 0 && (
                <section className="space-y-sm">
                  <SectionTitle
                    sub={`${examenesActivos} examen${examenesActivos !== 1 ? 'es' : ''} activo${examenesActivos !== 1 ? 's' : ''}`}
                  >
                    Exámenes en curso
                  </SectionTitle>
                  <div className="space-y-md">
                    {gruposExamen.map((g) => (
                      <ExamenVivoGroup
                        key={g.examId}
                        examInfo={g.examInfo}
                        sesiones={g.sesiones}
                        onAbrir={handleAbrir}
                        onAbrirExamen={handleAbrirExamen}
                      />
                    ))}
                  </div>
                </section>
              )}

              {diagnostico.length > 0 && (
                <section className="space-y-sm">
                  <SectionTitle sub={`${diagnostico.length} sesión${diagnostico.length !== 1 ? 'es' : ''} de prueba`}>
                    Pruebas de detección
                  </SectionTitle>
                  {diagnostico.map((s) => (
                    <SesionVivoCard key={s.id} sesion={s} onAbrir={handleAbrir} />
                  ))}
                </section>
              )}

              {otras.length > 0 && (
                <section className="space-y-sm">
                  <SectionTitle sub={`${otras.length} sesión${otras.length !== 1 ? 'es' : ''}`}>
                    Otras
                  </SectionTitle>
                  {otras.map((s) => (
                    <SesionVivoCard key={s.id} sesion={s} onAbrir={handleAbrir} />
                  ))}
                </section>
              )}
            </div>
          )}
        </Card>
      </div>
    </StaffShell>
  );
}
