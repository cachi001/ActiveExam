/**
 * ProctoringRevisor — Registro de sesiones de proctoring finalizadas (C-46, C-76 tarea 17).
 *
 * Ruta: /admin/proctoring-sessions (roles: tutor | coordinador | admin_sistema)
 * Tabla con paginación real (GET /proctoring/sessions/registro) y filtros
 * server-side (alumno, examen, rango de fecha, nivel de riesgo). El catálogo de
 * exámenes del filtro sale de GET /proctoring/sessions/registro/examenes — NUNCA
 * hardcodeado en el frontend. Mismo patrón de paginación/filtros que
 * `ResultadosExamenPanel.tsx` (Pagination/PageSizeSelect + FiltrosPanel).
 *
 * L2.5: este módulo NO sanciona automáticamente. El score es un indicador de
 * prioridad para revisión humana. La decisión disciplinaria es siempre del revisor.
 * no se persiste screenshot_base64 en este componente (solo se lista).
 */

import { useCallback, useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Card, Icon, Badge, SectionTitle } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { RefreshBar } from '../ui/RefreshBar';
import { FiltrosPanel } from '../ui/FiltrosPanel';
import { Pagination, PageSizeSelect } from '../ui/Pagination';
import { AdminTable, type AdminColumn } from '../ui/AdminTable';
import { ConfirmModal } from '../ui/ConfirmModal';
import { useToast } from '../ui/toast';
import { STAFF_NAV } from '../ui/nav';
import { useAutoRefresh } from '../lib/useAutoRefresh';
import { useNavigate } from '../lib/router';
import { useApp } from '../lib/store';
import { API_BASE } from '../lib/api';
import { authProvider } from '../lib/authProvider';
import type { SesionProctoringResumen, Materia, Comision } from '../lib/types';
import { listarMateriasFn, listarComisionesFn } from '../lib/examContentBrowse';
import {
  listarRegistroSesionesFn,
  listarExamenesConSesionesFn,
  eliminarSesionTestFn,
  type ExamenConSesiones,
  type NivelRiesgoFiltro,
} from '../lib/proctoringRegistro';
import {
  formatFecha,
  getUmbralAlto,
  nivelRiesgo,
  scoreTextColor,
  SCORE_UMBRAL_MEDIO,
  type NivelRiesgo,
} from './proctoring/helpers';
import { StatCard } from './proctoring/StatCard';
import { statProps } from './proctoring/statCatalog';
import { etiquetaConBaja } from './materias/filtroEstado';

const PROCTORING_DETAIL_ROUTE = '/admin/proctoring-session-detail';
const PAGE_SIZE_DEFAULT = 20;

/** Opciones del filtro CON su rango de score.
 *
 * Antes decían solo "Bajo / Medio / Alto" y no había forma de saber qué
 * significaba cada uno: los cortes viven en el código y nunca se mostraban. El
 * corte alto además es configurable, así que se calcula con el umbral vigente en
 * vez de escribir un número fijo que puede quedar mintiendo.
 */
function nivelRiesgoOpciones(umbralAlto: number): { value: NivelRiesgoFiltro; label: string }[] {
  return [
    { value: 'bajo', label: `Bajo (0 a ${SCORE_UMBRAL_MEDIO - 1})` },
    { value: 'medio', label: `Medio (${SCORE_UMBRAL_MEDIO} a ${umbralAlto - 1})` },
    { value: 'alto', label: `Alto (${umbralAlto} a 100)` },
  ];
}

function riesgoBadgeTone(nivel: NivelRiesgo): 'success' | 'warning' | 'error' {
  if (nivel === 'alto') return 'error';
  if (nivel === 'medio') return 'warning';
  return 'success';
}

function alumnoDisplay(s: SesionProctoringResumen): string {
  return s.alumno_nombre || s.alumno_idnumber || s.alumno_email || '—';
}

function examenDisplay(s: SesionProctoringResumen): string {
  if (s.examen_titulo) return s.examen_titulo;
  return s.etiqueta?.trim() || 'Sin examen asociado';
}

/** Placeholder claro ("—") cuando materia/comisión no vienen resueltas (sesión
 * sin contenido vinculado, o examen sin comisión/materia). C-76 tarea 19.2. */
function materiaComisionDisplay(valor: string | null | undefined): string {
  return valor?.trim() || '—';
}

/** Agregados sobre el TOTAL filtrado (C-76 tarea 19.3/20.4) — vienen SIEMPRE del
 * backend, nunca se recalculan sumando `items` (que solo tiene la página actual).
 * `total_eventos`/`total_discrepancias` (tarea 19) se retiraron en la tarea 20. */
interface AgregadosRegistro {
  riesgo_bajo: number;
  riesgo_medio: number;
  riesgo_alto: number;
  en_cola_revision: number;
}

const AGREGADOS_INICIALES: AgregadosRegistro = {
  riesgo_bajo: 0, riesgo_medio: 0, riesgo_alto: 0, en_cola_revision: 0,
};

function traducirErrorApi(err: unknown): string {
  const status = (err as { status?: number })?.status;
  if (status === 401) return 'Tu sesión expiró. Cerrá sesión, volvé a entrar y reintentá.';
  if (status === 403) return 'No tenés permiso para acceder a esta información.';
  if (status && status >= 500) return 'Error en el servidor. Intentá de nuevo en unos instantes.';
  return 'No se pudo cargar el registro de sesiones. Revisá tu conexión.';
}

function TableSkeleton() {
  return (
    <div className="space-y-2 animate-pulse">
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="h-12 bg-surface-100 rounded-lg" />
      ))}
    </div>
  );
}

interface FiltrosRegistro {
  q: string;
  exam_id: string;
  fecha_desde: string;
  fecha_hasta: string;
  nivel_riesgo: NivelRiesgoFiltro | '';
  materia_id: string;
  comision_id: string;
  /** Mostrar los ENSAYOS del docente, ocultos por defecto (no borrados). */
  incluir_pruebas: boolean;
}

const FILTROS_INICIALES: FiltrosRegistro = {
  q: '', exam_id: '', fecha_desde: '', fecha_hasta: '', nivel_riesgo: '', materia_id: '', comision_id: '',
  incluir_pruebas: false,
};

export default function ProctoringRevisor() {
  const navigate = useNavigate();
  const toast = useToast();
  const setProctoringSessionId = useApp((s) => s.setProctoringSessionId);
  const setProctoringDetailBackRoute = useApp((s) => s.setProctoringDetailBackRoute);

  const [sesiones, setSesiones] = useState<SesionProctoringResumen[]>([]);
  const [total, setTotal] = useState(0);
  const [agregados, setAgregados] = useState<AgregadosRegistro>(AGREGADOS_INICIALES);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(PAGE_SIZE_DEFAULT);
  const [aplicados, setAplicados] = useState<FiltrosRegistro>(FILTROS_INICIALES);

  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | undefined>();

  // Catálogo de exámenes con sesiones (filtro "Examen") — SIEMPRE del backend.
  const [examenes, setExamenes] = useState<ExamenConSesiones[]>([]);

  // Filtro Materia → Comisión en cascada (C-76 tarea 20.7), mismo patrón que Notas.tsx.
  const [materias, setMaterias] = useState<Materia[]>([]);
  const [comisiones, setComisiones] = useState<Comision[]>([]);
  const [cargandoComisiones, setCargandoComisiones] = useState(false);

  // Borrador de filtros (se aplican con "Aplicar filtros", mismo patrón que Notas).
  const [borrQ, setBorrQ] = useState('');
  const [borrExamen, setBorrExamen] = useState('');
  const [borrFechaDesde, setBorrFechaDesde] = useState('');
  const [borrFechaHasta, setBorrFechaHasta] = useState('');
  const [borrNivelRiesgo, setBorrNivelRiesgo] = useState<NivelRiesgoFiltro | ''>('');
  const [borrMateria, setBorrMateria] = useState('');
  const [borrComision, setBorrComision] = useState('');

  // Eliminar sesión de test (C-76 tarea 20.1/20.8) — modal de confirmación.
  const [aBorrar, setABorrar] = useState<SesionProctoringResumen | null>(null);
  const [eliminando, setEliminando] = useState(false);

  const cargar = useCallback((filtros: FiltrosRegistro, paginaActual: number, tamano: number) => {
    setCargando(true);
    setError(null);
    listarRegistroSesionesFn(API_BASE, authProvider.getToken(), {
      q: filtros.q || undefined,
      exam_id: filtros.exam_id || undefined,
      fecha_desde: filtros.fecha_desde || undefined,
      fecha_hasta: filtros.fecha_hasta || undefined,
      nivel_riesgo: filtros.nivel_riesgo || undefined,
      materia_id: filtros.materia_id || undefined,
      comision_id: filtros.comision_id || undefined,
      incluir_pruebas: filtros.incluir_pruebas || undefined,
      page: paginaActual,
      page_size: tamano,
    })
      .then((resp) => {
        setSesiones(resp.items);
        setTotal(resp.total);
        setAgregados({
          riesgo_bajo: resp.riesgo_bajo,
          riesgo_medio: resp.riesgo_medio,
          riesgo_alto: resp.riesgo_alto,
          en_cola_revision: resp.en_cola_revision,
        });
        setLastUpdatedAt(Date.now());
      })
      .catch((err: unknown) => {
        setError(traducirErrorApi(err));
        setSesiones([]);
        setAgregados(AGREGADOS_INICIALES);
      })
      .finally(() => setCargando(false));
  }, []);

  useEffect(() => { cargar(aplicados, page, pageSize); }, [cargar, aplicados, page, pageSize]);

  // Catálogo de exámenes: se carga una sola vez (no depende de filtros/página).
  useEffect(() => {
    listarExamenesConSesionesFn(API_BASE, authProvider.getToken())
      .then(setExamenes)
      .catch(() => setExamenes([]));
  }, []);

  // Materias: una sola vez.
  useEffect(() => {
    listarMateriasFn(API_BASE, authProvider.getToken()).then(setMaterias);
  }, []);

  // Comisiones de la materia elegida (cascada).
  useEffect(() => {
    setBorrComision('');
    setComisiones([]);
    if (!borrMateria) return;
    setCargandoComisiones(true);
    listarComisionesFn(API_BASE, authProvider.getToken(), borrMateria)
      .then(setComisiones)
      .finally(() => setCargandoComisiones(false));
  }, [borrMateria]);

  // Auto-refresh cada 5 min: aparecen sesiones a medida que se finalizan.
  useAutoRefresh(() => cargar(aplicados, page, pageSize), undefined, !cargando);

  const handleAbrir = (sesion: SesionProctoringResumen) => {
    setProctoringSessionId(sesion.id);
    setProctoringDetailBackRoute('/admin/proctoring-sessions');
    navigate(PROCTORING_DETAIL_ROUTE + '/' + sesion.id);
  };

  const handleConfirmarEliminar = async () => {
    if (!aBorrar) return;
    setEliminando(true);
    try {
      await eliminarSesionTestFn(API_BASE, authProvider.getToken(), aBorrar.id);
      toast.success('Sesión de diagnóstico eliminada.');
      setABorrar(null);
      cargar(aplicados, page, pageSize);
    } catch (err: unknown) {
      toast.warning(traducirErrorApi(err));
    } finally {
      setEliminando(false);
    }
  };

  const aplicarFiltros = () => {
    setAplicados({
      q: borrQ.trim(),
      exam_id: borrExamen,
      fecha_desde: borrFechaDesde ? `${borrFechaDesde}T00:00:00` : '',
      fecha_hasta: borrFechaHasta ? `${borrFechaHasta}T23:59:59` : '',
      nivel_riesgo: borrNivelRiesgo,
      materia_id: borrMateria,
      comision_id: borrComision,
      // Se conserva: aplicar una búsqueda no puede apagar el modo de vista sin
      // avisar (el usuario vería desaparecer los ensayos y no sabría por qué).
      incluir_pruebas: aplicados.incluir_pruebas,
    });
    setPage(1);
  };
  const limpiarFiltros = () => {
    setBorrQ('');
    setBorrExamen('');
    setBorrFechaDesde('');
    setBorrFechaHasta('');
    setBorrNivelRiesgo('');
    setBorrMateria('');
    setBorrComision('');
    setAplicados(FILTROS_INICIALES);
    setPage(1);
  };
  const hayFiltrosActivos = Boolean(
    aplicados.q || aplicados.exam_id || aplicados.fecha_desde || aplicados.fecha_hasta ||
    aplicados.nivel_riesgo || aplicados.materia_id || aplicados.comision_id,
  );
  const hayCambiosFiltros =
    borrQ.trim() !== aplicados.q ||
    borrExamen !== aplicados.exam_id ||
    (borrFechaDesde ? `${borrFechaDesde}T00:00:00` : '') !== aplicados.fecha_desde ||
    (borrFechaHasta ? `${borrFechaHasta}T23:59:59` : '') !== aplicados.fecha_hasta ||
    borrNivelRiesgo !== aplicados.nivel_riesgo ||
    borrMateria !== aplicados.materia_id ||
    borrComision !== aplicados.comision_id;

  const filtrosIncluyenPruebas = aplicados.incluir_pruebas;

  const totalPaginas = Math.max(1, Math.ceil(total / pageSize));

  const cols: AdminColumn<SesionProctoringResumen>[] = [
    {
      key: 'alumno',
      header: 'Alumno',
      width: '18%',
      cell: (s) => (
        <div>
          <p className="font-semibold text-gray-900">
            {alumnoDisplay(s)}
            {/* migration 0102: sin esta marca, el ensayo del docente se lee como
                un alumno más que rindió y no tiene nota. */}
            {s.es_prueba && (
              <span
                className="ml-2 align-middle rounded-full bg-surface-200 px-2 py-0.5 text-[11px] font-medium text-on-surface-variant"
                title="El docente probando el examen. No cuenta como rendición ni genera nota."
              >
                prueba
              </span>
            )}
          </p>
          {s.alumno_nombre && (s.alumno_idnumber || s.alumno_email) && (
            <p className="text-xs text-gray-500 mt-0.5">{s.alumno_idnumber || s.alumno_email}</p>
          )}
        </div>
      ),
    },
    {
      key: 'examen',
      header: 'Examen',
      width: '18%',
      cell: (s) => <span className="text-gray-900">{examenDisplay(s)}</span>,
    },
    {
      key: 'materia',
      header: 'Materia',
      width: '13%',
      cell: (s) => <span className="text-gray-700">{materiaComisionDisplay(s.materia_nombre)}</span>,
    },
    {
      key: 'comision',
      header: 'Comisión',
      width: '11%',
      cell: (s) => <span className="text-gray-700">{materiaComisionDisplay(s.comision_nombre)}</span>,
    },
    {
      key: 'fecha',
      header: 'Fecha',
      width: '14%',
      cell: (s) => <span className="text-gray-500">{s.finalizada_en ? formatFecha(s.finalizada_en) : '—'}</span>,
    },
    {
      key: 'eventos',
      header: 'Eventos',
      width: '9%',
      align: 'center',
      headerAlign: 'center',
      cell: (s) => <span className="tabular-nums">{s.total_eventos ?? 0}</span>,
    },
    {
      key: 'discrepancias',
      header: 'Discrepancias',
      width: '11%',
      align: 'center',
      headerAlign: 'center',
      cell: (s) => (
        <span className={`tabular-nums ${(s.total_discrepancias ?? 0) > 0 ? 'text-error font-semibold' : ''}`}>
          {s.total_discrepancias ?? 0}
        </span>
      ),
    },
    {
      key: 'riesgo',
      header: 'Score / riesgo',
      width: '12%',
      align: 'center',
      headerAlign: 'center',
      cell: (s) => {
        const nivel = nivelRiesgo(s.score ?? 0, s.umbral_cola_revision_efectivo);
        return (
          <div className="inline-flex items-center gap-2">
            <span className={`font-bold tabular-nums ${scoreTextColor(s.score ?? 0, s.umbral_cola_revision_efectivo)}`}>{s.score ?? 0}</span>
            <Badge tone={riesgoBadgeTone(nivel)}>{nivel}</Badge>
          </div>
        );
      },
    },
    {
      key: 'acciones',
      header: 'Acción',
      width: '10rem',
      align: 'center',
      cell: (s) => (
        <div className="inline-flex items-center gap-1">
          <button
            type="button"
            onClick={() => handleAbrir(s)}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10 cursor-pointer"
          >
            <Icon name="visibility" className="text-[16px]" />
            Ver detalle
          </button>
          {/* Eliminar: SOLO sesiones modo='test' (diagnóstico, sin examen real).
              Las modo='examen' quedan PERMANENTEMENTE protegidas (regla dura
              #6/#7, cadena de custodia — tarea 16). C-76 tarea 20.8. */}
          {s.modo === 'test' && (
            <button
              type="button"
              title="Eliminar sesión de diagnóstico"
              onClick={(e) => { e.stopPropagation(); setABorrar(s); }}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-error hover:bg-error-container/40 cursor-pointer"
            >
              <Icon name="delete" className="text-[16px]" />
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <StaffShell
      nav={STAFF_NAV}
      title="Registro de sesiones"
      subtitle="Historial de sesiones de proctoring ya finalizadas. Para sesiones en curso, usá Supervisión en vivo; para acotar por riesgo, la Cola de revisión."
      help={
        <HelpButton title="Registro de sesiones">
          <p>
            Listado histórico de sesiones de proctoring <strong>ya finalizadas</strong>.
            Las que siguen en curso aparecen en <em>Supervisión en vivo</em>; para
            acotar por riesgo, usá <em>Cola de revisión</em>.
          </p>
          <p>
            Filtrá por alumno, materia, comisión, examen, rango de fecha o nivel
            de riesgo — todo se resuelve en el servidor. Click en "Ver detalle"
            para abrir eventos, evidencia y biometría. La decisión disciplinaria
            siempre es del revisor.
          </p>
          <p>
            Las sesiones de <strong>diagnóstico</strong> (prueba de cámara/mic,
            sin examen real) se pueden eliminar. Las sesiones de examen real
            quedan protegidas para siempre: son evidencia académica.
          </p>
        </HelpButton>
      }
    >
      <div className="space-y-lg animate-in fade-in duration-500">
        <RefreshBar
          texto="Registro de sesiones"
          lastUpdatedAt={lastUpdatedAt}
          cargando={cargando}
          onActualizar={() => cargar(aplicados, page, pageSize)}
        />

        {/* Stat cards de resumen (C-76 tarea 20.3) — ARRIBA de Filtros. Reflejan
            el TOTAL filtrado, vienen del backend TAL CUAL (nunca se recalculan
            sobre `sesiones`, que solo tiene la página actual). Mismo componente
            StatCard con color (statCatalog) que ya usan Dashboard/Supervisión en
            vivo — nada de estilo neutro inventado ni chips de riesgo aparte. */}
        {/* F-02 (c-78): el `sub` DECLARA el alcance. Esta pantalla es historial
            cerrado (solo finalizadas); el Panel de administración cuenta actividad
            de cualquier estado. Son números distintos a propósito, y ahora cada
            tarjeta lo dice en vez de dejarlo para inferir. */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-md">
          <StatCard {...statProps('sesiones', total, 'finalizadas')} />
          <StatCard
            {...statProps(
              'enColaRevision',
              agregados.en_cola_revision,
              'con examen vinculado, sobre el umbral',
            )}
          />
        </div>

        <FiltrosPanel
          onAplicar={aplicarFiltros}
          onLimpiar={limpiarFiltros}
          hayFiltros={hayFiltrosActivos}
          hayCambios={hayCambiosFiltros}
          aplicarDeshabilitado={cargando}
        >
          {/* Los ensayos del docente se ocultan por defecto: mezclados con las
              rendiciones reales obligaban a separarlos a ojo. Se ocultan, no se
              esconden — este control los trae de vuelta. Se aplica al instante y
              no espera a "Aplicar filtros": es un modo de vista, no una búsqueda. */}
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Ensayos del docente
            <button
              type="button"
              role="switch"
              aria-checked={filtrosIncluyenPruebas}
              onClick={() => {
                setAplicados({ ...aplicados, incluir_pruebas: !filtrosIncluyenPruebas });
                setPage(1);
              }}
              className={`mt-1 inline-flex h-9 items-center gap-2 rounded-md border px-3 text-[13px] transition-colors ${
                filtrosIncluyenPruebas
                  ? 'border-primary bg-primary-container text-on-primary-container'
                  : 'border-surface-300 bg-white text-on-surface-variant'
              }`}
            >
              <Icon name={filtrosIncluyenPruebas ? 'visibility' : 'visibility_off'} className="text-[18px]" />
              {filtrosIncluyenPruebas ? 'Visibles' : 'Ocultos'}
            </button>
          </label>
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Alumno
            <input
              type="text"
              value={borrQ}
              placeholder="Nombre, legajo o email…"
              onChange={(e) => setBorrQ(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') aplicarFiltros(); }}
              className="min-w-[220px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Materia
            <select
              value={borrMateria}
              onChange={(e) => setBorrMateria(e.target.value)}
              className="min-w-[180px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
            >
              <option value="">Todas las materias</option>
              {materias.map((m) => (
                <option key={m.id} value={m.id}>{etiquetaConBaja(m, `${m.codigo} — ${m.nombre}`)}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Comisión
            <select
              value={borrComision}
              onChange={(e) => setBorrComision(e.target.value)}
              disabled={!borrMateria || cargandoComisiones}
              className="min-w-[180px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none disabled:bg-surface-100 disabled:text-on-surface-variant disabled:cursor-not-allowed"
            >
              <option value="">
                {!borrMateria
                  ? 'Elegí una materia primero'
                  : cargandoComisiones
                    ? 'Cargando…'
                    : comisiones.length === 0
                      ? 'Sin comisiones'
                      : 'Todas las comisiones'}
              </option>
              {comisiones.map((c) => (
                <option key={c.id} value={c.id}>{c.codigo ? `${c.codigo} — ${c.nombre}` : c.nombre}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Examen
            <select
              value={borrExamen}
              onChange={(e) => setBorrExamen(e.target.value)}
              className="min-w-[200px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
            >
              <option value="">Todos los exámenes</option>
              {examenes.map((ex) => (
                <option key={ex.id} value={ex.id}>{ex.titulo}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Desde
            <input
              type="date"
              value={borrFechaDesde}
              onChange={(e) => setBorrFechaDesde(e.target.value)}
              className="rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Hasta
            <input
              type="date"
              value={borrFechaHasta}
              onChange={(e) => setBorrFechaHasta(e.target.value)}
              className="rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Nivel de riesgo
            <select
              value={borrNivelRiesgo}
              onChange={(e) => setBorrNivelRiesgo(e.target.value as NivelRiesgoFiltro | '')}
              className="min-w-[160px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
            >
              <option value="">Todos los niveles</option>
              {nivelRiesgoOpciones(getUmbralAlto()).map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </label>
        </FiltrosPanel>

        <Card>
          {/* "sesión" pierde la tilde al pluralizar: pegarle 'es' daba "sesiónes". */}
          <SectionTitle
            icon="history"
            sub={`${total} ${total === 1 ? 'sesión' : 'sesiones'}`}
            action={<PageSizeSelect value={pageSize} onChange={(ps) => { setPageSize(ps); setPage(1); }} />}
          >
            Sesiones finalizadas
          </SectionTitle>

          {cargando && !sesiones.length && <TableSkeleton />}

          {error && (
            <div className="flex items-center gap-sm text-error bg-error-container/40 rounded-xl px-md py-sm text-label-sm mb-md">
              <Icon name="error" className="text-[18px] shrink-0" fill />
              {error}
            </div>
          )}

          {!cargando && !error && sesiones.length === 0 && (
            <div className="text-center py-xl text-on-surface-variant space-y-base">
              <Icon name="search_off" className="text-[40px] text-outline" />
              <p className="text-label-md">
                {hayFiltrosActivos
                  ? 'Ninguna sesión coincide con los filtros.'
                  : 'Todavía no hay sesiones finalizadas.'}
              </p>
            </div>
          )}

          {sesiones.length > 0 && (
            <div className="-mx-lg">
              <AdminTable
                columns={cols}
                data={sesiones}
                keyExtractor={(s) => s.id}
                isLoading={cargando}
                tableMinWidth="1100px"
                onRowClick={handleAbrir}
              />
            </div>
          )}
        </Card>

        <Pagination
          currentPage={page}
          totalPages={totalPaginas}
          totalElements={total}
          pageSize={pageSize}
          onPageChange={setPage}
        />
      </div>

      {/* Confirmación de borrado (C-76 tarea 20.8) — SOLO llega acá para filas
          modo='test' (el botón ni se renderiza para modo='examen'). */}
      <ConfirmModal
        abierto={aBorrar !== null}
        titulo="Eliminar sesión de diagnóstico"
        mensaje={
          <>
            Vas a eliminar la sesión de diagnóstico de{' '}
            <strong>{aBorrar ? alumnoDisplay(aBorrar) : ''}</strong>. Esta acción no se
            puede deshacer. No afecta evidencia académica: las sesiones de examen
            real nunca se pueden eliminar.
          </>
        }
        textoConfirmar={eliminando ? 'Eliminando…' : 'Eliminar'}
        variante="danger"
        onConfirmar={handleConfirmarEliminar}
        onCancelar={() => setABorrar(null)}
      />
    </StaffShell>
  );
}
