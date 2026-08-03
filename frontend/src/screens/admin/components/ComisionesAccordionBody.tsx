import type React from 'react';
import { Fragment, useState } from 'react';
import { Icon, Button } from '../../../ui/components';
import { ActionMenu, type ActionItem } from '../../../ui/ActionMenu';
import type { Comision } from '../../../lib/types';
import { AlumnosComisionPanel } from './AlumnosComisionPanel';
import { AsignarDocenteDialog } from './AsignarDocenteDialog';
import { useAuth } from '../../../lib/authStore';
import { INPUT_CLASS, LABEL_CLASS, type FormComision } from './materiasComisionesTypes';

interface ComisionesAccordionBodyProps {
  materiaId: string;
  cargando: boolean;
  comisiones: Comision[] | undefined;
  mostrarFormComision: boolean;
  formComision: FormComision | null;
  setFormComision: React.Dispatch<React.SetStateAction<FormComision | null>>;
  enviandoComision: boolean;
  errorFormComision: string | null;
  primerInputComisionRef: React.RefObject<HTMLInputElement>;
  periodos: { value: string; label: string }[];
  onSubmitComision: (e: React.FormEvent) => void;
  onCancelarComision: () => void;
  abrirCrearComision: (materiaId: string) => void;
  abrirEditarComision: (materiaId: string, c: Comision) => void;
  abrirEliminarComision: (c: Comision) => void;
  /** Baja lógica: activa/desactiva la comisión (C-72 §17). */
  onToggleActivaComision: (c: Comision) => void;
  comisionExpandida: string | null;
  toggleComision: (id: string) => void;
}

export function ComisionesAccordionBody({
  materiaId,
  cargando,
  comisiones,
  mostrarFormComision,
  formComision,
  setFormComision,
  enviandoComision,
  errorFormComision,
  primerInputComisionRef,
  periodos,
  onSubmitComision,
  onCancelarComision,
  abrirCrearComision,
  abrirEditarComision,
  abrirEliminarComision,
  comisionExpandida,
  toggleComision,
}: ComisionesAccordionBodyProps) {
  // C-73 §9.5: docente a cargo de la comisión.
  const esAdmin = useAuth((st) => st.hasRole)(['admin_sistema']);
  const [asignando, setAsignando] = useState<Comision | null>(null);
  const [docenteLocal, setDocenteLocal] = useState<Record<string, string | null>>({});
  // Acciones del menú kebab por comisión. "Eliminar" solo aparece si la comisión
  // está VACÍA (0 inscriptos y 0 exámenes), mismo criterio que el guard del backend:
  // ofrecer un borrado que el servidor va a rechazar con 409 es un dead-end para el usuario.
  const accionesComision = (c: Comision, comExpandida: boolean): ActionItem[] => {
    const vacia = (c.total_inscriptos ?? 0) === 0 && (c.total_examenes ?? 0) === 0;
    return [
      { label: comExpandida ? 'Ocultar alumnos' : 'Ver alumnos', icon: 'groups', onClick: () => toggleComision(c.id) },
      { label: 'Editar comisión', icon: 'edit', onClick: () => abrirEditarComision(materiaId, c) },
      // Solo admin_sistema: la lista de usuarios (de donde sale el selector) es
      // admin-only, así que ofrecérselo a otro rol daría un diálogo vacío.
      ...(esAdmin
        ? [{
            label: c.docente_id ? 'Cambiar docente a cargo' : 'Asignar docente a cargo',
            icon: 'person',
            onClick: () => setAsignando(c),
          } as ActionItem]
        : []),
      ...(vacia
        ? [{ label: 'Eliminar comisión', icon: 'delete', danger: true, onClick: () => abrirEliminarComision(c) } as ActionItem]
        : []),
    ];
  };
  return (
    <div className="bg-surface-container-low border-t border-outline-variant/20">
      {/* Formulario de comisión */}
      {mostrarFormComision && formComision && (
        <div className="px-4 pt-4 pb-3">
          <p className="text-[12px] font-semibold text-on-surface-variant uppercase tracking-wide mb-3">
            {formComision.modo === 'crear' ? 'Nueva comisión' : 'Editar comisión'}
          </p>
          <form onSubmit={onSubmitComision} className="space-y-3">
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
                      setFormComision((prev) => prev ? { ...prev, codigo: e.target.value } : prev)
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
                    setFormComision((prev) => prev ? { ...prev, nombre: e.target.value } : prev)
                  }
                  className={INPUT_CLASS}
                />
              </div>
              <div>
                <label htmlFor="comision-periodo" className={LABEL_CLASS}>
                  Período
                </label>
                <select
                  id="comision-periodo"
                  name="comision-periodo"
                  disabled={enviandoComision}
                  value={formComision.periodo}
                  onChange={(e) =>
                    setFormComision((prev) => prev ? { ...prev, periodo: e.target.value } : prev)
                  }
                  className={INPUT_CLASS}
                >
                  <option value="">Seleccionar...</option>
                  {periodos.map((p) => (
                    <option key={p.value} value={p.value}>{p.label}</option>
                  ))}
                </select>
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
                    setFormComision((prev) => prev ? { ...prev, anio: e.target.value } : prev)
                  }
                  className={INPUT_CLASS}
                />
              </div>
            </div>

            {/* C-70: código de matriculación (enrolment key) — editable + copiar. */}
            <div>
              <label htmlFor="comision-codmatricula" className={LABEL_CLASS}>
                Código de matriculación
              </label>
              <div className="flex gap-2">
                <input
                  id="comision-codmatricula"
                  name="comision-codmatricula"
                  type="text"
                  disabled={enviandoComision}
                  placeholder={
                    formComision.modo === 'crear'
                      ? 'Se autogenera si lo dejás vacío (ej. PROG1-7K2Q)'
                      : ''
                  }
                  value={formComision.codigoMatriculacion}
                  onChange={(e) =>
                    setFormComision((prev) =>
                      prev ? { ...prev, codigoMatriculacion: e.target.value } : prev,
                    )
                  }
                  className={`${INPUT_CLASS} font-mono`}
                />
                {formComision.codigoMatriculacion.trim() && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={enviandoComision}
                    onClick={() =>
                      void navigator.clipboard?.writeText(
                        formComision.codigoMatriculacion.trim(),
                      )
                    }
                  >
                    <Icon name="content_copy" className="text-[18px]" />
                    Copiar
                  </Button>
                )}
              </div>
              <p className="text-[11px] text-on-surface-variant mt-1">
                El alumno usa este código para unirse a la comisión (como la clave de
                matriculación de Moodle).
              </p>
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
                onClick={onCancelarComision}
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
            onClick={() => abrirCrearComision(materiaId)}
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
                  <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-8 py-2">Código</th>
                  <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2">Nombre</th>
                  <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2">Período</th>
                  <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2">Año</th>
                  <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2">Cód. matriculación</th>
                  <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2">Docente a cargo</th>
                  <th className="text-right text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-4 py-2">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/20">
                {comisiones.map((c) => {
                  const comExpandida = comisionExpandida === c.id;
                  return (
                    <Fragment key={c.id}>
                      <tr className="hover:bg-surface-container/50 transition-colors">
                        <td className="px-8 py-3 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              aria-label={comExpandida ? `Ocultar alumnos de ${c.nombre}` : `Ver alumnos de ${c.nombre}`}
                              aria-expanded={comExpandida}
                              onClick={() => toggleComision(c.id)}
                              className="w-6 h-6 rounded-md flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors shrink-0"
                            >
                              <Icon name={comExpandida ? 'keyboard_arrow_down' : 'keyboard_arrow_right'} className="text-[18px]" />
                            </button>
                            <span className="font-mono text-[12px] text-on-surface-variant bg-surface-100 border border-outline-variant/40 px-2 py-0.5 rounded-md">
                              {c.codigo ?? '—'}
                            </span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-[13px] text-on-surface">
                          <span className="inline-flex items-center gap-2">
                            <span>{c.nombre}</span>
                            {c.activa === false && (
                              <span className="shrink-0 inline-flex items-center gap-1 rounded-full bg-outline-variant/40 text-on-surface-variant px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide">
                                <Icon name="pause_circle" className="text-[12px]" />
                                Inactiva
                              </span>
                            )}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-[13px] text-on-surface-variant">{c.periodo ?? '—'}</td>
                        <td className="px-4 py-3 text-[13px] text-on-surface-variant tabular-nums">{c.anio ?? '—'}</td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          {c.codigo_matriculacion ? (
                            <span className="font-mono text-[12px] text-primary bg-primary-container/40 px-2 py-0.5 rounded-md">
                              {c.codigo_matriculacion}
                            </span>
                          ) : (
                            <span className="text-[13px] text-on-surface-variant">—</span>
                          )}
                        </td>
                        {/* Docente a cargo: sin él las notas de esta comisión NO se
                            sincronizan al campus. Se avisa acá, donde se gestiona la
                            comisión, y no cuando el alumno ya rindió. */}
                        <td className="px-4 py-3 whitespace-nowrap text-[13px]">
                          {docenteLocal[c.id] ?? c.docente_nombre ? (
                            <span className="text-on-surface">
                              {docenteLocal[c.id] ?? c.docente_nombre}
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-error">
                              <Icon name="person_off" className="text-[14px]" />
                              sin asignar
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <ActionMenu
                            ariaLabel={`Acciones de ${c.nombre}`}
                            items={accionesComision(c, comExpandida)}
                          />
                        </td>
                      </tr>
                      {comExpandida && (
                        <tr>
                          <td colSpan={7} className="p-0">
                            <AlumnosComisionPanel comisionId={c.id} comisionNombre={c.nombre} />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Cards mobile */}
          <div className="sm:hidden divide-y divide-outline-variant/20">
            {comisiones.map((c) => {
              const comExpandida = comisionExpandida === c.id;
              return (
                <div key={c.id}>
                  <div className="px-8 py-3 flex items-center justify-between gap-3">
                    <button
                      type="button"
                      aria-label={comExpandida ? `Ocultar alumnos de ${c.nombre}` : `Ver alumnos de ${c.nombre}`}
                      aria-expanded={comExpandida}
                      onClick={() => toggleComision(c.id)}
                      className="w-6 h-6 rounded-md flex items-center justify-center text-on-surface-variant hover:bg-surface-container shrink-0"
                    >
                      <Icon name={comExpandida ? 'keyboard_arrow_down' : 'keyboard_arrow_right'} className="text-[18px]" />
                    </button>
                    <div className="min-w-0 flex-1">
                      <p className="text-[13px] font-medium text-on-surface truncate flex items-center gap-2">
                        <span className="truncate">{c.nombre}</span>
                        {c.activa === false && (
                          <span className="shrink-0 inline-flex items-center gap-1 rounded-full bg-outline-variant/40 text-on-surface-variant px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide">
                            <Icon name="pause_circle" className="text-[12px]" />
                            Inactiva
                          </span>
                        )}
                      </p>
                      <p className="text-[11px] text-on-surface-variant font-mono mt-0.5">
                        {c.codigo ?? '—'}{c.periodo ? ` · ${c.periodo}` : ''}{c.anio ? ` · ${c.anio}` : ''}
                      </p>
                      {c.codigo_matriculacion && (
                        <p className="text-[11px] mt-0.5">
                          <span className="text-on-surface-variant">Matriculación: </span>
                          <span className="font-mono text-primary">{c.codigo_matriculacion}</span>
                        </p>
                      )}
                      {/* Sin docente a cargo, las notas de esta comisión NO se
                          sincronizan al campus. Se avisa acá —donde se gestiona la
                          comisión— y no cuando el alumno ya rindió. */}
                      <p className="text-[11px] mt-0.5">
                        <span className="text-on-surface-variant">Docente: </span>
                        {docenteLocal[c.id] ?? c.docente_nombre ? (
                          <span className="text-on-surface">
                            {docenteLocal[c.id] ?? c.docente_nombre}
                          </span>
                        ) : (
                          <span className="text-error">sin asignar</span>
                        )}
                      </p>
                    </div>
                    <ActionMenu
                      ariaLabel={`Acciones de ${c.nombre}`}
                      items={accionesComision(c, comExpandida)}
                    />
                  </div>
                  {comExpandida && (
                    <AlumnosComisionPanel comisionId={c.id} comisionNombre={c.nombre} />
                  )}
                </div>
              );
            })}
          </div>
        </>
      ) : null}

      {/* C-73 §9.5 — quién queda a cargo decide con qué cuenta se devuelven las notas. */}
      {asignando && (
        <AsignarDocenteDialog
          comisionId={asignando.id}
          comisionNombre={asignando.nombre}
          docenteActualId={asignando.docente_id}
          onCerrar={() => setAsignando(null)}
          onAsignado={(_id, nombre) =>
            setDocenteLocal((prev) => ({ ...prev, [asignando.id]: nombre }))
          }
        />
      )}
    </div>
  );
}
