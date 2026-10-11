/**
 * AlumnosInscriptos — pantalla propia para los inscriptos de una comisión.
 *
 * Ruta: /admin/materias/:comisionId/alumnos (roles: tutor, profesor, coordinador, admin_sistema)
 *
 * Antes vivía como panel expandible DENTRO de la fila de la comisión, en
 * Materias y comisiones — compitiendo por espacio con el resto de esa pantalla
 * (formularios de materia/comisión, modales de profesor/coordinador/tutor). Con
 * varios inscriptos el acordeón empujaba todo lo demás fuera de vista.
 *
 * Como pantalla propia sigue el mismo patrón que el resto de los listados
 * server-side del proyecto (ExamList, Auditoria): RefreshBar arriba, los
 * botones de exportar en su propia fila (no adentro del encabezado del
 * listado), FiltrosPanel con búsqueda + estado, y la paginación server-side
 * fuera de la card.
 */
import { useCallback, useEffect, useState } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Button, Badge } from '../ui/components';
import { STAFF_NAV } from '../ui/nav';
import { RefreshBar } from '../ui/RefreshBar';
import { FiltrosPanel } from '../ui/FiltrosPanel';
import { ExportButtons, type FormatoExport } from '../ui/ExportButtons';
import { Pagination, PageSizeSelect } from '../ui/Pagination';
import { ConfirmModal } from '../ui/ConfirmModal';
import { useToast } from '../ui/toast';
import { useNavigate, useRouteParam } from '../lib/router';
import {
  obtenerEncabezadoComision,
  listarAlumnosDeComision,
  inscribirAlumno,
  eliminarInscripcion,
  descargarExport,
  urlExportInscriptos,
  type ComisionEncabezado,
  type EstadoElegibilidadFiltro,
} from '../lib/examContentAdmin';
import { AlumnoPickerModal } from './admin/components/AlumnoPickerModal';
import type { AlumnoInscripto } from '../lib/types';

const PAGE_SIZE_DEFAULT = 10;
const PAGE_SIZE_OPTIONS = [10, 25, 50, 100];

const ESTADOS_ELEGIBILIDAD: { valor: EstadoElegibilidadFiltro; label: string }[] = [
  { valor: '', label: 'Todos' },
  { valor: 'puede_rendir', label: 'Puede rendir' },
  { valor: 'no_puede_rendir', label: 'No puede rendir' },
];

function nombreAlumno(a: AlumnoInscripto): string {
  const completo = [a.nombre, a.apellido].filter(Boolean).join(' ').trim();
  return completo || a.username;
}

function CondicionBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <Badge tone={ok ? 'success' : 'neutral'} className="text-[11px]">
      <Icon name={ok ? 'check_circle' : 'cancel'} className="text-[14px]" fill />
      {label}
    </Badge>
  );
}

interface Query {
  q: string;
  estado: EstadoElegibilidadFiltro;
  page: number;
  page_size: number;
}

export default function AlumnosInscriptos() {
  const navigate = useNavigate();
  const toast = useToast();
  const comisionId = useRouteParam('comisionId');

  const [encabezado, setEncabezado] = useState<ComisionEncabezado | null>(null);
  const [errorEncabezado, setErrorEncabezado] = useState<string | null>(null);

  useEffect(() => {
    if (!comisionId) return;
    setErrorEncabezado(null);
    obtenerEncabezadoComision(comisionId)
      .then(setEncabezado)
      .catch((err: unknown) => {
        const e = err as Error & { status?: number };
        setErrorEncabezado(e.status === 404 ? 'No se encontró la comisión.' : 'No se pudo cargar la comisión.');
      });
  }, [comisionId]);

  // ── Listado paginado + filtros (server-side, mismo patrón que ExamList) ────
  const [query, setQuery] = useState<Query>({ q: '', estado: '', page: 1, page_size: PAGE_SIZE_DEFAULT });
  const [borradorQ, setBorradorQ] = useState('');
  const [borradorEstado, setBorradorEstado] = useState<EstadoElegibilidadFiltro>('');

  const [alumnos, setAlumnos] = useState<AlumnoInscripto[] | null>(null);
  const [total, setTotal] = useState(0);
  // Cuántos hay inscriptos en la comisión EN TOTAL, sin filtro. Pareja de
  // `noPuedenRendir` en el aviso — mezclarlo con `total` (el filtrado) da
  // lecturas sin sentido ("1 de 0 inscriptos") en cuanto el filtro no matchea.
  const [totalComision, setTotalComision] = useState(0);
  // Cuántos del TOTAL de la comisión no pueden rendir. Viene del backend porque
  // se calcula sobre TODOS los inscriptos, no sobre el filtro/página actual.
  const [noPuedenRendir, setNoPuedenRendir] = useState(0);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | undefined>();

  const [pickerAbierto, setPickerAbierto] = useState(false);
  const [inscribiendo, setInscribiendo] = useState(false);
  const [aQuitar, setAQuitar] = useState<AlumnoInscripto | null>(null);
  const [descargando, setDescargando] = useState<FormatoExport | null>(null);

  const cargar = useCallback(async () => {
    if (!comisionId) return;
    setCargando(true);
    setError(null);
    try {
      const data = await listarAlumnosDeComision(comisionId, {
        page: query.page,
        page_size: query.page_size,
        q: query.q || undefined,
        estado: query.estado || undefined,
      });
      setAlumnos(data.items);
      setTotal(data.total);
      setTotalComision(data.total_comision ?? data.total);
      setNoPuedenRendir(data.no_pueden_rendir ?? 0);
      setLastUpdatedAt(Date.now());
    } catch (err) {
      const e = err as Error & { status?: number };
      setError(
        e.status === 404
          ? 'No se encontró la comisión.'
          : 'No se pudieron cargar los alumnos inscriptos.',
      );
      setAlumnos([]);
    } finally {
      setCargando(false);
    }
  }, [comisionId, query]);

  useEffect(() => { void cargar(); }, [cargar]);

  const aplicarBusqueda = () =>
    setQuery((q) => ({ ...q, q: borradorQ.trim(), estado: borradorEstado, page: 1 }));
  const limpiarBusqueda = () => {
    setBorradorQ('');
    setBorradorEstado('');
    setQuery((q) => ({ ...q, q: '', estado: '', page: 1 }));
  };
  const hayCambiosBusqueda = borradorQ.trim() !== query.q || borradorEstado !== query.estado;
  const hayFiltrosActivos = Boolean(borradorQ || borradorEstado || query.q || query.estado);
  const hayFiltrosAplicados = Boolean(query.q || query.estado);

  async function exportar(formato: FormatoExport) {
    if (!comisionId) return;
    // El backend nombra la planilla `xlsx`; los botones hablan de «Excel», que es
    // lo que la gente busca. La traducción vive acá, en el borde.
    const extension = formato === 'excel' ? 'xlsx' : 'pdf';
    setDescargando(formato);
    try {
      await descargarExport(
        urlExportInscriptos(comisionId, extension),
        `inscriptos-${encabezado?.nombre ?? comisionId}.${extension}`,
      );
    } catch {
      toast.error('No se pudo generar el archivo. Probá de nuevo.');
    } finally {
      setDescargando(null);
    }
  }

  async function handleInscribir(usuarioIds: string[]) {
    if (!comisionId || usuarioIds.length === 0) return;
    setInscribiendo(true);
    let ok = 0;
    let yaEstaban = 0;
    let fallaron = 0;
    // No hay endpoint batch: inscribimos uno por uno y resumimos el resultado.
    for (const id of usuarioIds) {
      try {
        await inscribirAlumno(comisionId, id);
        ok++;
      } catch (err) {
        const e = err as Error & { status?: number };
        if (e.status === 409) yaEstaban++;
        else fallaron++;
      }
    }
    setPickerAbierto(false);
    setInscribiendo(false);
    await cargar();
    if (ok > 0) toast.success(`${ok} alumno${ok === 1 ? '' : 's'} inscripto${ok === 1 ? '' : 's'} correctamente.`);
    if (yaEstaban > 0) toast.error(`${yaEstaban} ya ${yaEstaban === 1 ? 'estaba inscripto' : 'estaban inscriptos'}.`);
    if (fallaron > 0) toast.error(`${fallaron} no se ${fallaron === 1 ? 'pudo' : 'pudieron'} inscribir.`);
  }

  async function handleQuitar() {
    if (!aQuitar || !comisionId) return;
    const alumno = aQuitar;
    setAQuitar(null);
    try {
      await eliminarInscripcion(comisionId, alumno.usuario_id);
      toast.success('Inscripción eliminada.');
      await cargar();
    } catch (err) {
      const e = err as Error & { status?: number };
      if (e.status === 404) toast.error('El alumno no estaba inscripto.');
      else toast.error('No se pudo quitar la inscripción.');
    }
  }

  if (!comisionId) {
    return (
      <StaffShell nav={STAFF_NAV} title="Alumnos inscriptos">
        <div className="flex items-center gap-sm text-error py-md">
          <Icon name="error" className="text-[20px]" fill />
          <span>No se encontró el id de la comisión.</span>
        </div>
      </StaffShell>
    );
  }

  const inscriptosIds = new Set((alumnos ?? []).map((a) => a.usuario_id));
  const hayResultados = Boolean(alumnos && alumnos.length > 0);
  const totalPaginas = Math.max(1, Math.ceil(total / query.page_size));

  return (
    <StaffShell
      nav={STAFF_NAV}
      title="Alumnos inscriptos"
      subtitle={
        encabezado
          ? `${encabezado.nombre} · ${encabezado.materia_nombre} · ${encabezado.codigo}`
          : undefined
      }
    >
      <div className="space-y-lg animate-in fade-in duration-500">
        <Button variant="ghost" icon="arrow_back" size="sm" onClick={() => navigate('/admin/materias')}>
          Volver
        </Button>

        {errorEncabezado && (
          <div className="flex items-center gap-sm text-error bg-error-container/40 rounded-xl px-md py-sm text-label-sm">
            <Icon name="error" className="text-[18px] shrink-0" fill />
            {errorEncabezado}
          </div>
        )}

        <div className="flex justify-end gap-2">
          <ExportButtons
            exportando={descargando}
            disabled={total === 0}
            onExportar={(f) => void exportar(f)}
          />
        </div>

        <RefreshBar lastUpdatedAt={lastUpdatedAt} cargando={cargando} onActualizar={() => void cargar()} />

        <FiltrosPanel
          onAplicar={aplicarBusqueda}
          onLimpiar={limpiarBusqueda}
          hayFiltros={hayFiltrosActivos}
          hayCambios={hayCambiosBusqueda}
          aplicarDeshabilitado={cargando}
        >
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Buscar
            <input
              type="text"
              value={borradorQ}
              placeholder="Nombre, correo o usuario…"
              onChange={(e) => setBorradorQ(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') aplicarBusqueda(); }}
              className="min-w-[220px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-1 text-[12px] font-medium text-on-surface-variant">
            Estado
            <select
              value={borradorEstado}
              onChange={(e) => setBorradorEstado(e.target.value as EstadoElegibilidadFiltro)}
              className="min-w-[160px] rounded-md border border-surface-300 bg-white px-3 py-2 text-[13px] text-on-surface focus:border-primary focus:outline-none"
            >
              {ESTADOS_ELEGIBILIDAD.map((op) => (
                <option key={op.valor} value={op.valor}>{op.label}</option>
              ))}
            </select>
          </label>
        </FiltrosPanel>

        {/* Inscribir es la acción principal de esta pantalla, pero abajo de los
            filtros y no arriba de todo: ahí compite con el título antes de que
            la persona sepa siquiera de qué comisión está mirando la lista. */}
        <div className="flex justify-end">
          <Button variant="primary" size="sm" icon="person_add" onClick={() => setPickerAbierto(true)}>
            Inscribir alumno
          </Button>
        </div>

        {/* Salud de la comisión ENTERA (no del filtro/página actual): se calcula
            server-side sobre todos los inscriptos. */}
        {noPuedenRendir > 0 && (
          <div
            role="alert"
            className="flex items-start gap-2 rounded-lg bg-error-container/40 px-3 py-2 text-[12px] text-error"
          >
            <Icon name="warning" className="text-[16px] shrink-0 mt-0.5" fill />
            <span>
              <strong>
                {noPuedenRendir} de {totalComision} {totalComision === 1 ? 'inscripto' : 'inscriptos'}
              </strong>{' '}
              {noPuedenRendir === 1 ? 'no va' : 'no van'} a poder rendir: falta que
              completen el consentimiento o la captura biométrica. Cada fila muestra
              qué le falta, y el export lo trae en una columna.
            </span>
          </div>
        )}

        <div className="rounded-xl border border-outline-variant/40 bg-surface overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-outline-variant/20">
            <Icon name="groups" className="text-[16px] text-on-surface-variant shrink-0" />
            <h2 className="text-[14px] font-semibold text-on-surface">
              Alumnos inscriptos
              <span className="ml-1 font-normal text-on-surface-variant">({total})</span>
            </h2>
            <PageSizeSelect
              className="ml-auto"
              value={query.page_size}
              onChange={(ps) => setQuery((q) => ({ ...q, page_size: ps, page: 1 }))}
              options={PAGE_SIZE_OPTIONS}
            />
          </div>

          <div className="px-4 py-3">
            {cargando && !hayResultados ? (
              <div className="py-6 text-center">
                <Icon name="progress_activity" className="ae-spin text-[22px] text-outline" />
              </div>
            ) : error ? (
              <div role="alert" className="flex items-center justify-between gap-xs text-error text-body-sm p-sm rounded-lg bg-error-container">
                <span className="flex items-center gap-xs">
                  <Icon name="error" className="text-[18px] shrink-0" fill />
                  {error}
                </span>
                <Button variant="ghost" size="sm" onClick={() => void cargar()}>Reintentar</Button>
              </div>
            ) : !hayResultados ? (
              <div className="py-6 text-on-surface-variant text-[13px] flex items-center gap-2">
                <Icon name="info" className="text-[16px] shrink-0" />
                {hayFiltrosAplicados
                  ? 'Ningún inscripto coincide con los filtros.'
                  : 'No hay alumnos inscriptos todavía.'}
              </div>
            ) : (
              <ul className="divide-y divide-outline-variant/20 rounded-lg border border-outline-variant/40 overflow-hidden">
                {(alumnos ?? []).map((a) => (
                  <li key={a.usuario_id} className="px-3 py-3 flex flex-col sm:flex-row sm:items-center gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-[13px] font-medium text-on-surface truncate">{nombreAlumno(a)}</p>
                      <p className="text-[11px] text-on-surface-variant truncate">
                        {a.email}
                        <span className="font-mono"> · {a.username}</span>
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-1.5 shrink-0">
                      <CondicionBadge ok={a.consentimiento_vigente} label="Consentimiento" />
                      <CondicionBadge ok={a.biometria_vigente} label="Biometría" />
                      {a.puede_rendir ? (
                        <Badge tone="primary" className="text-[11px]">
                          <Icon name="task_alt" className="text-[14px]" fill />
                          Puede rendir
                        </Badge>
                      ) : (
                        <span title={a.razon ?? undefined}>
                          <Badge tone="error" className="text-[11px]">
                            <Icon name="block" className="text-[14px]" fill />
                            No puede rendir
                          </Badge>
                        </span>
                      )}
                    </div>

                    <button
                      type="button"
                      aria-label={`Quitar inscripción de ${nombreAlumno(a)}`}
                      onClick={() => setAQuitar(a)}
                      className="w-8 h-8 rounded-md flex items-center justify-center text-on-surface-variant hover:bg-error-container hover:text-error transition-colors shrink-0 self-end sm:self-auto"
                    >
                      <Icon name="person_remove" className="text-[18px]" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <Pagination
          currentPage={query.page}
          totalPages={totalPaginas}
          totalElements={total}
          pageSize={query.page_size}
          onPageChange={(p) => setQuery((q) => ({ ...q, page: p }))}
        />
      </div>

      <AlumnoPickerModal
        abierto={pickerAbierto}
        comisionNombre={encabezado?.nombre ?? 'esta comisión'}
        yaInscriptos={inscriptosIds}
        inscribiendo={inscribiendo}
        onConfirmar={(usuarioIds) => void handleInscribir(usuarioIds)}
        onCancelar={() => setPickerAbierto(false)}
      />

      <ConfirmModal
        abierto={aQuitar !== null}
        variante="danger"
        titulo="Quitar inscripción"
        mensaje={
          aQuitar ? (
            <>
              ¿Quitar la inscripción de <strong>{nombreAlumno(aQuitar)}</strong> de{' '}
              <strong>{encabezado?.nombre ?? 'esta comisión'}</strong>?
              <br />
              <span className="text-on-surface-variant text-body-sm">
                El alumno dejará de figurar como inscripto en esta comisión.
              </span>
            </>
          ) : null
        }
        textoConfirmar="Quitar inscripción"
        textoCancelar="Cancelar"
        onConfirmar={() => void handleQuitar()}
        onCancelar={() => setAQuitar(null)}
      />
    </StaffShell>
  );
}
