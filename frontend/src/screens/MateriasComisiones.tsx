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
import { STAFF_NAV } from '../ui/nav';
import { useToast } from '../ui/toast';
import { api } from '../lib/api';
import {
  crearMateria,
  actualizarMateria,
  crearComision,
  actualizarComision,
  eliminarMateria,
  eliminarComision,
  setMateriaActiva,
  setComisionActiva,
} from '../lib/examContentAdmin';
import type { Materia, Comision } from '../lib/types';
import { ConfirmModal } from '../ui/ConfirmModal';
import { MateriaFormPanel } from './admin/components/MateriaFormPanel';
import { ComisionesAccordionBody } from './admin/components/ComisionesAccordionBody';
import {
  FORM_MATERIA_VACIO,
  FORM_COMISION_VACIO,
  mensajeDeError,
  type FormMateria,
  type FormComision,
} from './admin/components/materiasComisionesTypes';

export default function MateriasComisiones() {
  const toast = useToast();

  // ── Materias ──────────────────────────────────────────────────────────────
  const [materias, setMaterias] = useState<Materia[]>([]);
  const [cargandoMaterias, setCargandoMaterias] = useState(true);

  // ── Acordeón ──────────────────────────────────────────────────────────────
  const [expandida, setExpandida] = useState<string | null>(null);
  const [comisionesPorMateria, setComisionesPorMateria] = useState<Record<string, Comision[]>>({});
  const [cargandoComisiones, setCargandoComisiones] = useState<Record<string, boolean>>({});

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

  // ── Borrado (solo si 100% vacío; el backend es la autoridad) ───────────────
  const [confirmarBorrado, setConfirmarBorrado] = useState<
    { tipo: 'materia' | 'comision'; id: string; nombre: string; materiaId?: string } | null
  >(null);
  const [borrando, setBorrando] = useState(false);

  // Activar / desactivar (freeze) una materia. La materia inactiva no se oculta
  // al alumno inscripto; solo corta inscripciones nuevas y bloquea rendir (server-side).
  async function toggleActivaMateria(m: Materia) {
    const nuevoEstado = !(m.activa ?? true);
    try {
      const actualizada = await setMateriaActiva(m.id, nuevoEstado);
      setMaterias((prev) =>
        prev.map((x) => (x.id === m.id ? { ...x, activa: actualizada.activa ?? nuevoEstado } : x)),
      );
      toast.success(nuevoEstado ? 'Materia activada.' : 'Materia desactivada (congelada).');
    } catch {
      toast.error('No se pudo cambiar el estado de la materia.');
    }
  }

  // Activar / desactivar (baja lógica) una comisión. Congela SOLO esa comisión:
  // corta inscripciones nuevas por su código y bloquea iniciar sus exámenes. No
  // desmatricula a nadie. Es la salida cuando el borrado está bloqueado.
  async function toggleActivaComision(materiaId: string, c: Comision) {
    const nuevoEstado = !(c.activa ?? true);
    try {
      const actualizada = await setComisionActiva(c.id, nuevoEstado);
      setComisionesPorMateria((prev) => ({
        ...prev,
        [materiaId]: (prev[materiaId] ?? []).map((x) =>
          x.id === c.id ? { ...x, activa: actualizada.activa ?? nuevoEstado } : x,
        ),
      }));
      toast.success(nuevoEstado ? 'Comisión activada.' : 'Comisión desactivada (congelada).');
    } catch {
      toast.error('No se pudo cambiar el estado de la comisión.');
    }
  }

  async function confirmarEliminar() {
    if (!confirmarBorrado) return;
    const target = confirmarBorrado;
    setBorrando(true);
    try {
      if (target.tipo === 'materia') {
        await eliminarMateria(target.id);
        setMaterias((prev) => prev.filter((m) => m.id !== target.id));
        setComisionesPorMateria((prev) => {
          const next = { ...prev };
          delete next[target.id];
          return next;
        });
        if (expandida === target.id) setExpandida(null);
        toast.success('Materia eliminada.');
      } else if (target.materiaId) {
        await eliminarComision(target.id);
        const mid = target.materiaId;
        setComisionesPorMateria((prev) => ({
          ...prev,
          [mid]: (prev[mid] ?? []).filter((c) => c.id !== target.id),
        }));
        toast.success('Comisión eliminada.');
      }
      setConfirmarBorrado(null);
    } catch (err) {
      const status = (err as { status?: number })?.status;
      // 409: tiene inscriptos/exámenes → el mensaje del backend sugiere desactivar.
      toast.error(
        status === 409
          ? (err as Error).message ||
              'No se puede eliminar: tiene inscriptos o exámenes. Desactivala en su lugar.'
          : 'No se pudo eliminar. Reintentá en un momento.',
      );
      setConfirmarBorrado(null);
    } finally {
      setBorrando(false);
    }
  }

  useEffect(() => {
    api.listarPeriodos().then(setPeriodos).catch(() => {/* usa fallback */});
  }, []);

  // ── Carga inicial de materias ─────────────────────────────────────────────

  const cargarMaterias = useCallback(async () => {
    setCargandoMaterias(true);
    try {
      const data = await api.materiasDisponibles();
      setMaterias(data);
    } catch {
      toast.error('No se pudo cargar la lista de materias.');
    } finally {
      setCargandoMaterias(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { void cargarMaterias(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
        const data = await api.comisionesDeMateria(materiaId);
        setComisionesPorMateria((prev) => ({ ...prev, [materiaId]: data }));
      } catch {
        toast.error('No se pudieron cargar las comisiones.');
        setComisionesPorMateria((prev) => ({ ...prev, [materiaId]: [] }));
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
        <Button icon="add" onClick={abrirCrearMateria} size="sm">
          Nueva materia
        </Button>
      }
    >
      <div className="space-y-lg animate-in fade-in duration-500">

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
        ) : materias.length === 0 ? (
          <div className="py-16 text-center text-on-surface-variant space-y-base rounded-xl border border-outline-variant/60 bg-surface-container-lowest">
            <Icon name="school" className="text-[36px] text-outline" />
            <p className="text-[13px]">No hay materias registradas. Creá la primera usando el botón de arriba.</p>
          </div>
        ) : (
          // Master-detail: materias a la izquierda, comisiones de la seleccionada a la derecha.
          <div className="grid lg:grid-cols-3 gap-lg items-start">
            {/* Columna izquierda: lista de materias (seleccionables). */}
            <div className="lg:col-span-1 rounded-xl border border-outline-variant/60 bg-surface-container-lowest shadow-card overflow-hidden">
              <div className="px-4 py-3 border-b border-outline-variant/40 flex items-center gap-2">
                <Icon name="school" className="text-[16px] text-on-surface-variant shrink-0" />
                <h2 className="text-[13px] font-semibold text-on-surface">
                  Materias <span className="text-on-surface-variant font-normal">({materias.length})</span>
                </h2>
              </div>
              <div className="divide-y divide-outline-variant/30">
                {materias.map((m) => {
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
                        <p className="text-[11px] font-mono text-on-surface-variant mt-0.5">{m.codigo}</p>
                      </button>
                      <ActionMenu
                        ariaLabel={`Acciones de ${m.nombre}`}
                        items={[
                          { label: 'Editar materia', icon: 'edit', onClick: () => abrirEditarMateria(m) },
                          { label: 'Nueva comisión', icon: 'add_circle', onClick: () => abrirCrearComision(m.id) },
                          m.activa === false
                            ? { label: 'Activar materia', icon: 'play_circle', onClick: () => void toggleActivaMateria(m) }
                            : { label: 'Desactivar materia', icon: 'pause_circle', onClick: () => void toggleActivaMateria(m) },
                          {
                            label: 'Eliminar materia',
                            icon: 'delete',
                            danger: true,
                            onClick: () =>
                              setConfirmarBorrado({ tipo: 'materia', id: m.id, nombre: m.nombre }),
                          },
                        ]}
                      />
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Columna derecha: comisiones de la materia seleccionada. */}
            <div className="lg:col-span-2 rounded-xl border border-outline-variant/60 bg-surface-container-lowest shadow-card overflow-hidden min-w-0">
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
                return (
                  <>
                    <div className="px-4 py-3 border-b border-outline-variant/40 flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <h2 className="text-[13px] font-semibold text-on-surface truncate">
                          Comisiones de {m.nombre}
                        </h2>
                        <p className="text-[11px] text-on-surface-variant">
                          {(comisionesPorMateria[m.id]?.length ?? 0)} comisión(es)
                        </p>
                      </div>
                      <Button variant="outline" size="sm" icon="add" onClick={() => abrirCrearComision(m.id)}>
                        Nueva comisión
                      </Button>
                    </div>
                    <ComisionesAccordionBody
                      materiaId={m.id}
                      cargando={cargandoComisiones[m.id]}
                      comisiones={comisionesPorMateria[m.id]}
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
                      abrirEliminarComision={(c) =>
                        setConfirmarBorrado({
                          tipo: 'comision',
                          id: c.id,
                          nombre: c.nombre,
                          materiaId: m.id,
                        })
                      }
                      onToggleActivaComision={(c) => void toggleActivaComision(m.id, c)}
                      comisionExpandida={comisionExpandida}
                      toggleComision={toggleComision}
                    />
                  </>
                );
              })()}
            </div>
          </div>
        )}
      </div>

      <ConfirmModal
        abierto={confirmarBorrado !== null}
        variante="danger"
        titulo={confirmarBorrado?.tipo === 'materia' ? 'Eliminar materia' : 'Eliminar comisión'}
        mensaje={
          <>
            ¿Seguro que querés eliminar {confirmarBorrado?.tipo === 'materia' ? 'la materia' : 'la comisión'}{' '}
            <strong>«{confirmarBorrado?.nombre}»</strong>? Esta acción no se puede deshacer. Solo se
            permite si no tiene inscriptos ni exámenes.
          </>
        }
        textoConfirmar={borrando ? 'Eliminando…' : 'Eliminar'}
        onConfirmar={() => void confirmarEliminar()}
        onCancelar={() => { if (!borrando) setConfirmarBorrado(null); }}
      />
    </StaffShell>
  );
}
