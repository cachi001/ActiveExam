/**
 * MateriasComisiones — gestión admin de materias y comisiones (C-69).
 *
 * Ruta: /admin/materias (roles: admin_sistema)
 *
 * Funcionalidades:
 *  - Listar materias con acordeón de comisiones (carga lazy por materia).
 *  - Crear / editar materia (formulario inline sobre la lista).
 *  - Crear / editar comisión (formulario inline dentro de la sección expandida).
 *
 * Lee datos con api.materiasDisponibles() / api.comisionesDeMateria() que
 * manejan demo-mode. Escribe con crearMateria / actualizarMateria / crearComision /
 * actualizarComision de examContentAdmin (requieren backend real; en modo demo
 * muestran error de red esperado).
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { StaffShell } from '../ui/shells';
import { Icon, Button } from '../ui/components';
import { HelpButton } from '../ui/HelpButton';
import { ActionMenu } from '../ui/ActionMenu';
import { RefreshBar } from '../ui/RefreshBar';
import { STAFF_NAV } from '../ui/nav';
import { useAutoRefresh } from '../lib/useAutoRefresh';
import { useToast } from '../ui/toast';
import { useAuth } from '../lib/authStore';
import { tieneCapacidad } from '../lib/capabilities';
import {
  contarDeBaja,
  filtrarPorEstado,
  OPCIONES_ESTADO_BAJA,
  type EstadoBajaFiltro,
} from './materias/filtroEstado';
import { api } from '../lib/api';
import {
  crearMateria,
  actualizarMateria,
  crearComision,
  actualizarComision,
  darDeBajaMateria,
  reactivarMateria,
  darDeBajaComision,
  reactivarComision,
  impactoBajaMateria,
  impactoBajaComision,
  type ImpactoBaja,
} from '../lib/examContentAdmin';
import type { Materia, Comision } from '../lib/types';
import { ConfirmModal } from '../ui/ConfirmModal';
import { AvisoImpactoBaja } from '../ui/AvisoImpactoBaja';
import { AvisoSinResponsable } from '../ui/AvisoSinResponsable';
import { MateriaFormPanel } from './admin/components/MateriaFormPanel';
import {
  AsignarCoordinadorDialog,
  AsignarProfesorDialog,
} from './admin/components/AsignarCoordinadorDialog';
import { ComisionesAccordionBody } from './admin/components/ComisionesAccordionBody';
import {
  FORM_MATERIA_VACIO,
  FORM_COMISION_VACIO,
  mensajeDeError,
  type FormMateria,
  type FormComision,
} from './admin/components/materiasComisionesTypes';

// c-78 §18.4: la materia no tiene a NADIE a cargo. En producción las tres
// materias estaban así y nada lo advertía. El listado solo llena estas dos listas
// para staff y coordinador; en cualquier otro rol vienen vacías y el aviso no
// aplica — pero esta pantalla es admin-only, así que acá el dato siempre está.
function sinResponsable(m: Materia): boolean {
  return (m.coordinadores?.length ?? 0) === 0 && (m.profesores?.length ?? 0) === 0;
}

export default function MateriasComisiones() {
  const toast = useToast();

  // La ESTRUCTURA académica (crear/editar/borrar materias y comisiones) es
  // admin-only. El tutor puede inscribir y ver, pero no crear estructura — el
  // backend lo enforcea (`gestionar_estructura`); acá solo ocultamos los botones.
  const roles = useAuth((s) => s.principal?.roles) ?? [];
  const puedeEditarEstructura = tieneCapacidad(roles, 'gestionar_estructura');

  // ── Materias ──────────────────────────────────────────────────────────────
  const [materias, setMaterias] = useState<Materia[]>([]);
  const [cargandoMaterias, setCargandoMaterias] = useState(true);
  // c-78 E-13 / D16: "no pudo cargar" NO es lo mismo que "cargó y está vacío".
  // Un 401 se dibujaba como "No hay materias registradas", y alguien podía
  // recrear a mano materias que ya existían. Son tres estados, no dos.
  const [errorMaterias, setErrorMaterias] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | undefined>();

  // Filtro de baja lógica. Arranca en 'activa': quien entra a gestionar materias
  // viene a ver las vigentes. Antes no existía, así que las dadas de baja
  // quedaban mezcladas con un cartel y no había forma de aislarlas para
  // reactivarlas ni de sacarlas de la vista.
  const [estadoMaterias, setEstadoMaterias] = useState<EstadoBajaFiltro>('activa');
  const [estadoComisiones, setEstadoComisiones] = useState<EstadoBajaFiltro>('activa');
  const materiasVisibles = filtrarPorEstado(materias, estadoMaterias);
  const materiasDeBaja = contarDeBaja(materias);

  // ── Acordeón ──────────────────────────────────────────────────────────────
  const [expandida, setExpandida] = useState<string | null>(null);
  const [comisionesPorMateria, setComisionesPorMateria] = useState<Record<string, Comision[]>>({});
  const [cargandoComisiones, setCargandoComisiones] = useState<Record<string, boolean>>({});
  // D16: por materia, el motivo por el que sus comisiones no cargaron. null/ausente
  // = no hubo error. Distinto de una lista vacia (materia sin comisiones).
  const [errorComisiones, setErrorComisiones] = useState<Record<string, string | null>>({});

  // ── Comisión expandida (para ver/gestionar alumnos inscriptos) ─────────────
  const [comisionExpandida, setComisionExpandida] = useState<string | null>(null);

  function toggleComision(comisionId: string) {
    setComisionExpandida((prev) => (prev === comisionId ? null : comisionId));
  }

  // ── Formulario de materia ─────────────────────────────────────────────────
  const [formMateria, setFormMateria] = useState<FormMateria | null>(null);
  const [errorFormMateria, setErrorFormMateria] = useState<string | null>(null);
  const [enviandoMateria, setEnviandoMateria] = useState(false);
  const primerInputMateriaRef = useRef<HTMLInputElement>(null);

  // ── Formulario de comisión ────────────────────────────────────────────────
  const [formComision, setFormComision] = useState<FormComision | null>(null);
  const [errorFormComision, setErrorFormComision] = useState<string | null>(null);
  const [enviandoComision, setEnviandoComision] = useState(false);
  const primerInputComisionRef = useRef<HTMLInputElement>(null);
  const [periodos, setPeriodos] = useState<{ value: string; label: string }[]>([
    { value: '1C', label: '1er cuatrimestre' },
    { value: '2C', label: '2do cuatrimestre' },
  ]);

  // ── Coordinadores de la materia (c-79) ────────────────────────────────────
  // Sin esta pantalla el rol coordinador queda inutilizable: desde c-79 dejó de
  // tener alcance institucional y solo ve las materias que tiene asignadas.
  const [coordinandoMateria, setCoordinandoMateria] = useState<Materia | null>(null);
  // c-78: el PROFESOR es el otro rol de materia. Se asigna igual que el
  // coordinador pero es una membresía distinta: no habilita el veredicto.
  const [asignandoProfesor, setAsignandoProfesor] = useState<Materia | null>(null);

  // Baja pendiente de confirmación (c-78, Opción C). Desactivar dejó de ser un
  // click directo: primero se consulta qué se lleva puesto (cuántas rendiciones
  // ya tiene, si hay gente rindiendo AHORA) y recién ahí se confirma. Reactivar
  // sigue siendo directo — no rompe nada.
  const [pendienteBaja, setPendienteBaja] = useState<
    { tipo: 'materia' | 'comision'; id: string; nombre: string; materiaId?: string } | null
  >(null);
  const [impactoBaja, setImpactoBaja] = useState<ImpactoBaja | null>(null);
  const [cargandoImpacto, setCargandoImpacto] = useState(false);
  const [dandoDeBaja, setDandoDeBaja] = useState(false);

  // El impacto se pide al abrir el diálogo. Si la consulta falla, el diálogo
  // sigue sirviendo sin el aviso: el servidor es igual la autoridad (rechaza con
  // 409 si hay gente rindiendo).
  useEffect(() => {
    if (!pendienteBaja) { setImpactoBaja(null); setCargandoImpacto(false); return; }
    const { tipo, id } = pendienteBaja;
    let vigente = true;
    setCargandoImpacto(true);
    (tipo === 'materia' ? impactoBajaMateria(id) : impactoBajaComision(id))
      .then((i) => { if (vigente) setImpactoBaja(i); })
      .catch(() => { if (vigente) setImpactoBaja(null); })
      .finally(() => { if (vigente) setCargandoImpacto(false); });
    return () => { vigente = false; };
  }, [pendienteBaja]);

  // Baja / reactivación de una materia (c-78). UN SOLO patrón en todo el sistema:
  // `DELETE /{id}` da de baja, `POST /{id}/reactivar` la revierte — igual que
  // usuario y examen. La materia de baja no se le oculta al alumno ya inscripto;
  // corta inscripciones nuevas y bloquea rendir (server-side). Nada se borra.
  async function toggleActivaMateria(m: Materia) {
    if (m.activa ?? true) {
      setPendienteBaja({ tipo: 'materia', id: m.id, nombre: m.nombre });
      return;
    }
    try {
      await reactivarMateria(m.id);
      setMaterias((prev) => prev.map((x) => (x.id === m.id ? { ...x, activa: true } : x)));
      toast.success('Materia reactivada.');
    } catch {
      toast.error('No se pudo reactivar la materia.');
    }
  }

  // Ídem para una comisión: afecta SOLO a esa comisión (corta inscripciones por
  // su código y bloquea iniciar sus exámenes). No desmatricula a nadie.
  async function toggleActivaComision(materiaId: string, c: Comision) {
    if (c.activa ?? true) {
      setPendienteBaja({ tipo: 'comision', id: c.id, nombre: c.nombre, materiaId });
      return;
    }
    try {
      await reactivarComision(c.id);
      setComisionesPorMateria((prev) => ({
        ...prev,
        [materiaId]: (prev[materiaId] ?? []).map((x) =>
          x.id === c.id ? { ...x, activa: true } : x,
        ),
      }));
      toast.success('Comisión reactivada.');
    } catch {
      toast.error('No se pudo reactivar la comisión.');
    }
  }

  async function confirmarBaja() {
    const target = pendienteBaja;
    if (!target) return;
    setDandoDeBaja(true);
    try {
      if (target.tipo === 'materia') {
        await darDeBajaMateria(target.id);
        setMaterias((prev) =>
          prev.map((x) => (x.id === target.id ? { ...x, activa: false } : x)),
        );
        toast.success(
          'Materia dada de baja. No se borró nada: podés reactivarla cuando quieras.',
        );
      } else if (target.materiaId) {
        const mid = target.materiaId;
        await darDeBajaComision(target.id);
        setComisionesPorMateria((prev) => ({
          ...prev,
          [mid]: (prev[mid] ?? []).map((x) =>
            x.id === target.id ? { ...x, activa: false } : x,
          ),
        }));
        toast.success('Comisión dada de baja. No se desmatriculó a nadie.');
      }
    } catch (err) {
      // 409 = hay gente rindiendo en este momento. El backend dice a cuántos
      // iba a afectar; taparlo con un mensaje genérico manda a reintentar algo
      // que reintentar no arregla.
      const detalle = err instanceof Error ? err.message : '';
      toast.error(
        detalle ||
          `No se pudo dar de baja la ${target.tipo === 'materia' ? 'materia' : 'comisión'}.`,
      );
    } finally {
      setDandoDeBaja(false);
      setPendienteBaja(null);
    }
  }

  useEffect(() => {
    api.listarPeriodos().then(setPeriodos).catch(() => {/* usa fallback */});
  }, []);

  // ── Carga inicial de materias ─────────────────────────────────────────────

  const cargarMaterias = useCallback(async () => {
    setCargandoMaterias(true);
    setErrorMaterias(null);
    try {
      // strict: sin esto el cliente devuelve [] ante un 401 y el `catch` de
      // abajo nunca corre — que es exactamente el bug E-13.
      const data = await api.materiasDisponibles(true);
      setMaterias(data);
      setLastUpdatedAt(Date.now());
    } catch (err: unknown) {
      const status = (err as { status?: number })?.status;
      setErrorMaterias(
        status === 401
          ? 'Tu sesión expiró. Cerrá sesión, volvé a entrar y reintentá.'
          : status === 403
            ? 'No tenés permiso para ver las materias.'
            : 'No se pudo cargar la lista de materias. Puede ser la conexión o el servidor.',
      );
      // NO se degrada a []: eso afirmaría que no hay materias, y no lo sabemos.
      toast.error('No se pudo cargar la lista de materias.');
    } finally {
      setCargandoMaterias(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { void cargarMaterias(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-refresh cada 5 min: los conteos de inscriptos/exámenes pueden cambiar.
  useAutoRefresh(() => void cargarMaterias(), undefined, !cargandoMaterias);

  // Escape cierra el formulario activo
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      if (formMateria) cerrarFormMateria();
      else if (formComision) cerrarFormComision();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formMateria, formComision]);

  // ── Acordeón ──────────────────────────────────────────────────────────────

  // Master-detail: seleccionar una materia carga sus comisiones en el panel derecho.
  async function seleccionarMateria(materiaId: string) {
    if (formComision && formComision.materiaId !== materiaId) cerrarFormComision();
    setExpandida(materiaId);
    if (!comisionesPorMateria[materiaId]) {
      setCargandoComisiones((prev) => ({ ...prev, [materiaId]: true }));
      try {
        const data = await api.comisionesDeMateria(materiaId, true);
        setComisionesPorMateria((prev) => ({ ...prev, [materiaId]: data }));
        setErrorComisiones((prev) => ({ ...prev, [materiaId]: null }));
      } catch {
        // D16: NO se cachea [] como si la materia no tuviera comisiones — se
        // marca el error y la proxima apertura vuelve a intentar.
        toast.error('No se pudieron cargar las comisiones.');
        setErrorComisiones((prev) => ({
          ...prev,
          [materiaId]: 'No se pudieron cargar las comisiones de esta materia.',
        }));
      } finally {
        setCargandoComisiones((prev) => ({ ...prev, [materiaId]: false }));
      }
    }
  }
  const toggleExpand = seleccionarMateria;

  // Auto-seleccionar la primera materia para que el panel derecho no quede vacío.
  useEffect(() => {
    if (!expandida && materias.length > 0) void seleccionarMateria(materias[0].id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [materias]);

  // ── Formulario de materia ─────────────────────────────────────────────────

  function abrirCrearMateria() {
    setFormMateria({ ...FORM_MATERIA_VACIO, modo: 'crear' });
    setErrorFormMateria(null);
    setTimeout(() => primerInputMateriaRef.current?.focus(), 50);
  }

  function abrirEditarMateria(m: Materia) {
    setFormMateria({ modo: 'editar', id: m.id, codigo: m.codigo, nombre: m.nombre });
    setErrorFormMateria(null);
    setTimeout(() => primerInputMateriaRef.current?.focus(), 50);
  }

  function cerrarFormMateria() {
    setFormMateria(null);
    setErrorFormMateria(null);
  }

  async function handleSubmitMateria(e: React.FormEvent) {
    e.preventDefault();
    if (!formMateria) return;
    setErrorFormMateria(null);
    setEnviandoMateria(true);
    try {
      if (formMateria.modo === 'crear') {
        const nueva = await crearMateria({ codigo: formMateria.codigo, nombre: formMateria.nombre });
        setMaterias((prev) => [...prev, { ...nueva }]);
        toast.success('Materia creada correctamente.');
      } else if (formMateria.modo === 'editar' && formMateria.id) {
        const actualizada = await actualizarMateria(formMateria.id, {
          nombre: formMateria.nombre,
          codigo: formMateria.codigo,
        });
        setMaterias((prev) =>
          prev.map((m) =>
            m.id === formMateria.id
              ? { ...m, nombre: actualizada.nombre, codigo: actualizada.codigo }
              : m,
          ),
        );
        toast.success('Materia actualizada correctamente.');
      }
      cerrarFormMateria();
    } catch (err) {
      setErrorFormMateria(mensajeDeError(err, 'materia'));
    } finally {
      setEnviandoMateria(false);
    }
  }

  // ── Formulario de comisión ────────────────────────────────────────────────

  function abrirCrearComision(materiaId: string) {
    if (expandida !== materiaId) void toggleExpand(materiaId);
    setFormComision({ ...FORM_COMISION_VACIO, modo: 'crear', materiaId });
    setErrorFormComision(null);
    setTimeout(() => primerInputComisionRef.current?.focus(), 80);
  }

  function abrirEditarComision(materiaId: string, c: Comision) {
    if (expandida !== materiaId) void toggleExpand(materiaId);
    setFormComision({
      modo: 'editar',
      materiaId,
      comisionId: c.id,
      codigo: c.codigo ?? '',
      nombre: c.nombre,
      periodo: c.periodo ?? '',
      anio: c.anio != null ? String(c.anio) : '',
      codigoMatriculacion: c.codigo_matriculacion ?? '',
    });
    setErrorFormComision(null);
    setTimeout(() => primerInputComisionRef.current?.focus(), 80);
  }

  function cerrarFormComision() {
    setFormComision(null);
    setErrorFormComision(null);
  }

  async function handleSubmitComision(e: React.FormEvent) {
    e.preventDefault();
    if (!formComision) return;
    setErrorFormComision(null);
    setEnviandoComision(true);
    const anioNum = formComision.anio ? parseInt(formComision.anio, 10) : null;
    const periodoVal = formComision.periodo.trim() || null;
    try {
      if (formComision.modo === 'crear') {
        const nueva = await crearComision(formComision.materiaId, {
          codigo: formComision.codigo,
          nombre: formComision.nombre,
          periodo: periodoVal,
          anio: anioNum,
          codigo_matriculacion: formComision.codigoMatriculacion.trim() || null,
        });
        setComisionesPorMateria((prev) => ({
          ...prev,
          [formComision.materiaId]: [...(prev[formComision.materiaId] ?? []), { ...nueva }],
        }));
        toast.success('Comisión creada correctamente.');
      } else if (formComision.modo === 'editar' && formComision.comisionId) {
        const actualizada = await actualizarComision(formComision.comisionId, {
          nombre: formComision.nombre,
          periodo: periodoVal,
          anio: anioNum,
          codigo_matriculacion: formComision.codigoMatriculacion.trim() || null,
        });
        setComisionesPorMateria((prev) => {
          const list = prev[formComision.materiaId] ?? [];
          return {
            ...prev,
            [formComision.materiaId]: list.map((c) =>
              c.id === formComision.comisionId
                ? {
                    ...c,
                    nombre: actualizada.nombre,
                    periodo: actualizada.periodo,
                    anio: actualizada.anio,
                    codigo_matriculacion: actualizada.codigo_matriculacion,
                  }
                : c,
            ),
          };
        });
        toast.success('Comisión actualizada correctamente.');
      }
      cerrarFormComision();
    } catch (err) {
      setErrorFormComision(mensajeDeError(err, 'comision'));
    } finally {
      setEnviandoComision(false);
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <StaffShell
      nav={STAFF_NAV}
      title="Materias y comisiones"
      subtitle="Creá y gestioná materias y sus comisiones de cursado."
      help={
        <HelpButton title="Materias y comisiones">
          <p>
            Desde acá podés crear materias y agregar comisiones a cada una. Las comisiones
            se usan para asociar exámenes importados al catálogo de cursado.
          </p>
          <p>
            Hacé clic en una materia para expandirla y ver o agregar comisiones.
            La asociación examen↔comisión sigue siendo opcional (D11).
          </p>
        </HelpButton>
      }
      actions={
        puedeEditarEstructura ? (
          <Button icon="add" onClick={abrirCrearMateria} size="sm">
            Nueva materia
          </Button>
        ) : undefined
      }
    >
      <div className="space-y-lg animate-in fade-in duration-500">
        <RefreshBar
          texto="Materias y comisiones"
          lastUpdatedAt={lastUpdatedAt}
          cargando={cargandoMaterias}
          onActualizar={() => void cargarMaterias()}
        />

        {formMateria && (
          <MateriaFormPanel
            form={formMateria}
            setForm={setFormMateria}
            enviando={enviandoMateria}
            error={errorFormMateria}
            primerInputRef={primerInputMateriaRef}
            onSubmit={handleSubmitMateria}
            onCancelar={cerrarFormMateria}
          />
        )}

        {cargandoMaterias ? (
          <div className="py-16 text-center text-on-surface-variant">
            <Icon name="progress_activity" className="ae-spin text-[28px] text-outline" />
          </div>
        ) : errorMaterias ? (
          // D16: la carga FALLÓ. No se afirma nada sobre el contenido.
          <div className="py-16 text-center text-on-surface-variant space-y-base rounded-xl border border-outline-variant/60 bg-surface-container-lowest">
            <Icon name="cloud_off" className="text-[36px] text-error" />
            <p className="text-[13px]">{errorMaterias}</p>
            <Button variant="ghost" size="sm" onClick={() => void cargarMaterias()}>
              Reintentar
            </Button>
          </div>
        ) : materias.length === 0 ? (
          <div className="py-16 text-center text-on-surface-variant space-y-base rounded-xl border border-outline-variant/60 bg-surface-container-lowest">
            <Icon name="school" className="text-[36px] text-outline" />
            <p className="text-[13px]">No hay materias registradas. Creá la primera usando el botón de arriba.</p>
          </div>
        ) : (
          // Master-detail: materias a la izquierda, comisiones de la seleccionada a la derecha.
          // De 1280 para arriba el reparto pasa a 1 a 3: es donde la derecha muestra la
          // tabla de comisiones, de siete columnas, y con el reparto 1 a 2 no entraba y
          // scrolleaba en horizontal. Abajo de 1280 la derecha son cards angostas, así
          // que ahí conviene el 1 a 2 y que el nombre de la materia se lea entero.
          <div className="grid lg:grid-cols-3 xl:grid-cols-4 gap-lg items-start">
            {/* Columna izquierda: lista de materias (seleccionables). */}
            <div className="lg:col-span-1 rounded-xl border border-outline-variant/60 bg-surface-container-lowest shadow-card overflow-hidden">
              <div className="px-4 py-3 border-b border-outline-variant/40 flex items-center gap-2 flex-wrap">
                <Icon name="school" className="text-[16px] text-on-surface-variant shrink-0" />
                <h2 className="text-[13px] font-semibold text-on-surface">
                  Materias{' '}
                  <span className="text-on-surface-variant font-normal">
                    ({materiasVisibles.length})
                  </span>
                </h2>
                <label className="ml-auto flex items-center gap-1.5 text-[11px] text-on-surface-variant">
                  <span className="sr-only">Filtrar materias por estado</span>
                  <select
                    aria-label="Filtrar materias por estado"
                    value={estadoMaterias}
                    onChange={(e) => setEstadoMaterias(e.target.value as EstadoBajaFiltro)}
                    className="rounded-md border border-outline-variant/60 bg-white px-2 py-1 text-[11px] text-on-surface focus:border-primary focus:outline-none"
                  >
                    {OPCIONES_ESTADO_BAJA.map((o) => (
                      <option key={o.valor} value={o.valor}>{o.label}</option>
                    ))}
                  </select>
                </label>
              </div>
              {/* Que haya materias dadas de baja escondidas tiene que decirse: si
                  no, quien busca una que dio de baja concluye que se borró. */}
              {estadoMaterias === 'activa' && materiasDeBaja > 0 && (
                <button
                  type="button"
                  onClick={() => setEstadoMaterias('inactiva')}
                  className="w-full px-4 py-2 text-left text-[11px] text-on-surface-variant bg-surface-container-low hover:bg-surface-container border-b border-outline-variant/40"
                >
                  <Icon name="delete_outline" className="text-[13px] align-middle mr-1" />
                  Hay {materiasDeBaja}{' '}
                  {materiasDeBaja === 1 ? 'materia dada de baja' : 'materias dadas de baja'}.
                  Verlas
                </button>
              )}
              {/* La lista vacía POR EL FILTRO no es "no hay materias": decirlo así
                  llevaría a crear de nuevo una materia que ya existe. */}
              {materiasVisibles.length === 0 && (
                <div className="px-4 py-10 text-center text-[12px] text-on-surface-variant space-y-2">
                  <Icon name="filter_alt_off" className="text-[28px] text-outline" />
                  <p>
                    {estadoMaterias === 'inactiva'
                      ? 'No hay materias dadas de baja.'
                      : 'Ninguna materia coincide con este filtro.'}
                  </p>
                  <Button variant="ghost" size="sm" onClick={() => setEstadoMaterias('todas')}>
                    Ver todas
                  </Button>
                </div>
              )}
              <div className="divide-y divide-outline-variant/30">
                {materiasVisibles.map((m) => {
                  const sel = expandida === m.id;
                  return (
                    <div
                      key={m.id}
                      className={`flex items-center gap-3 px-4 py-3 transition-colors group ${
                        sel ? 'bg-primary-fixed/50' : 'hover:bg-surface-container-low'
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => void seleccionarMateria(m.id)}
                        className="flex-1 min-w-0 text-left"
                      >
                        <p className={`text-[13px] font-semibold truncate flex items-center gap-2 ${sel ? 'text-primary' : 'text-on-surface'}`}>
                          <span className="truncate">{m.nombre}</span>
                          {m.activa === false && (
                            <span className="shrink-0 inline-flex items-center gap-1 rounded-full bg-outline-variant/40 text-on-surface-variant px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide">
                              <Icon name="pause_circle" className="text-[12px]" />
                              Inactiva
                            </span>
                          )}
                        </p>
                        {/* c-78 §18.4: sin nadie a cargo se ve de un vistazo en la
                            lista, sin abrir materia por materia. Va en la segunda
                            línea junto al código: arriba le comía el ancho al
                            nombre, que es lo que la persona viene a leer. */}
                        <p className="text-[11px] font-mono text-on-surface-variant mt-0.5 flex items-center gap-2">
                          <span className="truncate">{m.codigo}</span>
                          {sinResponsable(m) && (
                            <span
                              title="Esta materia no tiene profesor ni coordinador asignado."
                              className="shrink-0 inline-flex items-center gap-1 rounded-full bg-warning-container text-on-surface px-2 py-0.5 text-[10px] font-sans font-medium uppercase tracking-wide"
                            >
                              <Icon name="person_off" className="text-[12px]" />
                              Sin responsable
                            </span>
                          )}
                        </p>
                      </button>
                      {puedeEditarEstructura && (
                      <ActionMenu
                        ariaLabel={`Acciones de ${m.nombre}`}
                        items={[
                          { label: 'Editar materia', icon: 'edit', onClick: () => abrirEditarMateria(m) },
                          { label: 'Nueva comisión', icon: 'add_circle', onClick: () => abrirCrearComision(m.id) },
                          { label: 'Coordinadores', icon: 'supervisor_account', onClick: () => setCoordinandoMateria(m) },
                          { label: 'Profesores', icon: 'co_present', onClick: () => setAsignandoProfesor(m) },
                          // UN SOLO patrón de baja (c-78). Antes convivían dos entradas
                          // que hacían exactamente lo mismo: "Eliminar materia" ya no
                          // borraba nada desde que la baja pasó a ser lógica, y encima
                          // solo aparecía con la materia vacía, que es justo el caso en
                          // el que no hay nada que sacar.
                          m.activa === false
                            ? { label: 'Reactivar materia', icon: 'play_circle', onClick: () => void toggleActivaMateria(m) }
                            : { label: 'Dar de baja la materia', icon: 'delete', danger: true, onClick: () => void toggleActivaMateria(m) },
                        ]}
                      />
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Columna derecha: comisiones de la materia seleccionada. */}
            <div className="lg:col-span-2 xl:col-span-3 rounded-xl border border-outline-variant/60 bg-surface-container-lowest shadow-card overflow-hidden min-w-0">
              {(() => {
                const m = materias.find((x) => x.id === expandida);
                if (!m) {
                  return (
                    <div className="py-16 text-center text-on-surface-variant text-[13px]">
                      Elegí una materia para ver sus comisiones.
                    </div>
                  );
                }
                const mostrarFormComision = formComision?.materiaId === m.id;
                const comisionesDeLaMateria = comisionesPorMateria[m.id] ?? [];
                const comisionesVisibles = filtrarPorEstado(
                  comisionesDeLaMateria,
                  estadoComisiones,
                );
                const comisionesDeBaja = contarDeBaja(comisionesDeLaMateria);
                return (
                  <>
                    <div className="px-4 py-3 border-b border-outline-variant/40 flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        {/* Pliega en vez de truncar: es el título que dice de qué
                            materia son las comisiones que se están viendo, y cortado
                            a "Comisiones de Progr…" deja de responder esa pregunta. */}
                        <h2 className="text-[13px] font-semibold text-on-surface">
                          Comisiones de {m.nombre}
                        </h2>
                        <p className="text-[11px] text-on-surface-variant">
                          {comisionesVisibles.length} comisión(es)
                          {m.coordinadores && m.coordinadores.length > 0
                            ? ` · Coordina: ${m.coordinadores.map((c) => c.nombre).join(', ')}`
                            : ''}
                          {m.profesores && m.profesores.length > 0
                            ? ` · Profesor: ${m.profesores.map((c) => c.nombre).join(', ')}`
                            : ''}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <select
                          aria-label="Filtrar comisiones por estado"
                          value={estadoComisiones}
                          onChange={(e) => setEstadoComisiones(e.target.value as EstadoBajaFiltro)}
                          className="rounded-md border border-outline-variant/60 bg-white px-2 py-1 text-[11px] text-on-surface focus:border-primary focus:outline-none"
                        >
                          {OPCIONES_ESTADO_BAJA.map((o) => (
                            <option key={o.valor} value={o.valor}>{o.label}</option>
                          ))}
                        </select>
                        {puedeEditarEstructura && (
                          <Button variant="outline" size="sm" icon="add" onClick={() => abrirCrearComision(m.id)}>
                            Nueva comisión
                          </Button>
                        )}
                      </div>
                    </div>
                    {estadoComisiones === 'activa' && comisionesDeBaja > 0 && (
                      <button
                        type="button"
                        onClick={() => setEstadoComisiones('inactiva')}
                        className="w-full px-4 py-2 text-left text-[11px] text-on-surface-variant bg-surface-container-low hover:bg-surface-container border-b border-outline-variant/40"
                      >
                        <Icon name="delete_outline" className="text-[13px] align-middle mr-1" />
                        Hay {comisionesDeBaja}{' '}
                        {comisionesDeBaja === 1
                          ? 'comisión dada de baja'
                          : 'comisiones dadas de baja'}
                        . Verlas
                      </button>
                    )}
                    {/* c-78 §18.4: el aviso completo, con qué falta y por qué
                        importa, va donde se está trabajando la materia. Las
                        comisiones sin tutor ya se marcan una por una en la
                        columna "Tutor" de la tabla de abajo. */}
                    {sinResponsable(m) && (
                      <div className="px-4 pt-3">
                        <AvisoSinResponsable sinResponsableDeMateria nombre={m.nombre} />
                      </div>
                    )}
                    {errorComisiones[m.id] ? (
                      /* D16: la carga de comisiones FALLÓ. No se dibuja como
                         "esta materia no tiene comisiones". */
                      <div className="py-16 text-center text-on-surface-variant space-y-base">
                        <Icon name="cloud_off" className="text-[36px] text-error" />
                        <p className="text-[13px]">{errorComisiones[m.id]}</p>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => void seleccionarMateria(m.id)}
                        >
                          Reintentar
                        </Button>
                      </div>
                    ) : (
                    <ComisionesAccordionBody
                      materiaId={m.id}
                      cargando={cargandoComisiones[m.id]}
                      comisiones={comisionesVisibles}
                      mostrarFormComision={mostrarFormComision}
                      formComision={mostrarFormComision ? formComision : null}
                      setFormComision={setFormComision}
                      enviandoComision={enviandoComision}
                      errorFormComision={errorFormComision}
                      primerInputComisionRef={primerInputComisionRef}
                      periodos={periodos}
                      onSubmitComision={handleSubmitComision}
                      onCancelarComision={cerrarFormComision}
                      abrirCrearComision={abrirCrearComision}
                      abrirEditarComision={abrirEditarComision}
                      onToggleActivaComision={(c) => void toggleActivaComision(m.id, c)}
                      comisionExpandida={comisionExpandida}
                      toggleComision={toggleComision}
                    />
                    )}
                  </>
                );
              })()}
            </div>
          </div>
        )}
      </div>

      {coordinandoMateria && (
        <AsignarCoordinadorDialog
          materiaId={coordinandoMateria.id}
          materiaNombre={coordinandoMateria.nombre}
          coordinadoresActuales={coordinandoMateria.coordinadores ?? []}
          onCerrar={() => setCoordinandoMateria(null)}
          onCambiado={(coordinadores) => {
            // Se refleja en la lista sin recargar todo: el diálogo queda abierto
            // y el usuario puede seguir agregando o quitando.
            setMaterias((prev) =>
              prev.map((m) =>
                m.id === coordinandoMateria.id ? { ...m, coordinadores } : m,
              ),
            );
            setCoordinandoMateria((prev) => (prev ? { ...prev, coordinadores } : prev));
          }}
        />
      )}

      {asignandoProfesor && (
        <AsignarProfesorDialog
          materiaId={asignandoProfesor.id}
          materiaNombre={asignandoProfesor.nombre}
          profesoresActuales={asignandoProfesor.profesores ?? []}
          onCerrar={() => setAsignandoProfesor(null)}
          onCambiado={(profesores) => {
            setMaterias((prev) =>
              prev.map((m) =>
                m.id === asignandoProfesor.id ? { ...m, profesores } : m,
              ),
            );
            setAsignandoProfesor((prev) => (prev ? { ...prev, profesores } : prev));
          }}
        />
      )}

      <ConfirmModal
        abierto={pendienteBaja !== null}
        variante="danger"
        titulo={pendienteBaja?.tipo === 'materia' ? 'Dar de baja la materia' : 'Dar de baja la comisión'}
        mensaje={
          <>
            <p>
              <strong>«{pendienteBaja?.nombre}»</strong> sale de los listados y deja de
              admitir inscripciones nuevas. Sus exámenes dejan de poder rendirse.
            </p>
            <p className="mt-2">
              <strong>No se borra nada</strong> y no se desmatricula a nadie: podés
              reactivarla cuando quieras.
            </p>
            <AvisoImpactoBaja impacto={impactoBaja} cargando={cargandoImpacto} />
          </>
        }
        textoConfirmar={dandoDeBaja ? 'Dando de baja…' : 'Dar de baja'}
        onConfirmar={() => void confirmarBaja()}
        onCancelar={() => { if (!dandoDeBaja) setPendienteBaja(null); }}
      />
    </StaffShell>
  );
}
