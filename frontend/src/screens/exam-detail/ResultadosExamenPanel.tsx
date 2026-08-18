/**
 * ResultadosExamenPanel — panel autocontenido de "alumnos que rindieron" un
 * examen puntual: filtros, paginación, tabla y sincronización con Moodle
 * (todas / seleccionadas / individual, con barra de progreso real).
 *
 * Extraído de ExamResultados.tsx (C-72 §19) para poder reusarlo en dos
 * entradas: la ruta dedicada `/admin/examenes/:id/resultados` (ExamResultados.tsx)
 * y el picker por materia/comisión/examen de `/admin/notas` (Notas.tsx) — ambas
 * pantallas muestran EXACTAMENTE lo mismo, solo cambia cómo se llega al examenId.
 */
import { useCallback, useEffect, useState } from 'react';
import { Button, Card, Icon, SectionTitle } from '../../ui/components';
import { API_BASE } from '../../lib/api';
import { authProvider } from '../../lib/authProvider';
import { type TableQuery } from '../../ui/TableToolbar';
import { FiltrosPanel } from '../../ui/FiltrosPanel';
import { Pagination, PageSizeSelect } from '../../ui/Pagination';
import { RefreshBar } from '../../ui/RefreshBar';
import { useAutoRefresh } from '../../lib/useAutoRefresh';
import {
  archivarResultadoFn,
  contarRetencionesPorRevision,
  listarResultadosFn,
  sincronizarMoodleFn,
  type ResultadoExamen,
  type SincronizarMoodleResponse,
} from '../../lib/examContentResultados';
import { EstadoBadge } from './EstadoBadge';
import { EstadoEntregaBadge, ESTADO_ENTREGA_OPCIONES } from './EstadoEntregaBadge';
import { SyncResultBanner, type SyncResult } from './SyncResultBanner';
import { AdminTable, type AdminColumn } from '../../ui/AdminTable';
import { useToast } from '../../ui/toast';

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

const ESTADO_OPCIONES = [
  { value: 'pendiente', label: 'Pendiente de sincronizar' },
  { value: 'enviado',   label: 'Sincronizado en Moodle' },
  { value: 'fallido',   label: 'Falló' },
  { value: 'sin_token', label: 'Sin token' },
];

export function ResultadosExamenPanel({ examenId }: { examenId: string }) {
  const toast = useToast();

  const FILTROS_INICIALES = { estado: '', estado_entrega: '', archivado: 'false', fecha_desde: '', fecha_hasta: '' };
  const [query, setQuery] = useState<TableQuery>({
    q: '',
    filters: FILTROS_INICIALES,
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
  const [borrEstadoEntrega, setBorrEstadoEntrega] = useState('');
  // 'mostrar archivadas' — default false (el listado NO muestra archivadas).
  const [borrMostrarArchivadas, setBorrMostrarArchivadas] = useState(false);
  const [borrFechaDesde, setBorrFechaDesde] = useState('');
  const [borrFechaHasta, setBorrFechaHasta] = useState('');
  // session_id de la fila cuyo archivar/desarchivar está en curso.
  const [archivandoId, setArchivandoId] = useState<string | null>(null);

  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);
  const [sincronizando, setSincronizando] = useState(false);
  const [errorSync, setErrorSync] = useState<string | null>(null);
  // Progreso real del lote: se sincroniza una nota a la vez (no hay streaming
  // del backend) para poder mostrar "X de Y sincronizadas" en vivo.
  const [syncProgreso, setSyncProgreso] = useState<{ hecho: number; total: number } | null>(null);

  // Selección de filas para subida individual o por lote.
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  // session_id de la fila cuya subida individual está en curso.
  const [sincronizandoId, setSincronizandoId] = useState<string | null>(null);

  // El examen cambia (picker de Notas): resetea todo el estado local para no
  // arrastrar filtros/selección/resultados del examen anterior.
  useEffect(() => {
    setQuery({ q: '', filters: FILTROS_INICIALES, page: 1, page_size: PAGE_SIZE_DEFAULT });
    setBorrQ('');
    setBorrEstado('');
    setBorrEstadoEntrega('');
    setBorrMostrarArchivadas(false);
    setBorrFechaDesde('');
    setBorrFechaHasta('');
    setSelectedIds(new Set());
    setSyncResult(null);
    setErrorSync(null);
  }, [examenId]);

  const fetchResultados = useCallback(async (q: TableQuery) => {
    setCargandoTabla(true);
    setErrorTabla(null);
    try {
      const resp = await listarResultadosFn(API_BASE, authProvider.getToken(), examenId, {
        q: q.q || undefined,
        estado: q.filters['estado'] || undefined,
        estado_entrega: q.filters['estado_entrega'] || undefined,
        archivado: q.filters['archivado'] === 'true',
        fecha_desde: q.filters['fecha_desde'] || undefined,
        fecha_hasta: q.filters['fecha_hasta'] || undefined,
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

  // Sincroniza una lista de session_ids UNA A LA VEZ (no hay streaming del
  // backend: el endpoint procesa todo el lote en una sola respuesta) y va
  // actualizando `syncProgreso` después de cada una, para que la barra sea real
  // ("12 de 40") y no solo un spinner indefinido.
  async function sincronizarConProgreso(ids: string[]): Promise<SincronizarMoodleResponse> {
    const acumulado: SincronizarMoodleResponse = { enviadas: 0, fallidas: 0, sin_token: 0, total: ids.length };
    setSyncProgreso({ hecho: 0, total: ids.length });
    for (let i = 0; i < ids.length; i++) {
      try {
        const r = await sincronizarMoodleFn(API_BASE, authProvider.getToken(), examenId, [ids[i]]);
        acumulado.enviadas += r.enviadas;
        acumulado.fallidas += r.fallidas;
        acumulado.sin_token += r.sin_token;
      } catch {
        acumulado.fallidas += 1;
      }
      setSyncProgreso({ hecho: i + 1, total: ids.length });
    }
    return acumulado;
  }

  // Lote completo: publica TODAS las notas pendientes (no solo la página
  // visible — trae los ids pendientes de todo el examen antes de sincronizar).
  async function handleSincronizar() {
    setSincronizando(true);
    setErrorSync(null);
    setSyncResult(null);
    try {
      const pendientesResp = await listarResultadosFn(API_BASE, authProvider.getToken(), examenId, {
        estado: 'pendiente',
        page: 1,
        page_size: 500,
      });
      const ids = pendientesResp.items.map((r) => r.session_id);
      const result = ids.length > 0
        ? await sincronizarConProgreso(ids)
        : { enviadas: 0, fallidas: 0, sin_token: 0, total: 0 };
      setSyncResult(result);
      setSelectedIds(new Set());
      setQuery((q) => ({ ...q }));
    } catch (err: unknown) {
      setErrorSync(traducirErrorApi(err, 'sinc'));
    } finally {
      setSincronizando(false);
      setSyncProgreso(null);
    }
  }

  // Individual: publica SOLO la nota de una fila.
  async function handleSincronizarIndividual(sessionId: string) {
    setSincronizandoId(sessionId);
    setErrorSync(null);
    setSyncResult(null);
    try {
      const result = await sincronizarMoodleFn(API_BASE, authProvider.getToken(), examenId, [sessionId]);
      setSyncResult(result);
      setQuery((q) => ({ ...q }));
    } catch (err: unknown) {
      setErrorSync(traducirErrorApi(err, 'sinc'));
    } finally {
      setSincronizandoId(null);
    }
  }

  // Lote seleccionado: publica SOLO las filas seleccionadas.
  async function handleSincronizarSeleccionadas() {
    if (selectedIds.size === 0) {
      toast.warning('Seleccioná al menos una fila antes de publicar.');
      return;
    }
    setSincronizando(true);
    setErrorSync(null);
    setSyncResult(null);
    try {
      const result = await sincronizarConProgreso(Array.from(selectedIds));
      setSyncResult(result);
      setSelectedIds(new Set());
      setQuery((q) => ({ ...q }));
    } catch (err: unknown) {
      setErrorSync(traducirErrorApi(err, 'sinc'));
    } finally {
      setSincronizando(false);
      setSyncProgreso(null);
    }
  }

  function toggleSelectAll() {
    if (selectedIds.size === resultados.length && resultados.length > 0) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(resultados.map((r) => r.session_id)));
    }
  }

  function toggleSelect(sessionId: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(sessionId)) {
        next.delete(sessionId);
      } else {
        next.add(sessionId);
      }
      return next;
    });
  }

  const todosSeleccionados = resultados.length > 0 && selectedIds.size === resultados.length;
  const algunosSeleccionados = selectedIds.size > 0 && selectedIds.size < resultados.length;

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

  const aplicarFiltros = () =>
    setQuery((q) => ({
      ...q,
      q: borrQ.trim(),
      filters: {
        estado: borrEstado,
        estado_entrega: borrEstadoEntrega,
        archivado: String(borrMostrarArchivadas),
        fecha_desde: borrFechaDesde ? `${borrFechaDesde}T00:00:00` : '',
        fecha_hasta: borrFechaHasta ? `${borrFechaHasta}T23:59:59` : '',
      },
      page: 1,
    }));
  const limpiarFiltros = () => {
    setBorrQ('');
    setBorrEstado('');
    setBorrEstadoEntrega('');
    setBorrMostrarArchivadas(false);
    setBorrFechaDesde('');
    setBorrFechaHasta('');
    setQuery((q) => ({ ...q, q: '', filters: FILTROS_INICIALES, page: 1 }));
  };
  const hayCambiosFiltros =
    borrQ.trim() !== query.q ||
    borrEstado !== (query.filters['estado'] ?? '') ||
    borrEstadoEntrega !== (query.filters['estado_entrega'] ?? '') ||
    String(borrMostrarArchivadas) !== (query.filters['archivado'] ?? 'false') ||
    (borrFechaDesde ? `${borrFechaDesde}T00:00:00` : '') !== (query.filters['fecha_desde'] ?? '') ||
    (borrFechaHasta ? `${borrFechaHasta}T23:59:59` : '') !== (query.filters['fecha_hasta'] ?? '');
  const hayFiltrosActivos = Boolean(
    borrQ || borrEstado || borrEstadoEntrega || borrMostrarArchivadas || borrFechaDesde || borrFechaHasta,
  );
  const totalPaginas = Math.max(1, Math.ceil(total / query.page_size));

  // Archivar/desarchivar UNA fila. Optimista sobre el filtro activo: si el
  // panel está mostrando "no archivadas" (default) y se archiva una fila, esa
  // fila deja de pertenecer al filtro actual — se refresca la página completa
  // (mismo patrón que sincronizar) en vez de mutar solo esa fila en memoria.
  async function handleArchivar(sessionId: string, archivarA: boolean) {
    setArchivandoId(sessionId);
    try {
      await archivarResultadoFn(API_BASE, authProvider.getToken(), examenId, sessionId, archivarA);
      await fetchResultados(query);
      toast.success(archivarA ? 'Fila archivada.' : 'Fila desarchivada.');
    } catch (err: unknown) {
      toast.warning(traducirErrorApi(err, 'carga'));
    } finally {
      setArchivandoId(null);
    }
  }

  return (
    <div className="space-y-lg">
      {/* Barra de acciones de sync — antes vivía en el `actions` del StaffShell
          de ExamResultados.tsx; acá adentro para que el panel sea autocontenido
          y se pueda embeber en Notas.tsx sin duplicar los botones. */}
      <div className="flex items-center justify-end gap-sm flex-wrap">
        {selectedIds.size > 0 && (
          <Button
            variant="secondary"
            icon={sincronizando ? undefined : 'upload'}
            onClick={handleSincronizarSeleccionadas}
            disabled={sincronizando || sincronizandoId !== null}
          >
            {sincronizando ? 'Publicando…' : `Publicar seleccionadas (${selectedIds.size})`}
          </Button>
        )}
        <Button
          variant="primary"
          icon={sincronizando ? undefined : 'cloud_upload'}
          onClick={handleSincronizar}
          disabled={sincronizando || sincronizandoId !== null}
        >
          {sincronizando
            ? 'Publicando…'
            : pendientes > 0
              ? `Publicar notas en Moodle (${pendientes} pendiente${pendientes !== 1 ? 's' : ''})`
              : 'Publicar notas en Moodle'}
        </Button>
      </div>

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

        {syncProgreso && (
          <div className="mb-md rounded-xl border border-primary/20 bg-primary-fixed/20 p-md">
            <div className="flex items-center justify-between text-label-sm text-on-surface mb-xs">
              <span className="inline-flex items-center gap-xs font-medium">
                <Icon name="cloud_sync" className="text-[16px] ae-spin" />
                Sincronizando con Moodle…
              </span>
              <span className="tabular-nums text-on-surface-variant">
                {syncProgreso.hecho} de {syncProgreso.total}
              </span>
            </div>
            <div className="h-2 rounded-full bg-white overflow-hidden" role="progressbar"
              aria-valuenow={syncProgreso.hecho} aria-valuemin={0} aria-valuemax={syncProgreso.total}>
              <div
                className="h-full bg-primary transition-all duration-200"
                style={{ width: `${syncProgreso.total > 0 ? (syncProgreso.hecho / syncProgreso.total) * 100 : 0}%` }}
              />
            </div>
          </div>
        )}

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
            <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
              Estado de entrega
              <select
                value={borrEstadoEntrega}
                onChange={(e) => setBorrEstadoEntrega(e.target.value)}
                className="min-w-[190px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
              >
                <option value="">Todas las entregas</option>
                {ESTADO_ENTREGA_OPCIONES.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
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
            <label className="flex items-center gap-2 text-[12px] font-medium text-on-surface-variant self-end pb-2">
              <input
                type="checkbox"
                checked={borrMostrarArchivadas}
                onChange={(e) => setBorrMostrarArchivadas(e.target.checked)}
                className="w-4 h-4 accent-primary cursor-pointer"
              />
              Mostrar archivadas
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
              key: 'sel',
              header: (
                <input
                  type="checkbox"
                  aria-label="Seleccionar todas las filas"
                  checked={todosSeleccionados}
                  ref={(el) => {
                    if (el) el.indeterminate = algunosSeleccionados;
                  }}
                  onChange={toggleSelectAll}
                  className="w-4 h-4 accent-primary cursor-pointer"
                />
              ),
              width: '3rem',
              align: 'center',
              headerAlign: 'center',
              cell: (r) => (
                <input
                  type="checkbox"
                  aria-label={`Seleccionar fila de ${alumnoDisplay(r)}`}
                  checked={selectedIds.has(r.session_id)}
                  onChange={() => toggleSelect(r.session_id)}
                  className="w-4 h-4 accent-primary cursor-pointer"
                />
              ),
              tdClassName: 'px-3',
            },
            {
              key: 'alumno',
              header: 'Alumno',
              width: '33%',
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
              width: '20%',
              cell: (r) => <EstadoBadge estado={r.estado_moodle} retenidoPor={r.retenido_por} />,
            },
            {
              key: 'entrega',
              header: 'Entrega',
              width: '15%',
              cell: (r) => <EstadoEntregaBadge estado={r.estado_entrega} />,
            },
            {
              key: 'actualizado',
              header: 'Actualizado',
              width: '18%',
              cell: (r) => <span className="text-gray-500">{formatFecha(r.actualizado_en)}</span>,
            },
            {
              key: 'acciones',
              header: 'Acción',
              width: '10rem',
              align: 'center',
              tdClassName: 'sticky right-0 bg-white shadow-[-4px_0_4px_rgba(0,0,0,0.05)]',
              thClassName: 'sticky right-0 shadow-[-4px_0_4px_rgba(0,0,0,0.05)]',
              cell: (r) => {
                const enCurso = sincronizandoId === r.session_id;
                const archivandoEstaFila = archivandoId === r.session_id;
                const bloqueado = sincronizando || sincronizandoId !== null || archivandoId !== null;
                return (
                  <div className="flex items-center justify-center gap-1">
                    <button
                      type="button"
                      title={r.retenido_por ? 'Nota retenida — no se puede publicar' : 'Publicar esta nota en Moodle'}
                      disabled={bloqueado || Boolean(r.retenido_por)}
                      onClick={() => handleSincronizarIndividual(r.session_id)}
                      className={[
                        'inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors',
                        r.retenido_por
                          ? 'cursor-not-allowed text-gray-300'
                          : bloqueado
                            ? 'cursor-not-allowed text-gray-400'
                            : 'text-primary hover:bg-primary/10 cursor-pointer',
                      ].join(' ')}
                    >
                      {enCurso
                        ? <Icon name="progress_activity" className="ae-spin text-[16px]" />
                        : <Icon name="cloud_upload" className="text-[16px]" />}
                      {enCurso ? 'Publicando…' : 'Publicar'}
                    </button>
                    <button
                      type="button"
                      title={r.archivado ? 'Desarchivar esta fila' : 'Archivar esta fila (no se borra nada)'}
                      disabled={bloqueado}
                      onClick={() => handleArchivar(r.session_id, !r.archivado)}
                      className={[
                        'inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors',
                        bloqueado
                          ? 'cursor-not-allowed text-gray-400'
                          : 'text-on-surface-variant hover:bg-surface-100 cursor-pointer',
                      ].join(' ')}
                    >
                      {archivandoEstaFila
                        ? <Icon name="progress_activity" className="ae-spin text-[16px]" />
                        : <Icon name={r.archivado ? 'unarchive' : 'archive'} className="text-[16px]" />}
                    </button>
                  </div>
                );
              },
            },
          ];
          return (
            <div className="-mx-lg">
              <AdminTable
                columns={cols}
                data={resultados}
                keyExtractor={(r) => r.session_id}
                isLoading={cargandoTabla}
                tableMinWidth="700px"
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
  );
}

export default ResultadosExamenPanel;
