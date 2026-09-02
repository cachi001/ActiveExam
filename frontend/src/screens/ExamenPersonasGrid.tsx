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
import { statProps } from './proctoring/statCatalog';
import { STAFF_NAV } from '../ui/nav';
import { useToast } from '../ui/toast';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { api } from '../lib/api';
import { loadEffectiveConfig } from '../config/effectiveConfigCache';
import type { SesionProctoringResumen } from '../lib/types';
import {
  formatFechaRelativa,
  scoreCardAcento,
  scoreTextColor,
  nivelRiesgo,
  INNER_CHIP_BG,
} from './proctoring/helpers';
import { examInfoDeSesion, subtituloExamen } from './proctoring/colaAgregacion';
import { coincideBusqueda, correoPersona, inicialDe, nombrePersona } from './proctoring/persona';

const POLL_MS = 4000;
const DETALLE_ROUTE = '/admin/proctoring-session-detail';

export default function ExamenPersonasGrid() {
  const navigate = useNavigate();
  const toast = useToast();
  const examId = useApp((s) => s.proctoringExamId);
  const setProctoringSessionId = useApp((s) => s.setProctoringSessionId);
  const setProctoringDetailBackRoute = useApp((s) => s.setProctoringDetailBackRoute);

  const [personas, setPersonas] = useState<SesionProctoringResumen[]>([]);
  const [cargaInicial, setCargaInicial] = useState(true);
  // Buscar por persona. Con 40 rindiendo, encontrar a una scrolleando tarjetas es
  // el momento en que el tutor pierde el examen de vista.
  const [busqueda, setBusqueda] = useState('');
  const enVuelo = useRef(false);
  const toastRef = useRef(toast);
  toastRef.current = toast;

  // Contexto académico del header resuelto SERVER-SIDE (examen_contenido → comisión
  // → materia), tomado de las propias sesiones — igual que la Cola de Revisión. Un
  // examen importado real vive en la base, no en el catálogo mock de api.ts, así que
  // NO se joinea con joinExamInfo(examId): se prefiere lo que ya trae cada sesión.
  const examInfo = useMemo(
    () => (personas.length > 0 ? examInfoDeSesion(personas[0]) : null),
    [personas],
  );

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
    // Sembrar el umbral_cola_revision de la config efectiva antes del primer
    // render, así "Riesgo alto (≥X)" refleja lo que el admin configuró.
    void loadEffectiveConfig();
    void refrescar();
    const id = setInterval(() => void refrescar(), POLL_MS);
    return () => clearInterval(id);
  }, [examId, refrescar]);

  const abrir = (s: SesionProctoringResumen) => {
    setProctoringSessionId(s.id);
    // "Volver" del detalle regresa al grid de personas de este examen.
    setProctoringDetailBackRoute('/proctor/examen');
    navigate(DETALLE_ROUTE + '/' + s.id);
  };

  const eventos = personas.reduce((acc, s) => acc + s.total_eventos, 0);
  const riesgoAlto = personas.filter((s) => nivelRiesgo(s.score, s.umbral_cola_revision_efectivo) === 'alto').length;

  // El buscador filtra la GRILLA, no los totales de arriba: el tutor tiene que
  // seguir viendo cuánta gente hay y cuánto riesgo hay mientras busca a alguien.
  const visibles = useMemo(
    () => personas.filter((s) => coincideBusqueda(s, busqueda)),
    [personas, busqueda],
  );

  return (
    <StaffShell nav={STAFF_NAV} title="Supervisión en vivo">
      <div className="space-y-lg animate-in fade-in duration-500">
        {/* Volver + título del examen */}
        <div className="space-y-sm">
          <button
            onClick={() => navigate('/proctor')}
            className="inline-flex items-center gap-base text-label-md font-semibold text-on-surface-variant hover:text-on-surface transition-colors"
          >
            <Icon name="arrow_back" className="text-[18px]" />
            Volver a supervisión
          </button>
          <div className="flex items-start justify-between gap-md flex-wrap">
            <div className="min-w-0">
              <h1 className="font-headline text-headline-md text-on-surface tracking-tight truncate">
                {examInfo?.examNombre ?? 'Examen en curso'}
              </h1>
              {subtituloExamen(examInfo) && (
                <p className="text-body-md text-on-surface-variant mt-base">
                  {subtituloExamen(examInfo)}
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
          <StatCard icon="group" label="Personas" value={personas.length} sub="rindiendo" tono="primary" />
          <StatCard {...statProps('eventos', eventos)} />
          <StatCard {...statProps('riesgoAlto', riesgoAlto)} />
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

            {/* Buscador de persona. Va acá y no en el panel de filtros porque el
                tutor no tiene ese panel (solo ve su comisión) y es justamente
                quien más necesita encontrar a alguien rápido. */}
            <div className="flex items-center gap-sm mb-md">
              <div className="relative flex-1 max-w-md">
                <Icon
                  name="search"
                  className="absolute left-sm top-1/2 -translate-y-1/2 text-[18px] text-on-surface-variant pointer-events-none"
                />
                <input
                  type="search"
                  value={busqueda}
                  onChange={(e) => setBusqueda(e.target.value)}
                  placeholder="Buscar por nombre o correo…"
                  aria-label="Buscar persona"
                  className="w-full rounded-xl border border-outline-variant/60 bg-surface-container-lowest
                    pl-9 pr-md py-sm text-body-md text-on-surface
                    focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
                />
              </div>
              {busqueda.trim() !== '' && (
                <span className="text-label-sm text-on-surface-variant whitespace-nowrap">
                  {visibles.length} de {personas.length}
                </span>
              )}
            </div>

            {visibles.length === 0 ? (
              <Card className="flex flex-col items-center justify-center text-center gap-sm py-xl">
                <Icon name="person_search" className="text-[28px] text-on-surface-variant" />
                <p className="text-body-md text-on-surface-variant">
                  Ninguna persona coincide con «{busqueda.trim()}».
                </p>
              </Card>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-sm">
                {visibles.map((s) => (
                  <PersonaCard key={s.id} sesion={s} onAbrir={abrir} />
                ))}
              </div>
            )}
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
  const alto = nivelRiesgo(sesion.score, sesion.umbral_cola_revision_efectivo) === 'alto';
  // QUIÉN es. Sale del servidor; la etiqueta del cliente es solo el fallback.
  const nombre = nombrePersona(sesion);
  const discrepancias = sesion.total_discrepancias ?? 0;

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
      className={`group cursor-pointer rounded-xl border ${scoreCardAcento(sesion.score, sesion.umbral_cola_revision_efectivo)}
        p-sm shadow-card transition-all duration-200
        hover:shadow-card-lg hover:-translate-y-px focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40
        ${alto ? 'ring-1 ring-error/30' : ''}`}
    >
      <div className="flex items-center justify-between gap-sm">
        <div className="flex items-center gap-sm min-w-0">
          <div className="w-8 h-8 rounded-full bg-white/70 text-primary flex items-center justify-center text-label-md font-semibold shrink-0">
            {inicialDe(sesion)}
          </div>
          <div className="min-w-0">
            <p className="text-body-md font-semibold text-on-surface truncate" title={nombre}>
              {nombre}
            </p>
            <p className="text-label-sm text-on-surface-variant truncate">
              {/* Correo, NO `alumno_idnumber`: ese es el username, y para quien
                  entra por el campus vale "lti:1:7". Acá no se maneja legajo. */}
              {correoPersona(sesion) ? `${correoPersona(sesion)} · ` : ''}
              {formatFechaRelativa(sesion.creada_en)}
            </p>
          </div>
        </div>
        <span
          className={`inline-flex items-center justify-center min-w-[40px] px-sm py-base rounded-full
            text-label-sm font-bold tabular-nums shrink-0 ${INNER_CHIP_BG} ${scoreTextColor(sesion.score, sesion.umbral_cola_revision_efectivo)}`}
        >
          {sesion.score}
        </span>
      </div>

      {/* Métricas en una línea: con 40 tarjetas en pantalla, dos cajas por tarjeta
          eran ruido y obligaban a scrollear para barrer a la gente. */}
      <div className="flex items-center gap-sm mt-sm text-label-sm text-on-surface-variant">
        <span className="inline-flex items-center gap-base">
          <Icon name="notifications" className="text-[15px]" />
          {sesion.total_eventos ?? 0}
        </span>
        <span
          className={`inline-flex items-center gap-base ${discrepancias > 0 ? 'text-error font-semibold' : ''}`}
        >
          <Icon name="rule" className="text-[15px]" />
          {discrepancias}
        </span>
        {sesion.es_prueba && (
          <span className="inline-flex items-center gap-base text-warning font-semibold">
            <Icon name="science" className="text-[15px]" />
            Prueba
          </span>
        )}
        <Icon
          name="arrow_forward"
          className="text-[16px] ml-auto opacity-0 group-hover:opacity-100 transition-opacity"
        />
      </div>
    </div>
  );
}
