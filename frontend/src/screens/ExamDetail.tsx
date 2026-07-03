import { useCallback, useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Button, Card, Icon, SectionTitle } from '../ui/components';
import { STAFF_NAV } from '../ui/nav';
import { useNavigate, useRouteParam } from '../lib/router';
import { api, API_BASE, USE_REAL_BACKEND } from '../lib/api';
import { authProvider } from '../lib/authProvider';
import { TableToolbar, type TableQuery } from '../ui/TableToolbar';
import {
  getExamenHeaderFn,
  listarResultadosFn,
  sincronizarMoodleFn,
  type ResultadoExamen,
} from '../lib/examContentResultados';
import type { ExamenContenidoResumen } from '../lib/types';

import { EstadoBadge } from './exam-detail/EstadoBadge';
import { SyncResultBanner, type SyncResult } from './exam-detail/SyncResultBanner';
import { PreguntasSeleccionSection } from './exam-detail/PreguntasSeleccionSection';
import { ConfiguracionExamenSection } from './exam-detail/ConfiguracionExamenSection';
import { ComisionSection } from './exam-detail/ComisionSection';
import { DestinoMoodleSection } from './exam-detail/DestinoMoodleSection';

// ---------------------------------------------------------------------------
// Helpers locales (usados sólo en la tabla de resultados)
// ---------------------------------------------------------------------------

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
        <div key={i} className="h-12 bg-surface-container-high rounded-lg" />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Componente principal
// ---------------------------------------------------------------------------

const PAGE_SIZE_DEFAULT = 25;

export default function ExamDetail() {
  const navigate = useNavigate();
  const examenId = useRouteParam('id');

  const [examen, setExamen] = useState<ExamenContenidoResumen | null>(null);
  const [headerError, setHeaderError] = useState<string | null>(null);

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

  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);
  const [sincronizando, setSincronizando] = useState(false);
  const [errorSync, setErrorSync] = useState<string | null>(null);

  const cargarHeader = useCallback(() => {
    if (!examenId) return;
    if (!USE_REAL_BACKEND) {
      setExamen({ id: examenId, titulo: 'Examen demo', cantidad_preguntas: 0, comision_nombre: null, materia_nombre: null });
      return;
    }
    setHeaderError(null);
    getExamenHeaderFn(API_BASE, authProvider.getToken(), examenId)
      .then(setExamen)
      .catch((err: unknown) => setHeaderError(err instanceof Error ? err.message : String(err)));
  }, [examenId]);

  useEffect(() => {
    cargarHeader();
  }, [cargarHeader]);

  const fetchResultados = useCallback(async (q: TableQuery) => {
    if (!examenId || !USE_REAL_BACKEND) {
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
    } catch (err: unknown) {
      setErrorTabla(err instanceof Error ? err.message : 'Error al cargar los resultados.');
      setResultados([]);
    } finally {
      setCargandoTabla(false);
    }
  }, [examenId]);

  useEffect(() => {
    fetchResultados(query);
  }, [query, fetchResultados]);

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
      setErrorSync(err instanceof Error ? err.message : 'Error al sincronizar con Moodle.');
    } finally {
      setSincronizando(false);
    }
  }

  const pendientes = resultados.filter((r) => r.estado_moodle === 'pendiente').length;

  if (!examenId) {
    return (
      <StaffShell nav={STAFF_NAV} title="Detalle de examen">
        <Card>
          <div className="flex items-center gap-sm text-error py-md">
            <Icon name="error" className="text-[20px]" fill />
            <span>No se encontró el ID del examen.</span>
          </div>
        </Card>
      </StaffShell>
    );
  }

  const filterDefs = [
    {
      key: 'estado',
      label: 'Estado',
      placeholder: 'Todos los estados',
      options: [
        { value: 'pendiente', label: 'Pendiente de sincronizar' },
        { value: 'enviado',   label: 'Sincronizado en Moodle' },
        { value: 'fallido',   label: 'Falló' },
        { value: 'sin_token', label: 'Sin token' },
      ],
    },
  ];

  return (
    <StaffShell
      nav={STAFF_NAV}
      title={examen?.titulo ?? 'Detalle de examen'}
      subtitle={
        examen
          ? [examen.materia_nombre, examen.comision_nombre].filter(Boolean).join(' · ') || 'Sin materia / comisión asignada'
          : undefined
      }
      actions={
        USE_REAL_BACKEND ? (
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
        ) : undefined
      }
    >
      <div className="space-y-lg animate-in fade-in duration-500">

        <Button variant="ghost" icon="arrow_back" size="sm" onClick={() => navigate('/admin/examenes')}>
          Volver a la lista
        </Button>

        {/* Header stats */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-md">
          <Card className="flex items-start gap-sm !p-md">
            <div className="w-10 h-10 rounded-xl bg-primary-fixed text-on-primary-fixed-variant flex items-center justify-center shrink-0">
              <Icon name="quiz" className="text-[20px]" />
            </div>
            <div className="min-w-0">
              <p className="text-label-sm text-on-surface-variant uppercase tracking-wide">Preguntas</p>
              <p className="font-headline text-title-lg text-on-surface tabular-nums">
                {examen?.cantidad_preguntas ?? '—'}
              </p>
            </div>
          </Card>

          <Card className="flex items-start gap-sm !p-md">
            <div className="w-10 h-10 rounded-xl bg-surface-container text-on-surface-variant flex items-center justify-center shrink-0">
              <Icon name="menu_book" className="text-[20px]" />
            </div>
            <div className="min-w-0">
              <p className="text-label-sm text-on-surface-variant uppercase tracking-wide">Materia</p>
              <p className="text-label-md text-on-surface truncate">
                {examen?.materia_nombre ?? <span className="text-outline italic">— sin materia</span>}
              </p>
            </div>
          </Card>

          <Card className="col-span-2 sm:col-span-1 flex items-start gap-sm !p-md">
            <div className="w-10 h-10 rounded-xl bg-surface-container text-on-surface-variant flex items-center justify-center shrink-0">
              <Icon name="group" className="text-[20px]" />
            </div>
            <div className="min-w-0">
              <p className="text-label-sm text-on-surface-variant uppercase tracking-wide">Comisión</p>
              <p className="text-label-md text-on-surface truncate">
                {examen?.comision_nombre ?? <span className="text-outline italic">— sin comisión</span>}
              </p>
            </div>
          </Card>
        </div>

        {headerError && (
          <div className="flex items-center gap-sm text-error bg-error-container/40 rounded-xl px-md py-sm text-label-sm">
            <Icon name="error" className="text-[18px] shrink-0" fill />
            No se pudo cargar el encabezado del examen: {headerError}
          </div>
        )}

        {USE_REAL_BACKEND && (
          <PreguntasSeleccionSection
            examenId={examenId}
            onSeleccionGuardada={(cantidad) =>
              setExamen((prev) => (prev ? { ...prev, cantidad_preguntas: cantidad } : prev))
            }
          />
        )}

        {USE_REAL_BACKEND && (
          <ComisionSection
            examenId={examenId}
            materiaActual={examen?.materia_nombre}
            comisionActual={examen?.comision_nombre}
            onAsociada={cargarHeader}
          />
        )}

        {USE_REAL_BACKEND && <DestinoMoodleSection examenId={examenId} />}

        {USE_REAL_BACKEND && <ConfiguracionExamenSection examenId={examenId} />}

        {/* Tabla de resultados */}
        <Card>
          <SectionTitle sub={USE_REAL_BACKEND ? `${total} resultado${total !== 1 ? 's' : ''}` : 'Modo demo — sin datos reales'}>
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
            <TableToolbar
              query={query}
              onChange={setQuery}
              placeholder="Buscar por alumno…"
              filterDefs={filterDefs}
              total={USE_REAL_BACKEND ? total : undefined}
              loading={cargandoTabla}
            />
          </div>

          {!USE_REAL_BACKEND && (
            <div className="text-center py-xl text-on-surface-variant space-y-base">
              <Icon name="sync_disabled" className="text-[40px] text-outline" />
              <p className="text-label-md">Conectá el backend real para ver los resultados.</p>
            </div>
          )}

          {USE_REAL_BACKEND && cargandoTabla && !resultados.length && <TableSkeleton />}

          {USE_REAL_BACKEND && errorTabla && (
            <div className="flex items-center gap-sm text-error bg-error-container/40 rounded-xl px-md py-sm text-label-sm">
              <Icon name="error" className="text-[18px] shrink-0" fill />
              {errorTabla}
            </div>
          )}

          {USE_REAL_BACKEND && !cargandoTabla && !errorTabla && resultados.length === 0 && (
            <div className="text-center py-xl text-on-surface-variant space-y-base">
              <Icon name="search_off" className="text-[40px] text-outline" />
              <p className="text-label-md">
                {query.q || query.filters['estado']
                  ? 'Ningún resultado coincide con los filtros.'
                  : 'Este examen no tiene resultados todavía.'}
              </p>
            </div>
          )}

          {USE_REAL_BACKEND && resultados.length > 0 && (
            <div className="overflow-x-auto -mx-lg px-lg">
              <table className="w-full text-left min-w-[600px]">
                <thead>
                  <tr className="text-label-sm uppercase tracking-wide text-on-surface-variant border-b border-outline-variant/40">
                    <th className="py-sm pr-md font-semibold">Alumno</th>
                    <th className="py-sm pr-md font-semibold text-right">Nota</th>
                    <th className="py-sm pr-md font-semibold">Estado Moodle</th>
                    <th className="py-sm font-semibold">Actualizado</th>
                  </tr>
                </thead>
                <tbody>
                  {resultados.map((r) => (
                    <tr
                      key={r.session_id}
                      className={`border-b border-outline-variant/20 transition-colors
                        ${cargandoTabla ? 'opacity-50' : 'hover:bg-surface-container-low'}`}
                    >
                      <td className="py-sm pr-md">
                        <p className="text-label-md font-semibold text-on-surface">{alumnoDisplay(r)}</p>
                        {r.alumno_nombre && (
                          <p className="text-label-sm text-on-surface-variant">{r.alumno_email}</p>
                        )}
                      </td>
                      <td className="py-sm pr-md text-right tabular-nums">
                        {r.nota !== null
                          ? <span className="font-semibold text-on-surface">{r.nota}</span>
                          : <span className="text-outline text-label-sm">—</span>}
                      </td>
                      <td className="py-sm pr-md">
                        <EstadoBadge estado={r.estado_moodle} />
                      </td>
                      <td className="py-sm text-label-sm text-on-surface-variant">
                        {formatFecha(r.actualizado_en)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </StaffShell>
  );
}
