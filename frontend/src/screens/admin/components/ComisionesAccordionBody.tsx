import type React from 'react';
import { Fragment, useState } from 'react';
import { Icon, Button } from '../../../ui/components';
import { ModalOverlay } from '../../../ui/ModalOverlay';
import { ActionMenu, type ActionItem } from '../../../ui/ActionMenu';
import type { Comision } from '../../../lib/types';
import { useNavigate } from '../../../lib/router';
import { AsignarDocenteDialog } from './AsignarDocenteDialog';
import { DetalleComisionDialog } from './DetalleComisionDialog';
import { resumenTutores } from './resumenTutores';
import { useAuth } from '../../../lib/authStore';
import { tieneCapacidad } from '../../../lib/capabilities';
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
  /** Baja lógica: da de baja o reactiva la comisión (C-72 §17, c-78). */
  onToggleActivaComision: (c: Comision) => void;
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
  onToggleActivaComision,
}: ComisionesAccordionBodyProps) {
  const navigate = useNavigate();
  // C-73 §9.5: docente a cargo de la comisión.
  const esAdmin = useAuth((st) => st.hasRole)(['admin_sistema']);
  // Crear/editar/borrar comisiones = estructura académica (admin). El tutor
  // puede ver alumnos e inscribir, pero no editar la estructura de la comisión.
  const rolesActuales = useAuth((s) => s.principal?.roles) ?? [];
  const puedeEditarEstructura = tieneCapacidad(rolesActuales, 'gestionar_estructura');
  const [asignando, setAsignando] = useState<Comision | null>(null);
  const [detallando, setDetallando] = useState<Comision | null>(null);
  const [tutoresLocal, setTutoresLocal] = useState<Record<string, { id: string; nombre: string }[]>>({});
  // Los tutores vigentes de una comisión: los recién editados si se tocaron en
  // esta pantalla, si no los que trajo el servidor.
  const tutoresDe = (c: Comision) => tutoresLocal[c.id] ?? c.tutores ?? [];
  // Acciones del menú kebab por comisión. UN SOLO patrón de baja (c-78): dar de
  // baja / reactivar. Antes convivían dos entradas que hacían lo mismo — "Eliminar
  // comisión" ya no borraba nada desde que la baja pasó a ser lógica, y encima
  // solo aparecía con la comisión VACÍA, así que una comisión con inscriptos no
  // se podía dar de baja desde ninguna parte (el toggle estaba declarado pero
  // nunca cableado al menú).
  const accionesComision = (c: Comision): ActionItem[] => {
    return [
      // "Ver detalle" es la contraparte de haber achicado la fila: los tutores
      // por nombre y el resto de los datos de la comisión salieron de las
      // columnas para no seguir ensanchando la tabla, y viven acá.
      { label: 'Ver detalle', icon: 'info', onClick: () => setDetallando(c) },
      // Pantalla propia (no un panel expandible acá adentro): con varios
      // inscriptos el acordeón empujaba el resto de esta pantalla fuera de vista.
      { label: 'Ver alumnos', icon: 'groups', onClick: () => navigate(`/admin/materias/${c.id}/alumnos`) },
      ...(puedeEditarEstructura
        ? [{ label: 'Editar comisión', icon: 'edit', onClick: () => abrirEditarComision(materiaId, c) } as ActionItem]
        : []),
      // Solo admin_sistema: la lista de usuarios (de donde sale el selector) es
      // admin-only, así que ofrecérselo a otro rol daría un diálogo vacío.
      ...(esAdmin
        ? [{
            label: (tutoresLocal[c.id] ?? c.tutores)?.length ? 'Gestionar tutores' : 'Asignar tutor',
            icon: 'person',
            onClick: () => setAsignando(c),
          } as ActionItem]
        : []),
      ...(puedeEditarEstructura
        ? [
            c.activa === false
              ? { label: 'Reactivar comisión', icon: 'play_circle', onClick: () => onToggleActivaComision(c) } as ActionItem
              : { label: 'Dar de baja la comisión', icon: 'delete', danger: true, onClick: () => onToggleActivaComision(c) } as ActionItem,
          ]
        : []),
    ];
  };
  return (
    <div className="border-t border-outline-variant/20">
      {/* Formulario de comisión */}
      {mostrarFormComision && formComision && (
        <ModalOverlay
          etiqueta={formComision.modo === 'crear' ? 'Nueva comisión' : 'Editar comisión'}
          onCerrar={enviandoComision ? undefined : onCancelarComision}
        >
        <div className="w-full max-w-2xl bg-white rounded-lg border border-surface-200 shadow-lg flex flex-col max-h-[85vh]">
        <header className="flex items-center justify-between gap-md px-lg pt-lg pb-md border-b border-surface-200">
          <h2 className="text-title-lg text-on-surface">
            {formComision.modo === 'crear' ? 'Nueva comisión' : 'Editar comisión'}
          </h2>
          <button
            type="button"
            onClick={onCancelarComision}
            disabled={enviandoComision}
            aria-label="Cerrar"
            className="text-on-surface-variant hover:text-on-surface disabled:opacity-50"
          >
            <Icon name="close" className="text-[22px]" />
          </button>
        </header>
        <div className="px-lg py-lg overflow-y-auto">
          <form onSubmit={onSubmitComision} className="space-y-5">
            <div className="grid sm:grid-cols-2 gap-5">
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
            </div>

            <div className="grid sm:grid-cols-2 gap-5">
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

            <div className="flex gap-sm justify-end pt-2 border-t border-surface-200">
              <Button
                type="button"
                variant="ghost"
                onClick={onCancelarComision}
                disabled={enviandoComision}
              >
                Cancelar
              </Button>
              <Button type="submit" disabled={enviandoComision}>
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
        </div>
        </ModalOverlay>
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
          {puedeEditarEstructura && (
            <button
              type="button"
              onClick={() => abrirCrearComision(materiaId)}
              className="text-primary hover:underline font-medium ml-1"
            >
              Agregar la primera
            </button>
          )}
        </div>
      ) : comisiones && comisiones.length > 0 ? (
        <>
          {/* Tabla desktop. El corte es `xl` (1280px) y no `sm`: son siete columnas
              dentro de una card que además comparte la fila con la lista de materias,
              y por debajo de ese ancho la tabla scrolleaba en horizontal con la
              columna Acciones anclada encima de la de Tutor, que quedaba ilegible.
              Abajo de 1280 se usan las cards, que muestran los mismos datos sin
              esconder ninguno. */}
          <div className="hidden xl:block overflow-x-auto">
            {/* `min-w-full` (min-width: 100%), SIN `table-fixed` ni anchos en
                px por columna: el navegador arma la tabla con su algoritmo
                nativo de `table-layout: auto`, que primero mide cuánto necesita
                cada columna por su contenido y RECIÉN DESPUÉS reparte el
                sobrante entre TODAS proporcionalmente para llegar al ancho
                mínimo pedido. Los anchos en px fijos que probé antes sumaban
                más que el ancho real de la card en pantallas más chicas que la
                que usé para probar, y esa cuenta que no cerraba colapsaba la
                columna Nombre a casi nada (superponía su texto con Período).
                `min-w-full` no puede fallar así: nunca le pide a una columna
                más de lo que su contenido necesita, solo AGRANDA lo que ya
                está. `divide-x` marca el límite entre columnas con una línea
                fina para que no se lean mezcladas. */}
            <table className="min-w-full border-separate border-spacing-0">
              <thead>
                <tr className="bg-surface-container divide-x divide-outline-variant/30">
                  <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider pl-4 pr-5 py-2 whitespace-nowrap">Código</th>
                  <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-5 py-2 whitespace-nowrap">Nombre</th>
                  <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-5 py-2 whitespace-nowrap">Período</th>
                  <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-5 py-2 whitespace-nowrap">Año</th>
                  <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-5 py-2 whitespace-nowrap">Cód. matriculación</th>
                  <th className="text-left text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider px-5 py-2 whitespace-nowrap">Tutor</th>
                  {/* Sticky a la derecha: guarda contra el caso ANGOSTO real (una
                      ventana más chica que 1280px sigue mostrando esta tabla si el
                      usuario hace zoom-out, por ejemplo) donde sí hace falta scroll
                      horizontal y el menú de acciones no puede quedar fuera de vista. */}
                  <th className="sticky right-0 z-10 bg-surface-container text-right text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider pl-5 pr-4 py-2 whitespace-nowrap">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/20">
                {comisiones.map((c) => {
                  return (
                    <Fragment key={c.id}>
                      <tr className="divide-x divide-outline-variant/20">
                        <td className="pl-4 pr-5 py-3 whitespace-nowrap">
                          <span className="font-mono text-[12px] text-on-surface-variant bg-surface-100 border border-outline-variant/40 px-2 py-0.5 rounded-md">
                            {c.codigo ?? '—'}
                          </span>
                        </td>
                        <td className="px-5 py-3 text-[13px] text-on-surface whitespace-nowrap">
                          <span className="inline-flex items-center gap-2">
                            <span>{c.nombre}</span>
                            {c.activa === false && (
                              <span className="shrink-0 inline-flex items-center gap-1 rounded-full bg-outline-variant/40 text-on-surface-variant px-2 py-0.5 text-[10px] font-medium">
                                <Icon name="pause_circle" className="text-[12px]" />
                                Inactiva
                              </span>
                            )}
                          </span>
                        </td>
                        <td className="px-5 py-3 text-[13px] text-on-surface-variant whitespace-nowrap">{c.periodo ?? '—'}</td>
                        <td className="px-5 py-3 text-[13px] text-on-surface-variant tabular-nums whitespace-nowrap">{c.anio ?? '—'}</td>
                        <td className="px-5 py-3 whitespace-nowrap text-[13px] text-on-surface">
                          {c.codigo_matriculacion || <span className="text-on-surface-variant">—</span>}
                        </td>
                        {/* Docente a cargo: sin él las notas de esta comisión NO se
                            sincronizan al campus. Se avisa acá, donde se gestiona la
                            comisión, y no cuando el alumno ya rindió. */}
                        {/* La CANTIDAD, no los nombres: concatenados estiraban la fila
                            hasta forzar scroll horizontal, y ese scroll dejaba esta
                            misma columna tapada por la de Acciones, que está anclada.
                            Los nombres están en "Ver detalle". */}
                        <td className="px-5 py-3 whitespace-nowrap text-[13px]">
                          {tutoresDe(c).length ? (
                            <span className="text-on-surface">{resumenTutores(tutoresDe(c))}</span>
                          ) : (
                            <span className="text-error">{resumenTutores(tutoresDe(c))}</span>
                          )}
                        </td>
                        <td className="sticky right-0 z-10 bg-white pl-5 pr-4 py-3 text-right whitespace-nowrap">
                          <ActionMenu
                            ariaLabel={`Acciones de ${c.nombre}`}
                            items={accionesComision(c)}
                          />
                        </td>
                      </tr>
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Cards: mobile y todo lo que esté por debajo de 1280px (ver el comentario
              de la tabla). Muestran los mismos datos que las columnas. */}
          <div className="xl:hidden divide-y divide-outline-variant/20">
            {comisiones.map((c) => {
              return (
                <div key={c.id}>
                  <div className="px-8 py-3 flex items-center justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-[13px] font-medium text-on-surface truncate flex items-center gap-2">
                        <span className="truncate">{c.nombre}</span>
                        {c.activa === false && (
                          <span className="shrink-0 inline-flex items-center gap-1 rounded-full bg-outline-variant/40 text-on-surface-variant px-2 py-0.5 text-[10px] font-medium">
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
                          <span className="text-on-surface">{c.codigo_matriculacion}</span>
                        </p>
                      )}
                      {/* Sin docente a cargo, las notas de esta comisión NO se
                          sincronizan al campus. Se avisa acá —donde se gestiona la
                          comisión— y no cuando el alumno ya rindió. */}
                      {/* Igual que en la tabla: la cantidad, y los nombres en el
                          detalle. Acá además la card es angosta. */}
                      <p className="text-[11px] mt-0.5">
                        <span className="text-on-surface-variant">Tutor: </span>
                        {tutoresDe(c).length ? (
                          <span className="text-on-surface">{resumenTutores(tutoresDe(c))}</span>
                        ) : (
                          <span className="text-error">{resumenTutores(tutoresDe(c))}</span>
                        )}
                      </p>
                    </div>
                    <ActionMenu
                      ariaLabel={`Acciones de ${c.nombre}`}
                      items={accionesComision(c)}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </>
      ) : null}

      {detallando && (
        <DetalleComisionDialog
          comision={detallando}
          tutores={tutoresDe(detallando)}
          onCerrar={() => setDetallando(null)}
        />
      )}

      {/* C-73 §9.5 — quién queda a cargo decide con qué cuenta se devuelven las notas. */}
      {asignando && (
        <AsignarDocenteDialog
          comisionId={asignando.id}
          comisionNombre={asignando.nombre}
          tutoresActuales={tutoresLocal[asignando.id] ?? asignando.tutores ?? []}
          onCerrar={() => setAsignando(null)}
          onCambiado={(tutores) =>
            setTutoresLocal((prev) => ({ ...prev, [asignando.id]: tutores }))
          }
        />
      )}
    </div>
  );
}
