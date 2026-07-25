// Página de estadísticas institucionales (C-20). Reemplaza la vista agregada
// que antes no tenía fuente real (materias/comisiones/distribución de scores).
//
// Hace el fetch a GET /stats/resumen (con filtros APLICADOS) y delega el render al
// cuerpo presentacional `EstadisticasBody`, que implementa el contrato de carga
// resiliente (C-73): cargando / error / vacío-real / cargado. Un fetch fallido se
// muestra como error con reintentar — NUNCA como datos en cero.
//
// Filtros en cascada: materia → comisión → examen.
// Se editan en un borrador y recién se disparan al presionar "Aplicar filtros".
import { useCallback, useEffect, useRef, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { HelpButton } from '../ui/HelpButton';
import { Icon } from '../ui/components';
import { FiltrosPanel } from '../ui/FiltrosPanel';
import { RefreshBar } from '../ui/RefreshBar';
import { STAFF_NAV } from '../ui/nav';
import { useAutoRefresh } from '../lib/useAutoRefresh';
import { api } from '../lib/api';
import type {
  Comision,
  ExamenContenidoResumen,
  FiltrosStats,
  Materia,
  ResumenStats,
} from '../lib/types';
import { EstadisticasBody } from './admin/EstadisticasBody';

const SIN_FILTRO: FiltrosStats = {};

// ── Utilidades RefreshBar ───────────────────────────────────────────────────

function formatFechaCorta(iso?: string): string {
  if (!iso) return '-';
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return '-';
  return `${parseInt(m[3], 10)}/${parseInt(m[2], 10)}/${parseInt(m[1], 10)}`;
}

// ── Componente principal ────────────────────────────────────────────────────

export default function EstadisticasInstitucionales() {
  const [data, setData] = useState<ResumenStats | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | undefined>();

  const [borrador, setBorrador] = useState<FiltrosStats>(SIN_FILTRO);
  const [filtros, setFiltros] = useState<FiltrosStats>(SIN_FILTRO);

  // Cascada: materias → comisiones → exámenes
  const [materias, setMaterias] = useState<Materia[]>([]);
  const [comisiones, setComisiones] = useState<Comision[]>([]);
  const [catalogo, setCatalogo] = useState<ExamenContenidoResumen[]>([]);

  const [exportando, setExportando] = useState<'excel' | 'pdf' | null>(null);

  // Cargar materias una vez
  useEffect(() => {
    api.materiasDisponibles().then(setMaterias).catch(() => {});
  }, []);

  // Cargar comisiones cuando cambia la materia del borrador
  const prevMateriaRef = useRef<string | undefined>();
  useEffect(() => {
    const mid = borrador.materia_id;
    if (mid === prevMateriaRef.current) return;
    prevMateriaRef.current = mid;
    if (!mid) {
      setComisiones([]);
      setCatalogo([]);
      return;
    }
    api.comisionesDeMateria(mid).then(setComisiones).catch(() => setComisiones([]));
    // Reset cascada
    setCatalogo([]);
  }, [borrador.materia_id]);

  // Cargar exámenes cuando cambia la comisión del borrador
  const prevComisionRef = useRef<string | undefined>();
  useEffect(() => {
    const cid = borrador.comision_id;
    if (cid === prevComisionRef.current) return;
    prevComisionRef.current = cid;
    if (!cid) { setCatalogo([]); return; }
    api.listarExamenesContenido().then((all) =>
      setCatalogo(all.filter((e) => e.comision_id === cid))
    ).catch(() => setCatalogo([]));
  }, [borrador.comision_id]);

  const cargar = useCallback((f: FiltrosStats) => {
    setCargando(true);
    setError(null);
    api
      .obtenerResumenStats(f)
      .then((r) => {
        setData(r);
        setError(null);
        setLastUpdatedAt(Date.now());
      })
      .catch((e: unknown) => {
        const status = (e as { status?: number })?.status;
        setData(null);
        setError(
          status === 403
            ? 'No tenés permisos para ver las estadísticas institucionales.'
            : 'No se pudieron cargar las estadísticas. Revisá tu conexión e intentá de nuevo.',
        );
      })
      .finally(() => setCargando(false));
  }, []);

  useEffect(() => {
    cargar(filtros);
  }, [cargar, filtros]);

  // Auto-refresh cada 5 minutos (pausa en pestaña oculta) para mostrar lo último.
  useAutoRefresh(() => cargar(filtros), undefined, !cargando);

  const setCampo = (parche: Partial<FiltrosStats>) =>
    setBorrador((prev) => ({ ...prev, ...parche }));

  const aplicar = () => setFiltros(borrador);
  const limpiar = () => {
    setBorrador(SIN_FILTRO);
    setFiltros(SIN_FILTRO);
    setComisiones([]);
    setCatalogo([]);
  };

  const hayFiltros = Boolean(
    borrador.materia_id || borrador.comision_id || borrador.examen_id || borrador.desde || borrador.hasta,
  );
  const hayCambios =
    (borrador.materia_id ?? '') !== (filtros.materia_id ?? '') ||
    (borrador.comision_id ?? '') !== (filtros.comision_id ?? '') ||
    (borrador.examen_id ?? '') !== (filtros.examen_id ?? '') ||
    (borrador.desde ?? '') !== (filtros.desde ?? '') ||
    (borrador.hasta ?? '') !== (filtros.hasta ?? '');

  const exportar = async (formato: 'excel' | 'pdf') => {
    setExportando(formato);
    try {
      const blob =
        formato === 'pdf'
          ? await api.descargarResumenPdf(filtros)
          : await api.descargarResumenExcel(filtros);
      const ext = formato === 'pdf' ? 'pdf' : 'xlsx';
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `estadisticas.${ext}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      setError(`No se pudo exportar el ${formato === 'pdf' ? 'PDF' : 'Excel'}. Intentá de nuevo.`);
    } finally {
      setExportando(null);
    }
  };

  // RefreshBar — texto de rango de fechas aplicado
  const rangoTexto =
    filtros.desde || filtros.hasta
      ? `Datos desde ${formatFechaCorta(filtros.desde)} hasta ${formatFechaCorta(filtros.hasta)}`
      : 'Todos los datos disponibles';

  return (
    <StaffShell
      nav={STAFF_NAV}
      title="Estadísticas institucionales"
      subtitle="Métricas agregadas del cuatrimestre: catálogo, sesiones registradas y distribución de scores."
      help={
        <HelpButton title="Estadísticas institucionales">
          <p>
            Vista agregada (sin datos personales) del estado del cuatrimestre:
            cuántos exámenes, materias y comisiones hay cargados, cuántas
            sesiones se registraron y cómo se reparten los scores.
          </p>
          <p>
            Podés filtrar por materia, comisión y examen en cascada, y por rango de fechas.
            Podés descargar todo en Excel o PDF. El conteo{' '}
            <strong>&laquo;en riesgo&raquo;</strong> es una señal para PRIORIZAR la
            revisión humana — nunca una sanción ni un veredicto.
          </p>
        </HelpButton>
      }
    >
      {/* Acciones de export */}
      <div className="mb-md flex justify-end gap-2">
        <button
          type="button"
          onClick={() => exportar('excel')}
          disabled={exportando !== null || cargando}
          className="inline-flex items-center gap-1.5 rounded-md bg-success-600 px-4 py-2 text-[13px] font-semibold text-white hover:bg-success-700 disabled:opacity-60"
        >
          <Icon name={exportando === 'excel' ? 'progress_activity' : 'grid_on'} className={`text-[16px] ${exportando === 'excel' ? 'ae-spin' : ''}`} fill />
          {exportando === 'excel' ? 'Exportando…' : 'Exportar Excel'}
        </button>
        <button
          type="button"
          onClick={() => exportar('pdf')}
          disabled={exportando !== null || cargando}
          className="inline-flex items-center gap-1.5 rounded-md bg-error-600 px-4 py-2 text-[13px] font-semibold text-white hover:bg-error-700 disabled:opacity-60"
        >
          <Icon name={exportando === 'pdf' ? 'progress_activity' : 'picture_as_pdf'} className={`text-[16px] ${exportando === 'pdf' ? 'ae-spin' : ''}`} fill />
          {exportando === 'pdf' ? 'Exportando…' : 'Exportar PDF'}
        </button>
      </div>

      {/* RefreshBar — rango aplicado + hora de última carga + botón actualizar */}
      <RefreshBar
        texto={rangoTexto}
        lastUpdatedAt={lastUpdatedAt}
        cargando={cargando}
        onActualizar={() => cargar(filtros)}
      />

      {/* Panel de filtros en cascada */}
      <div className="mb-lg">
        <FiltrosPanel
          onAplicar={aplicar}
          onLimpiar={limpiar}
          hayFiltros={hayFiltros}
          hayCambios={hayCambios}
          aplicarDeshabilitado={cargando}
        >
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Materia
            <select
              value={borrador.materia_id ?? ''}
              onChange={(e) => {
                const v = e.target.value || undefined;
                setBorrador({ ...SIN_FILTRO, materia_id: v, desde: borrador.desde, hasta: borrador.hasta });
              }}
              className="min-w-[200px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
            >
              <option value="">Todas las materias</option>
              {materias.map((m) => (
                <option key={m.id} value={m.id}>{m.nombre}</option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Comisión
            <select
              value={borrador.comision_id ?? ''}
              onChange={(e) => {
                const v = e.target.value || undefined;
                setBorrador((prev) => ({ ...prev, comision_id: v, examen_id: undefined }));
              }}
              disabled={!borrador.materia_id || comisiones.length === 0}
              className="min-w-[180px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none disabled:opacity-50"
            >
              <option value="">Todas las comisiones</option>
              {comisiones.map((c) => (
                <option key={c.id} value={c.id}>{c.nombre}</option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Examen
            <select
              value={borrador.examen_id ?? ''}
              onChange={(e) => setCampo({ examen_id: e.target.value || undefined })}
              disabled={!borrador.comision_id || catalogo.length === 0}
              className="min-w-[200px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none disabled:opacity-50"
            >
              <option value="">Todos los exámenes</option>
              {catalogo.map((e) => (
                <option key={e.id} value={e.id}>{e.titulo}</option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Desde
            <input
              type="date"
              value={borrador.desde?.slice(0, 10) ?? ''}
              onChange={(e) => setCampo({ desde: e.target.value ? `${e.target.value}T00:00:00` : undefined })}
              className="rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
            />
          </label>

          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Hasta
            <input
              type="date"
              value={borrador.hasta?.slice(0, 10) ?? ''}
              onChange={(e) => setCampo({ hasta: e.target.value ? `${e.target.value}T23:59:59` : undefined })}
              className="rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
            />
          </label>
        </FiltrosPanel>
      </div>

      <div className="mt-lg">
        <EstadisticasBody
          cargando={cargando}
          error={error}
          data={data}
          onReintentar={() => cargar(filtros)}
        />
      </div>
    </StaffShell>
  );
}
