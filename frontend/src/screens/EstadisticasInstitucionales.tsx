// Página de estadísticas institucionales (C-20). Reemplaza la vista agregada
// que antes no tenía fuente real (materias/comisiones/distribución de scores).
//
// Hace el fetch a GET /stats/resumen (con filtros APLICADOS) y delega el render al
// cuerpo presentacional `EstadisticasBody`, que implementa el contrato de carga
// resiliente (C-73): cargando / error / vacío-real / cargado. Un fetch fallido se
// muestra como error con reintentar — NUNCA como datos en cero.
//
// Filtros: se editan en un borrador y recién se disparan al presionar "Aplicar
// filtros" (panel genérico FiltrosPanel). Export CSV/PDF son acciones de la
// pantalla (fuera del panel de filtros) y usan los filtros ya aplicados.
import { useCallback, useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { HelpButton } from '../ui/HelpButton';
import { Icon } from '../ui/components';
import { FiltrosPanel } from '../ui/FiltrosPanel';
import { STAFF_NAV } from '../ui/nav';
import { api } from '../lib/api';
import type { ExamenContenidoResumen, FiltrosStats, MateriaStat, ResumenStats } from '../lib/types';
import { EstadisticasBody } from './admin/EstadisticasBody';

const SIN_FILTRO: FiltrosStats = {};

export default function EstadisticasInstitucionales() {
  const [data, setData] = useState<ResumenStats | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // `borrador` = lo que se está editando en el panel; `filtros` = lo aplicado (lo
  // que se busca). Recién al "Aplicar filtros" el borrador pasa a ser aplicado.
  const [borrador, setBorrador] = useState<FiltrosStats>(SIN_FILTRO);
  const [filtros, setFiltros] = useState<FiltrosStats>(SIN_FILTRO);
  const [materiasOpts, setMateriasOpts] = useState<MateriaStat[]>([]);
  // Catálogo de exámenes: puebla los selects de "Examen" y "Comisión" (la comisión
  // sale de los propios exámenes; no hay endpoint dedicado y no hace falta).
  const [catalogo, setCatalogo] = useState<ExamenContenidoResumen[]>([]);
  const [exportando, setExportando] = useState<'excel' | 'pdf' | null>(null);

  const cargar = useCallback((f: FiltrosStats) => {
    setCargando(true);
    setError(null);
    api
      .obtenerResumenStats(f)
      .then((r) => {
        setData(r);
        setError(null);
        // Sin filtro de materia, este sumario trae TODAS las materias → pobla el selector.
        if (!f.materia_id && r.por_materia) setMateriasOpts(r.por_materia);
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

  // Catálogo de exámenes (una vez) para poblar los selects de examen/comisión.
  useEffect(() => {
    api.listarExamenesContenido().then(setCatalogo).catch(() => setCatalogo([]));
  }, []);

  const setCampo = (parche: Partial<FiltrosStats>) =>
    setBorrador((prev) => ({ ...prev, ...parche }));

  const aplicar = () => setFiltros(borrador);
  const limpiar = () => {
    setBorrador(SIN_FILTRO);
    setFiltros(SIN_FILTRO);
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

  // Opciones de los selects derivadas del catálogo (comisiones únicas por id).
  const comisionesOpts = Array.from(
    new Map(
      catalogo
        .filter((e) => e.comision_id && e.comision_nombre)
        .map((e) => [e.comision_id as string, e.comision_nombre as string]),
    ).entries(),
  ).map(([id, nombre]) => ({ id, nombre }));

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

  return (
    <StaffShell
      nav={STAFF_NAV}
      title="Estadísticas institucionales"
      subtitle="Métricas agregadas del cuatrimestre: catálogo, sesiones supervisadas y distribución de scores."
      help={
        <HelpButton title="Estadísticas institucionales">
          <p>
            Vista agregada (sin datos personales) del estado del cuatrimestre:
            cuántos exámenes, materias y comisiones hay cargados, cuántas
            sesiones se supervisaron y cómo se reparten los scores.
          </p>
          <p>
            Podés filtrar por materia y por fechas, y descargar todo en CSV o PDF.
            El conteo <strong>&laquo;en riesgo&raquo;</strong> es una señal para
            PRIORIZAR la revisión humana — nunca una sanción ni un veredicto.
          </p>
        </HelpButton>
      }
    >
      {/* Acciones de export — FUERA del panel de filtros. */}
      <div className="mb-md flex justify-end gap-2">
        <button
          type="button"
          onClick={() => exportar('excel')}
          disabled={exportando !== null || cargando}
          className="inline-flex items-center gap-1.5 rounded-md bg-success-600 px-4 py-2 text-[13px] font-semibold text-white hover:bg-success-700 disabled:opacity-60"
        >
          <Icon name={exportando === 'excel' ? 'hourglass_top' : 'grid_on'} className="text-[16px]" fill />
          {exportando === 'excel' ? 'Exportando…' : 'Exportar Excel'}
        </button>
        <button
          type="button"
          onClick={() => exportar('pdf')}
          disabled={exportando !== null || cargando}
          className="inline-flex items-center gap-1.5 rounded-md bg-error-600 px-4 py-2 text-[13px] font-semibold text-white hover:bg-error-700 disabled:opacity-60"
        >
          <Icon name={exportando === 'pdf' ? 'hourglass_top' : 'picture_as_pdf'} className="text-[16px]" fill />
          {exportando === 'pdf' ? 'Exportando…' : 'Exportar PDF'}
        </button>
      </div>

      {/* Panel de filtros genérico. */}
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
              onChange={(e) => setCampo({ materia_id: e.target.value || undefined })}
              className="min-w-[200px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
            >
              <option value="">Todas las materias</option>
              {materiasOpts.map((m) => (
                <option key={m.materia_id} value={m.materia_id}>{m.nombre}</option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Comisión
            <select
              value={borrador.comision_id ?? ''}
              onChange={(e) => setCampo({ comision_id: e.target.value || undefined })}
              className="min-w-[180px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
            >
              <option value="">Todas las comisiones</option>
              {comisionesOpts.map((c) => (
                <option key={c.id} value={c.id}>{c.nombre}</option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Examen
            <select
              value={borrador.examen_id ?? ''}
              onChange={(e) => setCampo({ examen_id: e.target.value || undefined })}
              className="min-w-[200px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
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

      <EstadisticasBody
        cargando={cargando}
        error={error}
        data={data}
        onReintentar={() => cargar(filtros)}
      />
    </StaffShell>
  );
}
