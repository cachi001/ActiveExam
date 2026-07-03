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
} from '../lib/examContentAdmin';
import type { Materia, Comision } from '../lib/types';
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

  async function toggleExpand(materiaId: string) {
    if (expandida === materiaId) {
      setExpandida(null);
      if (formComision?.materiaId === materiaId) cerrarFormComision();
      return;
    }
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
        const actualizada = await actualizarMateria(formMateria.id, { nombre: formMateria.nombre });
        setMaterias((prev) =>
          prev.map((m) => (m.id === formMateria.id ? { ...m, nombre: actualizada.nombre } : m)),
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
        });
        setComisionesPorMateria((prev) => {
          const list = prev[formComision.materiaId] ?? [];
          return {
            ...prev,
            [formComision.materiaId]: list.map((c) =>
              c.id === formComision.comisionId
                ? { ...c, nombre: actualizada.nombre, periodo: actualizada.periodo, anio: actualizada.anio }
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

        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/60 shadow-card overflow-hidden">
          <div className="px-4 py-3 border-b border-outline-variant/40 flex items-center gap-2">
            <Icon name="school" className="text-[16px] text-primary shrink-0" />
            <h2 className="text-[13px] font-semibold text-on-surface">
              Materias
              {!cargandoMaterias && (
                <span className="text-on-surface-variant font-normal ml-1">({materias.length})</span>
              )}
            </h2>
          </div>

          {cargandoMaterias ? (
            <div className="py-12 text-center text-on-surface-variant">
              <Icon name="progress_activity" className="ae-spin text-[28px] text-outline" />
            </div>
          ) : materias.length === 0 ? (
            <div className="py-12 text-center text-on-surface-variant space-y-base">
              <Icon name="school" className="text-[36px] text-outline" />
              <p className="text-[13px]">No hay materias registradas. Creá la primera usando el botón de arriba.</p>
            </div>
          ) : (
            <div className="divide-y divide-outline-variant/30">
              {materias.map((m) => {
                const estaExpandida = expandida === m.id;
                const comisiones = comisionesPorMateria[m.id];
                const cargando = cargandoComisiones[m.id];
                const mostrarFormComision = formComision?.materiaId === m.id;

                return (
                  <div key={m.id}>
                    <div className="flex items-center gap-3 px-4 py-3.5 hover:bg-surface-container-low transition-colors group">
                      <button
                        type="button"
                        aria-label={estaExpandida ? `Colapsar ${m.nombre}` : `Expandir ${m.nombre}`}
                        aria-expanded={estaExpandida}
                        onClick={() => void toggleExpand(m.id)}
                        className="w-7 h-7 rounded-md flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors shrink-0"
                      >
                        <Icon name={estaExpandida ? 'keyboard_arrow_down' : 'keyboard_arrow_right'} className="text-[20px]" />
                      </button>
                      <div className="w-8 h-8 rounded-lg bg-primary-fixed text-on-primary-fixed-variant flex items-center justify-center shrink-0">
                        <Icon name="school" className="text-[16px]" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <button
                          type="button"
                          onClick={() => void toggleExpand(m.id)}
                          className="text-[13px] font-semibold text-on-surface group-hover:text-primary transition-colors truncate text-left w-full"
                        >
                          {m.nombre}
                        </button>
                        <p className="text-[11px] font-mono text-on-surface-variant mt-0.5">{m.codigo}</p>
                      </div>
                      <ActionMenu
                        ariaLabel={`Acciones de ${m.nombre}`}
                        items={[
                          { label: 'Editar materia', icon: 'edit', onClick: () => abrirEditarMateria(m) },
                          { label: 'Nueva comisión', icon: 'add_circle', onClick: () => abrirCrearComision(m.id) },
                        ]}
                      />
                    </div>

                    {estaExpandida && (
                      <ComisionesAccordionBody
                        materiaId={m.id}
                        cargando={cargando}
                        comisiones={comisiones}
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
                        comisionExpandida={comisionExpandida}
                        toggleComision={toggleComision}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </StaffShell>
  );
}
