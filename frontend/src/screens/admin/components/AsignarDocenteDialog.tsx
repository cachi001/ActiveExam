/**
 * AsignarDocenteDialog — agrega o quita tutores a cargo de una comisión (c-79, N:M).
 *
 * Por qué importa más de lo que parece: cada tutor a cargo es quien puede devolver
 * las notas de la comisión al campus con SU cuenta, y es contra quien se valida que
 * un tutor solo toque los exámenes de lo suyo. Una comisión sin tutores no puede
 * sincronizar notas (quedan retenidas con el motivo «Falta conectar la cuenta del
 * campus»). Desde c-79 una comisión puede tener VARIOS tutores (co-dictado,
 * cobertura de licencias) — ya no uno solo.
 *
 * Los propios tutores NO pueden autoasignarse: la capacidad `asignar_docente` no
 * los incluye. Si pudieran, la validación de pertenencia dejaría de ser un control.
 */
import { useEffect, useState } from 'react';
import { adminApi } from '../../../lib/apiAdmin';
import { Button, Icon } from '../../../ui/components';
import { ModalOverlay } from '../../../ui/ModalOverlay';

type Docente = { id: string; nombre: string; legajo: string };
type TutorInfo = { id: string; nombre: string };

export function AsignarDocenteDialog({
  comisionId,
  comisionNombre,
  tutoresActuales,
  onCerrar,
  onCambiado,
}: {
  comisionId: string;
  comisionNombre: string;
  tutoresActuales: TutorInfo[];
  onCerrar: () => void;
  onCambiado: (tutores: TutorInfo[]) => void;
}) {
  const [docentes, setDocentes] = useState<Docente[]>([]);
  const [tutores, setTutores] = useState<TutorInfo[]>(tutoresActuales);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    adminApi
      // OJO con la firma: es (limit, offset, filtros). Invertirlos pide 1 resultado
      // salteando los primeros 200, y el selector queda vacío sin ningún error.
      .listarUsuarios(200, 0, { rol: 'tutor', estado: 'activo' })
      .then((r) => {
        if (!vivo) return;
        const items = (r as { items?: unknown[] }).items ?? [];
        setDocentes(
          items.map((u) => {
            const x = u as {
              id: string;
              nombre?: string;
              apellido?: string;
              username?: string;
            };
            const completo = [x.nombre, x.apellido].filter(Boolean).join(' ').trim();
            return {
              id: x.id,
              legajo: x.username ?? '',
              // Sin nombre cargado se muestra el legajo: un UUID no le sirve a nadie.
              nombre: completo || (x.username ?? x.id),
            };
          }),
        );
      })
      .catch(() => vivo && setError('No se pudo cargar la lista de docentes.'))
      .finally(() => vivo && setCargando(false));
    return () => {
      vivo = false;
    };
  }, []);

  const disponibles = docentes.filter((d) => !tutores.some((t) => t.id === d.id));

  async function agregar(docenteId: string) {
    setGuardando(true);
    setError(null);
    try {
      const r = await adminApi.agregarTutorComision(comisionId, docenteId);
      setTutores(r.tutores);
      onCambiado(r.tutores);
    } catch (err) {
      const e = err as { mensaje?: string };
      setError(e.mensaje ?? 'No se pudo agregar el tutor.');
    } finally {
      setGuardando(false);
    }
  }

  async function quitar(tutorId: string) {
    setGuardando(true);
    setError(null);
    try {
      const r = await adminApi.quitarTutorComision(comisionId, tutorId);
      setTutores(r.tutores);
      onCambiado(r.tutores);
    } catch (err) {
      const e = err as { mensaje?: string };
      setError(e.mensaje ?? 'No se pudo quitar el tutor.');
    } finally {
      setGuardando(false);
    }
  }

  return (
    <ModalOverlay etiqueta={`Tutores de ${comisionNombre}`} onCerrar={guardando ? undefined : onCerrar}>
      <div className="w-full max-w-md bg-white rounded-lg border border-surface-200 shadow-lg flex flex-col max-h-[85vh]">
        <header className="flex items-start justify-between gap-md px-lg pt-lg pb-md border-b border-surface-200">
          <div className="min-w-0">
            <h2 className="text-title-lg text-on-surface">Tutores a cargo</h2>
            <p className="text-label-md text-on-surface-variant mt-0.5 truncate">
              {comisionNombre}
            </p>
          </div>
          <button
            type="button"
            onClick={onCerrar}
            disabled={guardando}
            aria-label="Cerrar"
            className="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors disabled:opacity-40 shrink-0"
          >
            <Icon name="close" className="text-[20px]" />
          </button>
        </header>

        <div className="px-lg py-lg space-y-lg overflow-y-auto">
          {cargando ? (
            <div className="h-[120px] animate-pulse bg-surface-container-low rounded-lg" />
          ) : (
            <>
              {/* Los asignados como LISTA, no como chips apretados junto al select:
                  son el dato principal del diálogo y con dos o tres nombres largos
                  los chips se amontonaban en varias filas sin jerarquía. */}
              <section>
                <h3 className="text-label-sm text-on-surface-variant uppercase tracking-wider mb-sm">
                  Asignados ({tutores.length})
                </h3>
                {tutores.length === 0 ? (
                  <div className="flex items-start gap-sm rounded-lg bg-error-container/30 px-md py-sm">
                    <Icon name="person_off" className="text-[20px] shrink-0 text-error mt-0.5" />
                    <p className="text-body-md text-on-surface">
                      Sin tutores todavía. Las notas de esta comisión no se van a
                      sincronizar con el campus hasta que asignes al menos uno.
                    </p>
                  </div>
                ) : (
                  <ul className="rounded-lg border border-surface-200 divide-y divide-surface-200">
                    {tutores.map((t) => (
                      <li key={t.id} className="flex items-center gap-sm px-md py-sm">
                        <span className="w-8 h-8 rounded-full bg-primary text-on-primary flex items-center justify-center font-semibold text-[13px] shrink-0">
                          {t.nombre.trim().charAt(0).toUpperCase()}
                        </span>
                        <span className="text-body-md text-on-surface break-words flex-1 min-w-0">
                          {t.nombre}
                        </span>
                        <button
                          type="button"
                          onClick={() => void quitar(t.id)}
                          disabled={guardando}
                          aria-label={`Quitar a ${t.nombre}`}
                          className="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:bg-error-container/40 hover:text-error transition-colors disabled:opacity-40 shrink-0"
                        >
                          <Icon name="close" className="text-[18px]" />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section>
                <label
                  className="block text-label-sm text-on-surface-variant uppercase tracking-wider mb-sm"
                  htmlFor="docente-sel"
                >
                  Agregar tutor
                </label>
                <select
                  id="docente-sel"
                  className="w-full rounded-lg border border-surface-300 bg-white px-md py-sm text-body-md text-on-surface focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 disabled:bg-surface-100 disabled:text-on-surface-variant disabled:cursor-not-allowed"
                  disabled={guardando || disponibles.length === 0}
                  value=""
                  onChange={(e) => {
                    if (e.target.value) void agregar(e.target.value);
                  }}
                >
                  <option value="">
                    {disponibles.length === 0 ? 'No hay más tutores disponibles' : 'Elegir…'}
                  </option>
                  {disponibles.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.legajo ? `${d.nombre} · ${d.legajo}` : d.nombre}
                    </option>
                  ))}
                </select>
                <p className="text-label-sm text-on-surface-variant mt-sm leading-relaxed">
                  Las notas se devuelven al campus con la cuenta de cada tutor a cargo.
                </p>
              </section>
            </>
          )}

          {error && (
            <p className="text-label-md text-error flex items-start gap-1.5">
              <Icon name="error" className="text-[18px] shrink-0 mt-0.5" fill />
              {error}
            </p>
          )}
        </div>

        <footer className="flex justify-end px-lg py-md border-t border-surface-200">
          <Button variant="primary" onClick={onCerrar} disabled={guardando}>
            Listo
          </Button>
        </footer>
      </div>
    </ModalOverlay>
  );
}
