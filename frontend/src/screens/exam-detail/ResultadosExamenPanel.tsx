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
import { Badge, Button, Card, Icon, SectionTitle } from '../../ui/components';
import { API_BASE } from '../../lib/api';
import { authProvider } from '../../lib/authProvider';
import { type TableQuery } from '../../ui/TableToolbar';
import { FiltrosPanel } from '../../ui/FiltrosPanel';
import { Pagination, PageSizeSelect } from '../../ui/Pagination';
import { RefreshBar } from '../../ui/RefreshBar';
import { useAutoRefresh } from '../../lib/useAutoRefresh';
import {
  archivarResultadoFn,
  listarResultadosFn,
  desmarcarNotaCargadaFn,
  marcarNotaCargadaFn,
  sincronizarMoodleFn,
  type ArchivadoFiltro,
  type ResultadoExamen,
  type SincronizarMoodleResponse,
} from '../../lib/examContentResultados';
import { EstadoBadge } from './EstadoBadge';
import { useEstadosMoodle } from './useEstadosMoodle';
// Retenciones que SÍ frenan el marcado a mano: mientras no haya decisión humana
// no se sabe qué nota corresponde, así que afirmar que se cargó no tiene sentido.
const MOTIVOS_DE_REVISION = new Set(['en_riesgo']);
import { useResultados } from './useCatalogosNota';
import { SyncResultBanner, type SyncResult } from './SyncResultBanner';
import { AdminTable, type AdminColumn } from '../../ui/AdminTable';
import { ActionMenu } from '../../ui/ActionMenu';
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

function formatFecha(iso: string | null | undefined): string {
  // El ausente no tiene fecha: nunca rindió. Sin esta guarda, `new Date(null)`
  // da el epoch y la fila mostraba "31/12, 21:00", que parece un dato real.
  if (!iso) return '—';
  try {
    // Corta y en 24 horas: "27/08/2026, 11:50 p. m." ocupaba casi el doble y
    // empujaba la última columna fuera de la tabla. El año se sobreentiende en
    // un listado del cuatrimestre en curso; la fecha completa va en el título.
    return new Intl.DateTimeFormat('es-AR', {
      day: '2-digit', month: '2-digit',
      hour: '2-digit', minute: '2-digit', hour12: false,
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

export function ResultadosExamenPanel({ examenId }: { examenId: string }) {
  const toast = useToast();
  // Los estados los define el backend. Estaban escritos a mano acá y faltaba
  // 'manual' ("cargada a mano"), así que ese estado se veía en la tabla pero no
  // se podía filtrar: quien marcaba notas a mano no tenía después cómo listarlas.
  const estadosMoodle = useEstadosMoodle();
  // Los resultados también los define el backend: acá sólo se pintan.
  const catalogoResultados = useResultados();

  const FILTROS_INICIALES = { estado: '', resultado: '', estado_entrega: '', archivado: 'false', fecha_desde: '', fecha_hasta: '' };
  const [query, setQuery] = useState<TableQuery>({
    q: '',
    filters: FILTROS_INICIALES,
    page: 1,
    page_size: PAGE_SIZE_DEFAULT,
  });
  const [resultados, setResultados] = useState<ResultadoExamen[]>([]);
  const [total, setTotal] = useState(0);
  // Avisos del EXAMEN entero, calculados server-side. Contarlos sobre la página
  // hacía que cambiaran al paginar.
  const [avisos, setAvisos] = useState({ revision: 0, configuracion: 0 });
  const [cargandoTabla, setCargandoTabla] = useState(false);
  const [errorTabla, setErrorTabla] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | undefined>();
  // Borrador de filtros (se aplican con "Aplicar filtros").
  const [borrQ, setBorrQ] = useState('');
  const [borrEstado, setBorrEstado] = useState('');
  // Filtro por resultado académico (aprobado / desaprobado / anulada…).
  const [borrResultado, setBorrResultado] = useState('');
  const [borrEstadoEntrega, setBorrEstadoEntrega] = useState('');
  // 'mostrar archivadas' — default false (el listado NO muestra archivadas).
  const [borrMostrarArchivadas, setBorrMostrarArchivadas] = useState(false);
  const [borrFechaDesde, setBorrFechaDesde] = useState('');
  const [borrFechaHasta, setBorrFechaHasta] = useState('');
  // session_id de la fila cuyo archivar/desarchivar está en curso.
  const [archivandoId, setArchivandoId] = useState<string | null>(null);
  // c-78 §13.6: session_id de la fila que se está marcando como cargada a mano.
  const [marcandoId, setMarcandoId] = useState<string | null>(null);
  const [descargandoExport, setDescargandoExport] = useState(false);

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
    setBorrResultado('');
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
        resultado: q.filters['resultado'] || undefined,
        estado_entrega: q.filters['estado_entrega'] || undefined,
        // c-78 D6: el checkbox "Mostrar archivadas" manda 'todas' (ambas), que es
        // lo que su etiqueta promete. 'true' habría traído SOLO las archivadas.
        archivado: (q.filters['archivado'] as ArchivadoFiltro) || 'false',
        fecha_desde: q.filters['fecha_desde'] || undefined,
        fecha_hasta: q.filters['fecha_hasta'] || undefined,
        page: q.page,
        page_size: q.page_size,
      });
      setResultados(resp.items);
      setTotal(resp.total);
      setAvisos({
        revision: resp.retenidas_por_revision ?? 0,
        configuracion: resp.sin_sincronizar_config ?? 0,
      });
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
  // Los avisos vienen del BACKEND y describen todo el examen. Contarlos acá
  // sobre `resultados` (la página visible) hacía que el número cambiara al
  // paginar: en la página 2 "2 notas retenidas por revisión" desaparecía.
  //
  // Siguen separados en dos: la retención por revisión la destraba una persona
  // en la cola; la de configuración se arregla completando el destino de la
  // nota. Mandan al docente a lugares distintos.
  const retenidasPorRevision = avisos.revision;
  const retenidasPorConfig = avisos.configuracion;

  const aplicarFiltros = () =>
    setQuery((q) => ({
      ...q,
      q: borrQ.trim(),
      filters: {
        estado: borrEstado,
        resultado: borrResultado,
        estado_entrega: borrEstadoEntrega,
        archivado: borrMostrarArchivadas ? 'todas' : 'false',
        fecha_desde: borrFechaDesde ? `${borrFechaDesde}T00:00:00` : '',
        fecha_hasta: borrFechaHasta ? `${borrFechaHasta}T23:59:59` : '',
      },
      page: 1,
    }));
  const limpiarFiltros = () => {
    setBorrQ('');
    setBorrEstado('');
    setBorrResultado('');
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
    (borrMostrarArchivadas ? 'todas' : 'false') !== (query.filters['archivado'] ?? 'false') ||
    (borrFechaDesde ? `${borrFechaDesde}T00:00:00` : '') !== (query.filters['fecha_desde'] ?? '') ||
    (borrFechaHasta ? `${borrFechaHasta}T23:59:59` : '') !== (query.filters['fecha_hasta'] ?? '');
  const hayFiltrosActivos = Boolean(
    borrQ || borrEstado || borrEstadoEntrega || borrMostrarArchivadas || borrFechaDesde || borrFechaHasta,
  );
  // F-06 (c-78 §7.3): filtros YA APLICADOS. La condición del mensaje de vacío miraba
  // solo `q` y `estado`, así que filtrar por estado de entrega, por archivado o por
  // rango de fechas sin resultados decía "este examen no tiene resultados todavía" —
  // que es una afirmación distinta y falsa.
  const hayFiltrosAplicados = Boolean(
    query.q ||
      query.filters['estado'] ||
      query.filters['estado_entrega'] ||
      (query.filters['archivado'] && query.filters['archivado'] !== 'false') ||
      query.filters['fecha_desde'] ||
      query.filters['fecha_hasta'],
  );
  const totalPaginas = Math.max(1, Math.ceil(total / query.page_size));

  // Archivar/desarchivar UNA fila. Optimista sobre el filtro activo: si el
  // panel está mostrando "no archivadas" (default) y se archiva una fila, esa
  // fila deja de pertenecer al filtro actual — se refresca la página completa
  // (mismo patrón que sincronizar) en vez de mutar solo esa fila en memoria.
  // c-78 §13.6 (D14): sin API del campus, la nota se carga a mano y quedaba
  // 'pendiente' para siempre. Esto la mueve, dejando registrado quién lo afirmó.
  /** Las que se pueden marcar a mano: ni ya en el campus, ni retenidas por una
   *  revisión sin resolver (ahí todavía no se sabe qué nota va). */
  function marcablesDe(ids: Set<string>): string[] {
    return resultados
      .filter(
        (r) =>
          r.session_id &&
          ids.has(r.session_id) &&
          r.estado_moodle !== 'enviado' &&
          r.estado_moodle !== 'manual' &&
          !MOTIVOS_DE_REVISION.has(r.retenido_por ?? ''),
      )
      .map((r) => r.session_id);
  }

  /** Todas las de la página que se pueden marcar. Es lo que cuenta el botón de
   *  arriba cuando no hay nada seleccionado. */
  const marcablesDeTodas = resultados
    .filter(
      (r) =>
        r.session_id &&
        r.estado_moodle !== 'enviado' &&
        r.estado_moodle !== 'manual' &&
        !MOTIVOS_DE_REVISION.has(r.retenido_por ?? ''),
    )
    .map((r) => r.session_id);

  async function handleMarcarCargadasEnLote() {
    const ids =
      selectedIds.size > 0
        ? marcablesDe(selectedIds)
        : marcablesDeTodas;
    if (ids.length === 0) {
      toast.warning('Ninguna de las seleccionadas se puede marcar a mano.');
      return;
    }
    setMarcandoId('lote');
    let hechas = 0;
    try {
      // De a una: el backend no tiene endpoint de lote para esto y cada marca
      // deja su propio registro de quién y cuándo, que es el punto de la función.
      for (const id of ids) {
        try {
          await marcarNotaCargadaFn(API_BASE, authProvider.getToken(), examenId, id);
          hechas += 1;
        } catch {
          // Sigue con las demás: que una falle no puede dejar el lote a medias
          // sin avisar cuántas sí entraron.
        }
      }
      await fetchResultados(query);
      const quedaron = selectedIds.size - hechas;
      toast.success(
        `${hechas} nota${hechas === 1 ? '' : 's'} marcada${hechas === 1 ? '' : 's'} como cargada${hechas === 1 ? '' : 's'} a mano.` +
          (quedaron > 0 ? ` ${quedaron} quedaron sin marcar (ya estaban en el campus o están en revisión).` : ''),
      );
      setSelectedIds(new Set());
    } finally {
      setMarcandoId(null);
    }
  }

  async function handleDesmarcarCargada(sessionId: string) {
    setMarcandoId(sessionId);
    try {
      await desmarcarNotaCargadaFn(API_BASE, authProvider.getToken(), examenId, sessionId);
      await fetchResultados(query);
      toast.success('Se deshizo el marcado: la nota volvió a pendiente.');
    } catch (err: unknown) {
      toast.warning((err as Error)?.message || 'No se pudo deshacer el marcado.');
    } finally {
      setMarcandoId(null);
    }
  }

  async function handleMarcarCargada(sessionId: string) {
    setMarcandoId(sessionId);
    try {
      await marcarNotaCargadaFn(API_BASE, authProvider.getToken(), examenId, sessionId);
      await fetchResultados(query);
      toast.success('Nota marcada como cargada en el campus.');
    } catch (err: unknown) {
      const status = (err as { status?: number })?.status;
      toast.warning(
        status === 409
          ? 'El campus ya confirmó esta nota: no hace falta marcarla a mano.'
          : (err as Error)?.message || 'No se pudo marcar la nota.',
      );
    } finally {
      setMarcandoId(null);
    }
  }

  // c-78 §13.5 (E-10): el listado en un archivo, para cargarlo a mano en el campus.
  async function handleExportar(formato: 'xlsx' | 'pdf') {
    setDescargandoExport(true);
    try {
      const { descargarExport, urlExportNotas } = await import('../../lib/examContentAdmin');
      await descargarExport(urlExportNotas(examenId, formato), `notas.${formato}`);
    } catch {
      toast.warning('No se pudo generar el archivo. Probá de nuevo.');
    } finally {
      setDescargandoExport(false);
    }
  }

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
        {/* c-78 §13.5 (E-10): hay campus SIN API — la nota se carga a mano y para
            eso hace falta el listado en un archivo, no en la pantalla. */}
        {/* Dicen QUÉ HACEN ("Exportar a…", no "Excel" suelto) y llevan el color
            con el que cada formato ya se reconoce: verde el de la planilla,
            rojo el del PDF. Con dos botones grises al lado del azul de publicar,
            había que leer el ícono para saber cuál era cuál. */}
        <button
          type="button"
          disabled={descargandoExport || total === 0}
          onClick={() => void handleExportar('xlsx')}
          className="inline-flex items-center gap-2 rounded-lg border border-[#1D6F42]/30 bg-[#1D6F42]/5 px-4 py-2 text-[14px] font-medium text-[#1D6F42] transition-colors hover:bg-[#1D6F42]/10 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Icon name="table_view" className="text-[18px]" />
          Exportar a Excel
        </button>
        <button
          type="button"
          disabled={descargandoExport || total === 0}
          onClick={() => void handleExportar('pdf')}
          className="inline-flex items-center gap-2 rounded-lg border border-[#C4241B]/30 bg-[#C4241B]/5 px-4 py-2 text-[14px] font-medium text-[#C4241B] transition-colors hover:bg-[#C4241B]/10 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Icon name="picture_as_pdf" className="text-[18px]" />
          Exportar a PDF
        </button>
        {selectedIds.size > 0 && (
          <>
            <Button
              variant="secondary"
              icon={sincronizando ? undefined : 'upload'}
              onClick={handleSincronizarSeleccionadas}
              disabled={sincronizando || sincronizandoId !== null}
            >
              {sincronizando ? 'Publicando…' : `Publicar seleccionadas (${selectedIds.size})`}
            </Button>
          </>
        )}
        {/* Al lado de "Publicar": es la otra forma de cerrar el circuito cuando
            el campus no tiene API — se cargan las notas a mano y se marcan
            todas juntas. Marcarlas de a una es el trabajo que esto evita. */}
        <button
          type="button"
          onClick={handleMarcarCargadasEnLote}
          disabled={marcandoId !== null || sincronizando || marcablesDeTodas.length === 0}
          className="inline-flex items-center gap-2 rounded-lg bg-gray-900 px-4 py-2 text-[14px] font-medium text-white transition-colors hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Icon
            name={marcandoId === 'lote' ? 'progress_activity' : 'how_to_reg'}
            className={`text-[18px] ${marcandoId === 'lote' ? 'ae-spin' : ''}`}
          />
          {marcandoId === 'lote'
            ? 'Marcando…'
            : `Marcar como cargadas a mano (${marcablesDeTodas.length})`}
        </button>
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
            {/* Los filtros se llaman IGUAL que las columnas que filtran: uno
                decia "Estado" y el otro "Estado de entrega", y ninguno de los
                dos nombres coincidia con el titulo de su columna. */}
            <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
              Resultado
              <select
                value={borrResultado}
                onChange={(e) => setBorrResultado(e.target.value)}
                className="min-w-[170px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
              >
                <option value="">Todos</option>
                {[...catalogoResultados.values()].map((o) => (
                  <option key={o.valor} value={o.valor}>{o.etiqueta}</option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
              Estado de la entrega
              <select
                value={borrEstado}
                onChange={(e) => setBorrEstado(e.target.value)}
                className="min-w-[180px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
              >
                <option value="">Todos los estados</option>
                {estadosMoodle.map((o) => (
                  <option key={o.valor} value={o.valor}>{o.etiqueta}</option>
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
              {hayFiltrosAplicados
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
              width: '26%',
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
              // Más ancha: con la anulada muestra dos números ("0  78" tachado).
              width: '11%',
              // Centrada y no pegada al borde derecho: contra la columna de al
              // lado se leía como si fueran una sola cosa.
              align: 'center',
              // `nota_efectiva`: una anulación deja la nota en 0. La calculada
              // va en el tooltip — sin verla no se puede reclamar ni auditar la
              // decisión, pero el número que vale es el otro.
              cell: (r) => {
                const efectiva = r.nota_efectiva ?? r.nota;
                if (efectiva === null || efectiva === undefined) {
                  return <span className="text-gray-400">—</span>;
                }
                const cambio = r.nota != null && r.nota !== efectiva;
                return (
                  <span className="inline-flex items-baseline gap-1.5 tabular-nums">
                    <span className="font-semibold text-gray-900">{efectiva}</span>
                    {cambio && (
                      <span className="text-[12px] text-on-surface-variant line-through">
                        {r.nota}
                      </span>
                    )}
                  </span>
                );
              },
            },
            {
              // El resultado ACADÉMICO: es por lo que se abre este listado. El
              // valor, la etiqueta y el color los define el BACKEND
              // (`ResultadoNota`): acá no se decide nada.
              key: 'resultado',
              header: 'Resultado',
              width: '17%',
              cell: (r) => {
                const info = catalogoResultados.get(r.resultado ?? '');
                const detalle =
                  r.nota_aprobacion != null ? `Aprueba con ${r.nota_aprobacion}` : undefined;
                return (
                  <span title={detalle}>
                    <Badge tone={info?.tono ?? 'neutral'}>{info?.etiqueta ?? '—'}</Badge>
                  </span>
                );
              },
            },
            {
              key: 'estado',
              // La ENTREGA de la nota al campus. Así se la nombra en la
              // práctica: "entregar las notas" es subirlas a Moodle.
              header: 'Estado de la entrega',
              width: '26%',
              cell: (r) => <EstadoBadge
                  estado={r.estado_moodle}
                  retenidoPor={r.retenido_por}
                  retenciones={r.retenciones}
                  marcadaManualPor={r.marcada_manual_por}
                  marcadaManualEn={r.marcada_manual_en}
                />,
            },
            {
              key: 'actualizado',
              header: 'Actualizado',
              width: '12%',
              cell: (r) => (
                <span className="text-gray-500">{formatFecha(r.actualizado_en)}</span>
              ),
            },
            {
              key: 'acciones',
              header: 'Acciones',
              width: '5rem',
              align: 'center',
              tdClassName: 'sticky right-0 bg-white shadow-[-4px_0_4px_rgba(0,0,0,0.05)]',
              thClassName: 'sticky right-0 shadow-[-4px_0_4px_rgba(0,0,0,0.05)]',
              cell: (r) => {
                const enCurso = sincronizandoId === r.session_id;
                const archivandoEstaFila = archivandoId === r.session_id;
                const bloqueado = sincronizando || sincronizandoId !== null || archivandoId !== null;
                // SIEMPRE las mismas tres opciones. Antes "marcar cargada a
                // mano" desaparecia en las filas que ya estaban cargadas, asi
                // que una fila tenia dos opciones y la de al lado tres: se lee
                // como un error de la pantalla, y encima no explicaba nada.
                // Apagada con el motivo a la vista si dice lo que pasa.
                const yaEnElCampus = r.estado_moodle === 'enviado' || r.estado_moodle === 'manual';
                // El ausente no tiene sesión: no hay nada que publicar, marcar
                // ni archivar. Se apagan las tres con el motivo a la vista.
                const noRindio = !r.session_id;
                return (
                  <ActionMenu
                    ariaLabel={`Acciones de ${alumnoDisplay(r)}`}
                    items={[
                      {
                        label: enCurso ? 'Publicando…' : 'Publicar en el campus',
                        icon: 'cloud_upload',
                        disabled: noRindio || bloqueado || Boolean(r.retenido_por),
                        title: noRindio
                          ? 'El alumno no rindió: no hay nota que publicar'
                          : r.retenido_por
                          ? 'La nota esta retenida: no se puede publicar hasta que se resuelva'
                          : 'Enviar esta nota a la libreta del campus',
                        onClick: () => handleSincronizarIndividual(r.session_id),
                      },
                      r.estado_moodle === 'manual'
                        ? {
                            label:
                              marcandoId === r.session_id
                                ? 'Deshaciendo…'
                                : 'Deshacer: no estaba cargada',
                            icon: 'undo',
                            disabled: bloqueado || marcandoId !== null,
                            title:
                              'La marca la puso una persona y se puede corregir. ' +
                              'La nota vuelve a pendiente.',
                            onClick: () => handleDesmarcarCargada(r.session_id),
                          }
                        : {
                        label:
                          marcandoId === r.session_id
                            ? 'Marcando…'
                            : 'Marcar como cargada a mano',
                        icon: 'how_to_reg',
                        disabled: noRindio || bloqueado || marcandoId !== null || yaEnElCampus,
                        title: noRindio
                          ? 'El alumno no rindió: no hay nota que cargar'
                          : yaEnElCampus
                          ? 'Esta nota ya figura en el campus'
                          : 'Marcar que ya cargaste esta nota en el campus, a mano',
                        onClick: () => handleMarcarCargada(r.session_id),
                      },
                      {
                        label: archivandoEstaFila
                          ? 'Archivando…'
                          : r.archivado
                            ? 'Desarchivar'
                            : 'Archivar',
                        icon: r.archivado ? 'unarchive' : 'archive',
                        disabled: noRindio || bloqueado,
                        title: 'Sacar la fila de la vista. No se borra nada.',
                        onClick: () => handleArchivar(r.session_id, !r.archivado),
                      },
                    ]}
                  />
                );
              },
            },
          ];
          return (
            <div className="-mx-lg">
              <AdminTable
                columns={cols}
                data={resultados}
                // Los ausentes llegan sin `session_id` (cadena vacía): sin este
                // fallback todos compartían la misma clave y React reutilizaba el
                // DOM entre alumnos distintos, con el riesgo de que la selección o
                // el spinner de una fila cayeran sobre el ausente equivocado.
                keyExtractor={(r) => r.session_id || `alumno-${r.usuario_id ?? r.alumno_email}`}
                isLoading={cargandoTabla}
                tableMinWidth="820px"
                anchoFijo
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
