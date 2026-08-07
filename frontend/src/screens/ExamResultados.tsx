/**
 * ExamResultados — Página dedicada a los alumnos que rindieron un examen (C-72 §19).
 *
 * Ruta: /admin/examenes/:id/resultados. Antes esta tabla colgaba al final del
 * detalle del examen; ahora tiene su propia pantalla, con buscador, filtros,
 * paginación y la sincronización con Moodle. Un breadcrumb/volver lleva al detalle.
 */
import { useCallback, useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Button, Card, Icon, SectionTitle } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { STAFF_NAV } from '../ui/nav';
import { useRouteParam } from '../lib/router';
import { API_BASE } from '../lib/api';
import { authProvider } from '../lib/authProvider';
import { type TableQuery } from '../ui/TableToolbar';
import { FiltrosPanel } from '../ui/FiltrosPanel';
import { Pagination, PageSizeSelect } from '../ui/Pagination';
import { RefreshBar } from '../ui/RefreshBar';
import { useAutoRefresh } from '../lib/useAutoRefresh';
import {
  contarRetencionesPorRevision,
  getExamenHeaderFn,
  listarResultadosFn,
  sincronizarMoodleFn,
  type ResultadoExamen,
} from '../lib/examContentResultados';
import type { ExamenContenidoResumen } from '../lib/types';
import { EstadoBadge } from './exam-detail/EstadoBadge';
import { SyncResultBanner, type SyncResult } from './exam-detail/SyncResultBanner';
import { AdminTable, type AdminColumn } from '../ui/AdminTable';

function traducirErrorApi(err: unknown, contexto: 'carga' | 'sinc'): string {
  const status = (err as { status?: number })?.status;
  if (status === 401) return 'Tu sesión expiró. Cerrá sesión, volvé a entrar y reintentá.';
  if (status === 403) return 'No tenés permiso para acceder a esta información.';
  if (status === 404) return 'No se encontró el recurso solicitado.';
  if (status && status >= 500) return 'Error en el servidor. Intentá de nuevo en unos instantes.';
  if (contexto === 'sinc') return 'No se pudo completar la sincronización. Revisá tu conexión.';
  return 'No se pudieron cargar los resultados. Revisá tu conexión.';
}

function alumnoDisplay(r: ResultadoExamen): string {
  if (r.alumno_nombre) return r.alumno_nombre;
  return r.alumno_idnumber || r.alumno_email;
}

function formatFecha(iso: string): string {
  try {
    return new Intl.DateTimeFormat('es-AR', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    }).format(new Date(iso));
  } catch {
    return iso;
  }
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

const PAGE_SIZE_DEFAULT = 5;

export default function ExamResultados() {
  const examenId = useRouteParam('id');

  const [examen, setExamen] = useState<ExamenContenidoResumen | null>(null);
  const [query, setQuery] = useState<TableQuery>({
    q: '',
    filters: { estado: '' },
    page: 1,
    page_size: PAGE_SIZE_DEFAULT,
  });
  const [resultados, setResultados] = useState<ResultadoExamen[]>([]);
  const [total, setTotal] = useState(0);
  const [cargandoTabla, setCargandoTabla] = useState(false);
  const [errorTabla, setErrorTabla] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | undefined>();
  // Borrador de filtros (se aplican con "Aplicar filtros").
  const [borrQ, setBorrQ] = useState('');
  const [borrEstado, setBorrEstado] = useState('');

  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);
  const [sincronizando, setSincronizando] = useState(false);
  const [errorSync, setErrorSync] = useState<string | null>(null);

  useEffect(() => {
    if (!examenId) return;
    getExamenHeaderFn(API_BASE, authProvider.getToken(), examenId)
      .then(setExamen)
      .catch(() => { /* el título cae al fallback */ });
  }, [examenId]);

  const fetchResultados = useCallback(async (q: TableQuery) => {
    if (!examenId) {
      setResultados([]);
      setTotal(0);
      return;
    }
    setCargandoTabla(true);
    setErrorTabla(null);
    try {
      const resp = await listarResultadosFn(API_BASE, authProvider.getToken(), examenId, {
        q: q.q || undefined,
        estado: q.filters['estado'] || undefined,
        page: q.page,
        page_size: q.page_size,
      });
      setResultados(resp.items);
      setTotal(resp.total);
      setLastUpdatedAt(Date.now());
    } catch (err: unknown) {
      setErrorTabla(traducirErrorApi(err, 'carga'));
      setResultados([]);
    } finally {
      setCargandoTabla(false);
    }
  }, [examenId]);

  useEffect(() => {
    fetchResultados(query);
  }, [query, fetchResultados]);

  // Auto-refresh cada 5 min (las notas/estado de sincronización cambian solos).
  useAutoRefresh(() => fetchResultados(query), undefined, !cargandoTabla);

  async function handleSincronizar() {
    if (!examenId) return;
    setSincronizando(true);
    setErrorSync(null);
    setSyncResult(null);
    try {
      const result = await sincronizarMoodleFn(API_BASE, authProvider.getToken(), examenId);
      setSyncResult(result);
      setQuery((q) => ({ ...q }));
    } catch (err: unknown) {
      setErrorSync(traducirErrorApi(err, 'sinc'));
    } finally {
      setSincronizando(false);
    }
  }

  // Las RETENIDAS no cuentan como pendientes: el botón prometía "Sincronizar
  // (2 pendientes)", el backend mandaba 1 (la otra la frena el gate de riesgo) y
  // nada explicaba la diferencia. El contador ahora dice lo que realmente va a pasar.
  const pendientes = resultados.filter(
    (r) => r.estado_moodle === 'pendiente' && !r.retenido_por,
  ).length;
  // 'sin_destino'/'sin_credencial_docente' son retenciones de CONFIGURACIÓN del
  // campus, no de revisión: separadas para no decirle al admin que una nota está
  // "pendiente de revisión por riesgo" cuando el alumno nunca superó el umbral.
  const { revision: retenidasPorRevision, configuracion: retenidasPorConfig } =
    contarRetencionesPorRevision(resultados);

  const ESTADO_OPCIONES = [
    { value: 'pendiente', label: 'Pendiente de sincronizar' },
    { value: 'enviado',   label: 'Sincronizado en Moodle' },
    { value: 'fallido',   label: 'Falló' },
    { value: 'sin_token', label: 'Sin token' },
  ];

  const aplicarFiltros = () =>
    setQuery((q) => ({ ...q, q: borrQ.trim(), filters: { estado: borrEstado }, page: 1 }));
  const limpiarFiltros = () => {
    setBorrQ('');
    setBorrEstado('');
    setQuery((q) => ({ ...q, q: '', filters: { estado: '' }, page: 1 }));
  };
  const hayCambiosFiltros =
    borrQ.trim() !== query.q || borrEstado !== (query.filters['estado'] ?? '');
  const hayFiltrosActivos = Boolean(borrQ || borrEstado);
  const totalPaginas = Math.max(1, Math.ceil(total / query.page_size));

  const volver = () => window.history.back();

  return (
    <StaffShell
      nav={STAFF_NAV}
      title={examen?.titulo ? `Alumnos que rindieron — ${examen.titulo}` : 'Alumnos que rindieron'}
      subtitle={
        examen
          ? [examen.materia_nombre, examen.comision_nombre].filter(Boolean).join(' · ') || 'Resultados y sincronización con Moodle.'
          : 'Resultados y sincronización con Moodle.'
      }
      help={
        <HelpButton title="Alumnos que rindieron">
          <p>
            Lista todos los intentos de este examen: nota obtenida, estado de sincronización
            con Moodle y si la nota está retenida por revisión.
          </p>
          <p>
            <strong>Sincronizar con Moodle</strong> envía las notas pendientes al campus.
            Las notas retenidas por riesgo no se envían hasta que una persona lo apruebe
            desde la Cola de revisión.
          </p>
        </HelpButton>
      }
      actions={
        <Button
          variant="primary"
          icon={sincronizando ? undefined : 'sync'}
          onClick={handleSincronizar}
          disabled={sincronizando}
        >
          {sincronizando
            ? 'Sincronizando…'
            : pendientes > 0
              ? `Sincronizar con Moodle (${pendientes} pendiente${pendientes !== 1 ? 's' : ''})`
              : 'Sincronizar con Moodle'}
        </Button>
      }
    >
      <div className="space-y-lg animate-in fade-in duration-500">
        <Button variant="ghost" icon="arrow_back" size="sm" onClick={volver}>
          Volver
        </Button>

        <RefreshBar
          texto="Alumnos que rindieron"
          lastUpdatedAt={lastUpdatedAt}
          cargando={cargandoTabla}
          onActualizar={() => fetchResultados(query)}
        />

        {/* Aviso de notas frenadas. Sin esto, el admin sincroniza, ve que algunas
            filas no se movieron y no tiene forma de saber que fue a propósito. */}
        {retenidasPorRevision > 0 && (
          <div className="flex items-start gap-sm rounded-lg border border-error-200 bg-error-50 p-md">
            <Icon name="gavel" className="text-[20px] text-error-600 shrink-0 mt-0.5" />
            <div className="min-w-0">
              <p className="text-[14px] font-semibold text-on-surface">
                {retenidasPorRevision} nota{retenidasPorRevision !== 1 ? 's' : ''} retenida
                {retenidasPorRevision !== 1 ? 's' : ''} por revisión
              </p>
              <p className="text-[13px] text-on-surface-variant leading-snug mt-0.5">
                Corresponden a exámenes que superaron el umbral de riesgo o están en revisión.
                No se envían a Moodle hasta que una persona decida. Están marcadas en rojo en la tabla.
              </p>
            </div>
          </div>
        )}
        {retenidasPorConfig > 0 && (
          <div className="flex items-start gap-sm rounded-lg border border-warning-200 bg-warning-50 p-md">
            <Icon name="settings" className="text-[20px] text-warning-600 shrink-0 mt-0.5" />
            <div className="min-w-0">
              <p className="text-[14px] font-semibold text-on-surface">
                {retenidasPorConfig} nota{retenidasPorConfig !== 1 ? 's' : ''} sin sincronizar por configuración
              </p>
              <p className="text-[13px] text-on-surface-variant leading-snug mt-0.5">
                No tienen que ver con el riesgo de la sesión: falta el destino del examen en el campus
                o la cuenta del tutor a cargo. Están marcadas en rojo en la tabla.
              </p>
            </div>
          </div>
        )}


        <Card>
          <SectionTitle
            sub={`${total} resultado${total !== 1 ? 's' : ''}`}
            action={
              <PageSizeSelect
                value={query.page_size}
                onChange={(ps) => setQuery((q) => ({ ...q, page_size: ps, page: 1 }))}
              />
            }
          >
            Alumnos que rindieron
          </SectionTitle>

          {syncResult && (
            <SyncResultBanner result={syncResult} onClose={() => setSyncResult(null)} />
          )}
          {errorSync && (
            <div className="flex items-center gap-sm text-error bg-error-container/40 rounded-xl px-md py-sm text-label-sm mb-md">
              <Icon name="error" className="text-[18px] shrink-0" fill />
              {errorSync}
            </div>
          )}

          <div className="mb-md">
            <FiltrosPanel
              onAplicar={aplicarFiltros}
              onLimpiar={limpiarFiltros}
              hayFiltros={hayFiltrosActivos}
              hayCambios={hayCambiosFiltros}
              aplicarDeshabilitado={cargandoTabla}
            >
              <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
                Buscar
                <input
                  type="text"
                  value={borrQ}
                  placeholder="Nombre, apellido, legajo o email…"
                  onChange={(e) => setBorrQ(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') aplicarFiltros();
                  }}
                  className="min-w-[220px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
                />
              </label>
              <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
                Estado
                <select
                  value={borrEstado}
                  onChange={(e) => setBorrEstado(e.target.value)}
                  className="min-w-[180px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
                >
                  <option value="">Todos los estados</option>
                  {ESTADO_OPCIONES.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </label>
            </FiltrosPanel>
          </div>


          {cargandoTabla && !resultados.length && <TableSkeleton />}

          {errorTabla && (
            <div className="flex items-center gap-sm text-error bg-error-container/40 rounded-xl px-md py-sm text-label-sm">
              <Icon name="error" className="text-[18px] shrink-0" fill />
              {errorTabla}
            </div>
          )}

          {!cargandoTabla && !errorTabla && resultados.length === 0 && (
            <div className="text-center py-xl text-on-surface-variant space-y-base">
              <Icon name="search_off" className="text-[40px] text-outline" />
              <p className="text-label-md">
                {query.q || query.filters['estado']
                  ? 'Ningún resultado coincide con los filtros.'
                  : 'Este examen no tiene resultados todavía.'}
              </p>
            </div>
          )}

          {resultados.length > 0 && (() => {
            const cols: AdminColumn<ResultadoExamen>[] = [
              {
                key: 'alumno',
                header: 'Alumno',
                width: '35%',
                cell: (r) => (
                  <div>
                    <p className="font-semibold text-gray-900">{alumnoDisplay(r)}</p>
                    {r.alumno_nombre && <p className="text-xs text-gray-500 mt-0.5">{r.alumno_email}</p>}
                  </div>
                ),
              },
              {
                key: 'nota',
                header: 'Nota',
                width: '10%',
                align: 'right',
                cell: (r) => r.nota !== null
                  ? <span className="font-semibold text-gray-900 tabular-nums">{r.nota}</span>
                  : <span className="text-gray-400">—</span>,
              },
              {
                key: 'estado',
                header: 'Estado Moodle',
                width: '30%',
                cell: (r) => <EstadoBadge estado={r.estado_moodle} retenidoPor={r.retenido_por} />,
              },
              {
                key: 'actualizado',
                header: 'Actualizado',
                width: '25%',
                cell: (r) => <span className="text-gray-500">{formatFecha(r.actualizado_en)}</span>,
              },
            ];
            return (
              <div className="-mx-lg">
                <AdminTable
                  columns={cols}
                  data={resultados}
                  keyExtractor={(r) => r.session_id}
                  isLoading={cargandoTabla}
                />
              </div>
            );
          })()}
        </Card>

        {/* Paginación FUERA de la card — siempre visible */}
        <Pagination
          currentPage={query.page}
          totalPages={totalPaginas}
          totalElements={total}
          pageSize={query.page_size}
          onPageChange={(p) => setQuery((q) => ({ ...q, page: p }))}
        />
      </div>
    </StaffShell>
  );
}
