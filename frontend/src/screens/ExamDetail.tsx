/**
 * ExamDetail — Detalle de examen (admin): alumnos que rindieron, notas,
 * estado Moodle y botón de sincronización (C-69).
 *
 * Ruta: /admin/examenes/:id
 * Datos:
 *   - Header: GET /api/v1/exam-content/{id}/resumen → título, materia, comisión, preguntas
 *   - Tabla:  GET /api/v1/exam-content/{id}/resultados?q=&estado=&page=&page_size=
 *   - Sync:   POST /api/v1/exam-content/{id}/sincronizar-moodle
 *
 * Responsive: tabla con scroll horizontal contenido en mobile (~390px).
 */

import { useCallback, useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Badge, Button, Card, Icon, SectionTitle } from '../ui/components';
import { STAFF_NAV } from '../ui/nav';
import { useNavigate, useRouteParam } from '../lib/router';
import { API_BASE, USE_REAL_BACKEND } from '../lib/api';
import { authProvider } from '../lib/authProvider';
import { TableToolbar, type TableQuery } from '../ui/TableToolbar';
import {
  getExamenHeaderFn,
  listarResultadosFn,
  sincronizarMoodleFn,
  type EstadoMoodle,
  type ResultadoExamen,
} from '../lib/examContentResultados';
import {
  getPreguntasExamen,
  setPreguntasSeleccion,
  type PreguntaSeleccion,
} from '../lib/examContentAdmin';
import type { ExamenContenidoResumen } from '../lib/types';

// ---------------------------------------------------------------------------
// Badge de estado Moodle
// ---------------------------------------------------------------------------

const ESTADO_MOODLE_CONFIG: Record<EstadoMoodle, { label: string; tone: 'warning' | 'success' | 'error' | 'neutral' }> = {
  pendiente: { label: 'Pendiente de sincronizar', tone: 'warning' },
  enviado:   { label: 'Sincronizado en Moodle',  tone: 'success' },
  fallido:   { label: 'Falló',                   tone: 'error' },
  sin_token: { label: 'Sin token / no enviado',  tone: 'neutral' },
};

function EstadoBadge({ estado }: { estado: EstadoMoodle }) {
  const cfg = ESTADO_MOODLE_CONFIG[estado] ?? { label: estado, tone: 'neutral' as const };
  return <Badge tone={cfg.tone} dot>{cfg.label}</Badge>;
}

// ---------------------------------------------------------------------------
// Fila de alumno (fallback display cuando nombre es null)
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

// ---------------------------------------------------------------------------
// Skeleton para la tabla mientras carga
// ---------------------------------------------------------------------------

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
// Resultado de sincronización
// ---------------------------------------------------------------------------

type SyncResult = {
  enviadas: number;
  fallidas: number;
  sin_token: number;
  total: number;
  mensaje?: string;
};

function SyncResultBanner({ result, onClose }: { result: SyncResult; onClose: () => void }) {
  const todoSinToken = result.sin_token > 0 && result.enviadas === 0 && result.fallidas === 0;
  const tieneFallidas = result.fallidas > 0;
  const tone = todoSinToken ? 'warning' : tieneFallidas ? 'error' : 'success';

  const bgMap = { warning: 'bg-warning-container', error: 'bg-error-container', success: 'bg-success-container' };
  const textMap = { warning: 'text-warning', error: 'text-on-error-container', success: 'text-success' };
  const iconMap = { warning: 'info', error: 'error', success: 'check_circle' };

  return (
    <div className={`flex items-start gap-sm p-md rounded-xl ${bgMap[tone]} mb-md`}>
      <Icon name={iconMap[tone]} className={`${textMap[tone]} text-[20px] shrink-0 mt-0.5`} fill />
      <div className="flex-1 min-w-0">
        {todoSinToken ? (
          <p className={`text-label-md font-semibold ${textMap[tone]}`}>
            Token de Moodle no configurado
          </p>
        ) : (
          <p className={`text-label-md font-semibold ${textMap[tone]}`}>
            Sincronización completada
          </p>
        )}
        <ul className="mt-xs space-y-base text-label-sm text-on-surface">
          {result.enviadas > 0 && <li>✓ {result.enviadas} nota{result.enviadas !== 1 ? 's' : ''} enviada{result.enviadas !== 1 ? 's' : ''} a Moodle</li>}
          {result.fallidas > 0 && <li>✗ {result.fallidas} fallida{result.fallidas !== 1 ? 's' : ''}</li>}
          {result.sin_token > 0 && (
            <li>
              {result.sin_token} sin token
              {todoSinToken && ' — Configurá el token de Moodle en Configuración del sistema para habilitar la sincronización.'}
            </li>
          )}
        </ul>
        {result.mensaje && !todoSinToken && (
          <p className="mt-xs text-label-sm text-on-surface-variant">{result.mensaje}</p>
        )}
      </div>
      <button type="button" onClick={onClose} aria-label="Cerrar" className="text-on-surface-variant hover:text-on-surface shrink-0">
        <Icon name="close" className="text-[18px]" />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sección: Preguntas del examen (opción B — el docente elige qué preguntas
// del pool importado forman el examen que rinde el alumno).
// ---------------------------------------------------------------------------

const TIPO_PREGUNTA_LABEL: Record<string, string> = {
  multichoice: 'Opción múltiple',
  truefalse: 'Verdadero / Falso',
};

function tipoLabel(tipo: string): string {
  return TIPO_PREGUNTA_LABEL[tipo] ?? tipo;
}

function PreguntasSeleccionSection({
  examenId,
  onSeleccionGuardada,
}: {
  examenId: string;
  onSeleccionGuardada: (cantidad: number) => void;
}) {
  const [preguntas, setPreguntas] = useState<PreguntaSeleccion[]>([]);
  const [total, setTotal] = useState(0);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState<string | null>(null);

  const [guardando, setGuardando] = useState(false);
  const [okGuardado, setOkGuardado] = useState(false);
  const [errorGuardar, setErrorGuardar] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setErrorCarga(null);
    try {
      const resp = await getPreguntasExamen(examenId);
      setPreguntas(resp.items);
      setTotal(resp.total);
    } catch (err: unknown) {
      setErrorCarga(err instanceof Error ? err.message : 'No se pudieron cargar las preguntas.');
      setPreguntas([]);
      setTotal(0);
    } finally {
      setCargando(false);
    }
  }, [examenId]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const seleccionadas = preguntas.filter((p) => p.seleccionada).length;
  const ningunaMarcada = seleccionadas === 0;

  function toggle(id: string) {
    setOkGuardado(false);
    setPreguntas((prev) =>
      prev.map((p) => (p.id === id ? { ...p, seleccionada: !p.seleccionada } : p)),
    );
  }

  function setTodas(valor: boolean) {
    setOkGuardado(false);
    setPreguntas((prev) => prev.map((p) => ({ ...p, seleccionada: valor })));
  }

  async function guardar() {
    if (ningunaMarcada) return;
    setGuardando(true);
    setOkGuardado(false);
    setErrorGuardar(null);
    const ids = preguntas.filter((p) => p.seleccionada).map((p) => p.id);
    try {
      const res = await setPreguntasSeleccion(examenId, ids);
      setOkGuardado(true);
      onSeleccionGuardada(res.seleccionadas);
    } catch (err: unknown) {
      setErrorGuardar(err instanceof Error ? err.message : 'No se pudo guardar la selección.');
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Card>
      <SectionTitle
        sub={
          cargando
            ? 'Cargando preguntas…'
            : errorCarga
              ? undefined
              : `${seleccionadas} de ${total} pregunta${total !== 1 ? 's' : ''} seleccionada${seleccionadas !== 1 ? 's' : ''}`
        }
        action={
          !cargando && !errorCarga && preguntas.length > 0 ? (
            <div className="flex items-center gap-xs">
              <Button variant="ghost" size="sm" onClick={() => setTodas(true)} disabled={guardando}>
                Seleccionar todas
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setTodas(false)} disabled={guardando}>
                Quitar todas
              </Button>
            </div>
          ) : undefined
        }
      >
        Preguntas del examen
      </SectionTitle>

      {cargando && (
        <div className="space-y-2 animate-pulse">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-14 bg-surface-container-high rounded-lg" />
          ))}
        </div>
      )}

      {!cargando && errorCarga && (
        <div className="space-y-md">
          <div className="flex items-center gap-sm text-error bg-error-container/40 rounded-xl px-md py-sm text-label-sm">
            <Icon name="error" className="text-[18px] shrink-0" fill />
            {errorCarga}
          </div>
          <Button variant="outline" size="sm" icon="refresh" onClick={cargar}>
            Reintentar
          </Button>
        </div>
      )}

      {!cargando && !errorCarga && preguntas.length === 0 && (
        <div className="text-center py-xl text-on-surface-variant space-y-base">
          <Icon name="quiz" className="text-[40px] text-outline" />
          <p className="text-label-md">Este examen no tiene preguntas en el pool importado.</p>
        </div>
      )}

      {!cargando && !errorCarga && preguntas.length > 0 && (
        <div className="space-y-md">
          {/* Banners de guardado */}
          {okGuardado && (
            <div className="flex items-center gap-sm text-success bg-success-container rounded-xl px-md py-sm text-label-sm">
              <Icon name="check_circle" className="text-[18px] shrink-0" fill />
              Selección guardada.
            </div>
          )}
          {errorGuardar && (
            <div className="flex items-center gap-sm text-error bg-error-container/40 rounded-xl px-md py-sm text-label-sm">
              <Icon name="error" className="text-[18px] shrink-0" fill />
              {errorGuardar}
            </div>
          )}

          {/* Lista de preguntas */}
          <ul className="space-y-xs">
            {preguntas.map((p) => (
              <li key={p.id}>
                <label
                  className={`flex items-start gap-sm p-md rounded-xl border cursor-pointer select-none transition-colors
                    ${p.seleccionada
                      ? 'border-primary/40 bg-primary-fixed/30'
                      : 'border-outline-variant/40 hover:bg-surface-container-low'}`}
                >
                  <input
                    type="checkbox"
                    checked={p.seleccionada}
                    onChange={() => toggle(p.id)}
                    disabled={guardando}
                    className="w-4 h-4 accent-primary mt-0.5 shrink-0"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-label-md text-on-surface line-clamp-2 break-words">
                      {p.enunciado}
                    </p>
                    <div className="flex items-center gap-xs mt-xs flex-wrap">
                      <Badge tone="neutral">{tipoLabel(p.tipo)}</Badge>
                      <span className="text-label-sm text-on-surface-variant tabular-nums">
                        #{p.orden}
                      </span>
                    </div>
                  </div>
                </label>
              </li>
            ))}
          </ul>

          {/* Aviso de validación mínima */}
          {ningunaMarcada && (
            <div className="flex items-center gap-sm text-warning bg-warning-container rounded-xl px-md py-sm text-label-sm">
              <Icon name="info" className="text-[18px] shrink-0" fill />
              Tenés que dejar al menos 1 pregunta.
            </div>
          )}

          {/* Acción guardar */}
          <div className="flex justify-end">
            <Button
              variant="primary"
              icon={guardando ? undefined : 'save'}
              onClick={guardar}
              disabled={guardando || ningunaMarcada}
            >
              {guardando ? 'Guardando…' : 'Guardar selección'}
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Componente principal
// ---------------------------------------------------------------------------

const PAGE_SIZE_DEFAULT = 25;

export default function ExamDetail() {
  const navigate = useNavigate();
  const examenId = useRouteParam('id');

  // Header del examen
  const [examen, setExamen] = useState<ExamenContenidoResumen | null>(null);
  const [headerError, setHeaderError] = useState<string | null>(null);

  // Tabla de resultados
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

  // Sincronización Moodle
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);
  const [sincronizando, setSincronizando] = useState(false);
  const [errorSync, setErrorSync] = useState<string | null>(null);

  // ---------------------------------------------------------------------------
  // Carga del encabezado
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!examenId) return;
    if (!USE_REAL_BACKEND) {
      setExamen({ id: examenId, titulo: 'Examen demo', cantidad_preguntas: 0, comision_nombre: null, materia_nombre: null });
      return;
    }
    getExamenHeaderFn(API_BASE, authProvider.getToken(), examenId)
      .then(setExamen)
      .catch((err: unknown) => setHeaderError(err instanceof Error ? err.message : String(err)));
  }, [examenId]);

  // ---------------------------------------------------------------------------
  // Carga de resultados (serverside, depende de query)
  // ---------------------------------------------------------------------------

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

  // ---------------------------------------------------------------------------
  // Sincronización con Moodle
  // ---------------------------------------------------------------------------

  async function handleSincronizar() {
    if (!examenId) return;
    setSincronizando(true);
    setErrorSync(null);
    setSyncResult(null);
    try {
      const result = await sincronizarMoodleFn(API_BASE, authProvider.getToken(), examenId);
      setSyncResult(result);
      // Refrescar la tabla para reflejar los estados actualizados
      setQuery((q) => ({ ...q }));
    } catch (err: unknown) {
      setErrorSync(err instanceof Error ? err.message : 'Error al sincronizar con Moodle.');
    } finally {
      setSincronizando(false);
    }
  }

  // ---------------------------------------------------------------------------
  // Pendientes para el botón de sincronizar
  // ---------------------------------------------------------------------------

  const pendientes = resultados.filter((r) => r.estado_moodle === 'pendiente').length;

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

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

        {/* Botón volver */}
        <Button variant="ghost" icon="arrow_back" size="sm" onClick={() => navigate('/admin/examenes')}>
          Volver a la lista
        </Button>

        {/* Header del examen */}
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

        {/* Preguntas del examen (selección del pool) */}
        {USE_REAL_BACKEND && (
          <PreguntasSeleccionSection
            examenId={examenId}
            onSeleccionGuardada={(cantidad) =>
              setExamen((prev) => (prev ? { ...prev, cantidad_preguntas: cantidad } : prev))
            }
          />
        )}

        {/* Tabla de resultados */}
        <Card>
          <SectionTitle sub={USE_REAL_BACKEND ? `${total} resultado${total !== 1 ? 's' : ''}` : 'Modo demo — sin datos reales'}>
            Alumnos que rindieron
          </SectionTitle>

          {/* Banner de resultado de sincronización */}
          {syncResult && (
            <SyncResultBanner result={syncResult} onClose={() => setSyncResult(null)} />
          )}
          {errorSync && (
            <div className="flex items-center gap-sm text-error bg-error-container/40 rounded-xl px-md py-sm text-label-sm mb-md">
              <Icon name="error" className="text-[18px] shrink-0" fill />
              {errorSync}
            </div>
          )}

          {/* Toolbar */}
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

          {/* Contenido de la tabla */}
          {!USE_REAL_BACKEND && (
            <div className="text-center py-xl text-on-surface-variant space-y-base">
              <Icon name="sync_disabled" className="text-[40px] text-outline" />
              <p className="text-label-md">Conectá el backend real para ver los resultados.</p>
            </div>
          )}

          {USE_REAL_BACKEND && cargandoTabla && !resultados.length && (
            <TableSkeleton />
          )}

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
