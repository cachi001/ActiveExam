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
import { Icon, Card, SectionTitle, Button } from '../ui/components';
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

// ---------------------------------------------------------------------------
// Clases de input — misma estética que ImportExamModal (border-outline-variant,
// radius chico, focus ring primary).
// ---------------------------------------------------------------------------

const INPUT_CLASS =
  'w-full rounded-md border border-outline-variant bg-surface px-3 py-2.5 text-sm ' +
  'text-on-surface outline-none transition-colors hover:border-outline focus:border-primary ' +
  'focus:ring-1 focus:ring-primary/30 disabled:opacity-50 disabled:cursor-not-allowed';

const LABEL_CLASS = 'block text-xs font-semibold text-on-surface-variant uppercase tracking-wide mb-1';

// ---------------------------------------------------------------------------
// Estado del formulario de materia
// ---------------------------------------------------------------------------

interface FormMateria {
  modo: 'crear' | 'editar';
  id: string | null;         // id de la materia en edición
  codigo: string;
  nombre: string;
}

const FORM_MATERIA_VACIO: FormMateria = { modo: 'crear', id: null, codigo: '', nombre: '' };

// ---------------------------------------------------------------------------
// Estado del formulario de comisión
// ---------------------------------------------------------------------------

interface FormComision {
  modo: 'crear' | 'editar';
  materiaId: string;
  comisionId: string | null;  // id de la comisión en edición
  codigo: string;
  nombre: string;
  periodo: string;
  anio: string;               // string para el input; convertido a number al enviar
}

const FORM_COMISION_VACIO: Omit<FormComision, 'materiaId'> = {
  modo: 'crear',
  comisionId: null,
  codigo: '',
  nombre: '',
  periodo: '',
  anio: '',
};

// ---------------------------------------------------------------------------
// Helpers de error
// ---------------------------------------------------------------------------

function mensajeDeError(
  err: unknown,
  contexto: 'materia' | 'comision',
): string {
  const e = err as Error & { status?: number };
  if (e.status === 409) {
    return contexto === 'materia'
      ? 'Ya existe una materia con ese código.'
      : 'Ya existe una comisión con ese código en esta materia.';
  }
  if (e.status === 422) {
    return 'Datos inválidos. Revisá los campos e intentá de nuevo.';
  }
  if (e.status === 404) {
    return contexto === 'materia'
      ? 'No se encontró la materia.'
      : 'No se encontró la comisión o la materia.';
  }
  if (e.message?.includes('Failed to fetch') || e.message?.includes('fetch')) {
    return 'No se pudo conectar con el servidor. ¿Está activo el backend?';
  }
  return e.message ?? 'Error inesperado.';
}

// ---------------------------------------------------------------------------
// Componente principal
// ---------------------------------------------------------------------------

export default function MateriasComisiones() {
  const toast = useToast();

  // ── Materias ──────────────────────────────────────────────────────────────
  const [materias, setMaterias] = useState<Materia[]>([]);
  const [cargandoMaterias, setCargandoMaterias] = useState(true);

  // ── Acordeón ──────────────────────────────────────────────────────────────
  const [expandida, setExpandida] = useState<string | null>(null);
  const [comisionesPorMateria, setComisionesPorMateria] = useState<Record<string, Comision[]>>({});
  const [cargandoComisiones, setCargandoComisiones] = useState<Record<string, boolean>>({});

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
      // Limpiar formulario de comision si corresponde a esta materia
      if (formComision?.materiaId === materiaId) cerrarFormComision();
      return;
    }

    setExpandida(materiaId);

    // Carga lazy de comisiones
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
    // Asegurar que la materia esté expandida
    if (expandida !== materiaId) {
      void toggleExpand(materiaId);
    }
    setFormComision({ ...FORM_COMISION_VACIO, modo: 'crear', materiaId });
    setErrorFormComision(null);
    setTimeout(() => primerInputComisionRef.current?.focus(), 80);
  }

  function abrirEditarComision(materiaId: string, c: Comision) {
    if (expandida !== materiaId) {
      void toggleExpand(materiaId);
    }
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
        // Agregar al map de comisiones del acordeón
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

        {/* ── Formulario de materia (crear / editar) ──────────────────────── */}
        {formMateria && (
          <Card>
            <SectionTitle>
              {formMateria.modo === 'crear' ? 'Nueva materia' : 'Editar materia'}
            </SectionTitle>
            <form onSubmit={handleSubmitMateria} className="space-y-md mt-md">
              <div className="grid sm:grid-cols-2 gap-md">
                {formMateria.modo === 'crear' && (
                  <div>
                    <label htmlFor="materia-codigo" className={LABEL_CLASS}>
                      Código <span aria-hidden="true">*</span>
                    </label>
                    <input
                      ref={primerInputMateriaRef}
                      id="materia-codigo"
                      name="materia-codigo"
                      type="text"
                      required
                      disabled={enviandoMateria}
                      placeholder="Ej. CB101"
                      value={formMateria.codigo}
                      onChange={(e) =>
                        setFormMateria((prev) => prev ? { ...prev, codigo: e.target.value } : prev)
                      }
                      className={INPUT_CLASS}
                    />
                  </div>
                )}
                <div className={formMateria.modo === 'editar' ? 'sm:col-span-2' : ''}>
                  <label htmlFor="materia-nombre" className={LABEL_CLASS}>
                    Nombre <span aria-hidden="true">*</span>
                  </label>
                  <input
                    ref={formMateria.modo === 'editar' ? primerInputMateriaRef : undefined}
                    id="materia-nombre"
                    name="materia-nombre"
                    type="text"
                    required
                    disabled={enviandoMateria}
                    placeholder="Ej. Análisis Matemático I"
                    value={formMateria.nombre}
                    onChange={(e) =>
                      setFormMateria((prev) => prev ? { ...prev, nombre: e.target.value } : prev)
                    }
                    className={INPUT_CLASS}
                  />
                </div>
              </div>

              {errorFormMateria && (
                <div
                  role="alert"
                  className="flex items-center gap-xs text-error text-body-sm p-sm rounded-lg bg-error-container"
                >
                  <Icon name="error" className="text-[18px] shrink-0" fill />
                  {errorFormMateria}
                </div>
              )}

              <div className="flex gap-sm justify-end">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={cerrarFormMateria}
                  disabled={enviandoMateria}
                >
                  Cancelar
                </Button>
                <Button type="submit" disabled={enviandoMateria}>
                  {enviandoMateria ? (
                    <span className="inline-flex items-center gap-xs">
                      <Icon name="progress_activity" className="ae-spin text-[20px]" />
                      Guardando…
                    </span>
                  ) : formMateria.modo === 'crear' ? 'Crear materia' : 'Guardar cambios'}
                </Button>
              </div>
            </form>
          </Card>
        )}

        {/* ── Lista de materias con acordeón ──────────────────────────────── */}
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/60 shadow-card overflow-hidden">
          {/* Cabecera */}
          <div className="px-4 py-3 border-b border-outline-variant/40 flex items-center gap-2">
            <Icon name="school" className="text-[16px] text-primary shrink-0" />
            <h2 className="text-[13px] font-semibold text-on-surface">
              Materias
              {!cargandoMaterias && (
                <span className="text-on-surface-variant font-normal ml-1">({materias.length})</span>
              )}
            </h2>
          </div>

          {/* Carga */}
          {cargandoMaterias ? (
            <div className="py-12 text-center text-on-surface-variant">
              <Icon name="progress_activity" className="ae-spin text-[28px] text-outline" />
            </div>
          ) : materias.length === 0 ? (
            /* Vacío */
            <div className="py-12 text-center text-on-surface-variant space-y-base">
              <Icon name="school" className="text-[36px] text-outline" />
              <p className="text-[13px]">No hay materias registradas. Creá la primera usando el botón de arriba.</p>
            </div>
          ) : (
            /* Lista */
            <div className="divide-y divide-outline-variant/30">
              {materias.map((m) => {
                const estaExpandida = expandida === m.id;
                const comisiones = comisionesPorMateria[m.id];
                const cargando = cargandoComisiones[m.id];
                const mostrarFormComision = formComision?.materiaId === m.id;

                return (
                  <div key={m.id}>
                    {/* ── Fila de materia ──────────────────────────────── */}
                    <div className="flex items-center gap-3 px-4 py-3.5 hover:bg-surface-container-low transition-colors group">
                      {/* Botón de expansión */}
                      <button
                        type="button"
                        aria-label={estaExpandida ? `Colapsar ${m.nombre}` : `Expandir ${m.nombre}`}
                        aria-expanded={estaExpandida}
                        onClick={() => void toggleExpand(m.id)}
                        className="w-7 h-7 rounded-md flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors shrink-0"
                      >
                        <Icon
                          name={estaExpandida ? 'keyboard_arrow_down' : 'keyboard_arrow_right'}
                          className="text-[20px]"
                        />
                      </button>

                      {/* Icono de materia */}
                      <div className="w-8 h-8 rounded-lg bg-primary-fixed text-on-primary-fixed-variant flex items-center justify-center shrink-0">
                        <Icon name="school" className="text-[16px]" />
                      </div>

                      {/* Datos */}
                      <div className="flex-1 min-w-0">
                        <button
                          type="button"
                          onClick={() => void toggleExpand(m.id)}
                          className="text-[13px] font-semibold text-on-surface group-hover:text-primary transition-colors truncate text-left w-full"
                        >
                          {m.nombre}
                        </button>
                        <p className="text-[11px] font-mono text-on-surface-variant mt-0.5">
                          {m.codigo}
                        </p>
                      </div>

                      {/* Acciones */}
                      <ActionMenu
                        ariaLabel={`Acciones de ${m.nombre}`}
                        items={[
                          {
                            label: 'Editar materia',
                            icon: 'edit',
                            onClick: () => abrirEditarMateria(m),
                          },
                          {
                            label: 'Nueva comisión',
                            icon: 'add_circle',
                            onClick: () => abrirCrearComision(m.id),
                          },
                        ]}
                      />
                    </div>

                    {/* ── Sección expandida: comisiones ─────────────────── */}
                    {estaExpandida && (
                      <div className="bg-surface-container-low border-t border-outline-variant/20">

                        {/* Formulario de comisión */}
                        {mostrarFormComision && formComision && (
                          <div className="px-4 pt-4 pb-3">
                            <p className="text-[12px] font-semibold text-on-surface-variant uppercase tracking-wide mb-3">
                              {formComision.modo === 'crear' ? 'Nueva comisión' : 'Editar comisión'}
                            </p>
                            <form onSubmit={handleSubmitComision} className="space-y-3">
                              <div className="grid sm:grid-cols-2 md:grid-cols-4 gap-3">
                                {formComision.modo === 'crear' && (
                                  <div>
                                    <label htmlFor="comision-codigo" className={LABEL_CLASS}>
                                      Código <span aria-hidden="true">*</span>
                                    </label>
                                    <input
                                      ref={primerInputComisionRef}
                                      id="comision-codigo"
                                      name="comision-codigo"
                                      type="text"
                                      required
                                      disabled={enviandoComision}
                                      placeholder="Ej. 1A"
                                      value={formComision.codigo}
                                      onChange={(e) =>
                                        setFormComision((prev) =>
                                          prev ? { ...prev, codigo: e.target.value } : prev,
                                        )
                                      }
                                      className={INPUT_CLASS}
                                    />
                                  </div>
                                )}
                                <div className={formComision.modo === 'editar' ? 'sm:col-span-2' : ''}>
                                  <label htmlFor="comision-nombre" className={LABEL_CLASS}>
                                    Nombre <span aria-hidden="true">*</span>
                                  </label>
                                  <input
                                    ref={formComision.modo === 'editar' ? primerInputComisionRef : undefined}
                                    id="comision-nombre"
                                    name="comision-nombre"
                                    type="text"
                                    required
                                    disabled={enviandoComision}
                                    placeholder="Ej. Comisión 1A"
                                    value={formComision.nombre}
                                    onChange={(e) =>
                                      setFormComision((prev) =>
                                        prev ? { ...prev, nombre: e.target.value } : prev,
                                      )
                                    }
                                    className={INPUT_CLASS}
                                  />
                                </div>
                                <div>
                                  <label htmlFor="comision-periodo" className={LABEL_CLASS}>
                                    Período
                                  </label>
                                  <input
                                    id="comision-periodo"
                                    name="comision-periodo"
                                    type="text"
                                    disabled={enviandoComision}
                                    placeholder="Ej. 2026-1"
                                    value={formComision.periodo}
                                    onChange={(e) =>
                                      setFormComision((prev) =>
                                        prev ? { ...prev, periodo: e.target.value } : prev,
                                      )
                                    }
                                    className={INPUT_CLASS}
                                  />
                                </div>
                                <div>
                                  <label htmlFor="comision-anio" className={LABEL_CLASS}>
                                    Año
                                  </label>
                                  <input
                                    id="comision-anio"
                                    name="comision-anio"
                                    type="number"
                                    min={2000}
                                    max={2100}
                                    disabled={enviandoComision}
                                    placeholder="Ej. 2026"
                                    value={formComision.anio}
                                    onChange={(e) =>
                                      setFormComision((prev) =>
                                        prev ? { ...prev, anio: e.target.value } : prev,
                                      )
                                    }
                                    className={INPUT_CLASS}
                                  />
                                </div>
                              </div>

                              {errorFormComision && (
                                <div
                                  role="alert"
                                  className="flex items-center gap-xs text-error text-body-sm p-sm rounded-lg bg-error-container"
                                >
                                  <Icon name="error" className="text-[18px] shrink-0" fill />
                                  {errorFormComision}
                                </div>
                              )}

                              <div className="flex gap-sm justify-end">
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  onClick={cerrarFormComision}
                                  disabled={enviandoComision}
                                >
                                  Cancelar
                                </Button>
                                <Button type="submit" size="sm" disabled={enviandoComision}>
                                  {enviandoComision ? (
                                    <span className="inline-flex items-center gap-xs">
                                      <Icon name="progress_activity" className="ae-spin text-[18px]" />
                                      Guardando…
                                    </span>
                                  ) : formComision.modo === 'crear' ? 'Crear comisión' : 'Guardar'}
                                </Button>
                              </div>
                            </form>
                          </div>
                        )}

                        {/* Tabla de comisiones */}
                        {cargando ? (
                          <div className="py-6 text-center">
                            <Icon name="progress_activity" className="ae-spin text-[22px] text-outline" />
                          </div>
                        ) : comisiones && comisiones.length === 0 && !mostrarFormComision ? (
                          <div className="py-6 px-8 text-on-surface-variant text-[13px] flex items-center gap-2">
                            <Icon name="info" className="text-[16px] shrink-0" />
                            No hay comisiones todavía.
                            <button
                              type="button"
                              onClick={() => abrirCrearComision(m.id)}
                              className="text-primary hover:underline font-medium ml-1"
                            >
                              Agregar la primera
                            </button>
                          </div>
                        ) : comisiones && comisiones.length > 0 ? (
                          <>
                            {/* Tabla desktop */}
                            <div className="hidden sm:block overflow-x-auto">
                              <table className="w-full">
                                <thead>
                                  <tr className="bg-surface-container">
                                    <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-8 py-2">
                                      Código
                                    </th>
                                    <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2">
                                      Nombre
                                    </th>
                                    <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2">
                                      Período
                                    </th>
                                    <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2">
                                      Año
                                    </th>
                                    <th className="text-right text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2">
                                      Acciones
                                    </th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-outline-variant/20">
                                  {comisiones.map((c) => (
                                    <tr key={c.id} className="hover:bg-surface-container/50 transition-colors">
                                      <td className="px-8 py-3 whitespace-nowrap">
                                        <span className="font-mono text-[12px] text-on-surface-variant bg-surface-container px-2 py-0.5 rounded-md">
                                          {c.codigo ?? '—'}
                                        </span>
                                      </td>
                                      <td className="px-4 py-3 text-[13px] text-on-surface">
                                        {c.nombre}
                                      </td>
                                      <td className="px-4 py-3 text-[13px] text-on-surface-variant">
                                        {c.periodo ?? '—'}
                                      </td>
                                      <td className="px-4 py-3 text-[13px] text-on-surface-variant tabular-nums">
                                        {c.anio ?? '—'}
                                      </td>
                                      <td className="px-4 py-3 text-right">
                                        <ActionMenu
                                          ariaLabel={`Acciones de ${c.nombre}`}
                                          items={[
                                            {
                                              label: 'Editar comisión',
                                              icon: 'edit',
                                              onClick: () => abrirEditarComision(m.id, c),
                                            },
                                          ]}
                                        />
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>

                            {/* Cards mobile */}
                            <div className="sm:hidden divide-y divide-outline-variant/20">
                              {comisiones.map((c) => (
                                <div key={c.id} className="px-8 py-3 flex items-center justify-between gap-3">
                                  <div className="min-w-0">
                                    <p className="text-[13px] font-medium text-on-surface truncate">{c.nombre}</p>
                                    <p className="text-[11px] text-on-surface-variant font-mono mt-0.5">
                                      {c.codigo ?? '—'}
                                      {c.periodo ? ` · ${c.periodo}` : ''}
                                      {c.anio ? ` · ${c.anio}` : ''}
                                    </p>
                                  </div>
                                  <ActionMenu
                                    ariaLabel={`Acciones de ${c.nombre}`}
                                    items={[
                                      {
                                        label: 'Editar comisión',
                                        icon: 'edit',
                                        onClick: () => abrirEditarComision(m.id, c),
                                      },
                                    ]}
                                  />
                                </div>
                              ))}
                            </div>
                          </>
                        ) : null}

                        {/* Botón "Nueva comisión" al pie de la sección */}
                        {comisiones && comisiones.length > 0 && !mostrarFormComision && (
                          <div className="px-8 py-3 border-t border-outline-variant/20">
                            <Button
                              variant="ghost"
                              size="sm"
                              icon="add"
                              onClick={() => abrirCrearComision(m.id)}
                            >
                              Nueva comisión
                            </Button>
                          </div>
                        )}
                      </div>
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
