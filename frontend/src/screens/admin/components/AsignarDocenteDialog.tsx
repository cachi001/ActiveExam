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
import { ChipMultiSelect } from '../../../ui/ChipMultiSelect';

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
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={`Tutores de ${comisionNombre}`}
    >
      <div className="card w-full max-w-md p-lg">
        <h2 className="text-title-sm font-semibold text-on-surface">Tutores a cargo</h2>
        <p className="text-label-sm text-on-surface-variant mt-0.5 mb-md">
          {comisionNombre}
        </p>

        {cargando ? (
          <div className="h-[80px] animate-pulse bg-surface-container-low rounded-md" />
        ) : (
          <>
            {tutores.length === 0 && (
              <p className="text-label-sm text-on-surface-variant mb-md">
                Sin tutores asignados todavía.
              </p>
            )}

            <label className="text-label-sm text-on-surface-variant" htmlFor="docente-sel">
              Agregar tutor
            </label>
            <div className="mt-1">
              <ChipMultiSelect
                id="docente-sel"
                className="input w-full"
                disabled={guardando || disponibles.length === 0}
                seleccionados={tutores.map((t) => ({ id: t.id, textoOpcion: t.nombre }))}
                disponibles={disponibles.map((d) => ({
                  id: d.id,
                  textoOpcion: d.legajo ? `${d.nombre} · ${d.legajo}` : d.nombre,
                  textoChip: d.nombre,
                }))}
                onAgregar={agregar}
                onQuitar={quitar}
                textoOpcionVacia={
                  disponibles.length === 0 ? 'No hay más tutores disponibles' : 'Elegir…'
                }
              />
            </div>
            <p className="text-label-sm text-on-surface-variant mt-1.5">
              Las notas de esta comisión se devuelven al campus con la cuenta de cada
              tutor a cargo. Sin tutores asignados, las notas no se sincronizan.
            </p>
          </>
        )}

        {error && (
          <p className="text-label-sm text-error mt-md flex items-center gap-1.5">
            <Icon name="error" className="text-[16px]" />
            {error}
          </p>
        )}

        <div className="flex justify-end gap-sm mt-lg">
          <Button variant="primary" onClick={onCerrar} disabled={guardando}>
            Listo
          </Button>
        </div>
      </div>
    </div>
  );
}
