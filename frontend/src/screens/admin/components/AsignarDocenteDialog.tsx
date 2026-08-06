/**
 * AsignarDocenteDialog — pone (o quita) el tutor a cargo de una comisión.
 *
 * Por qué importa más de lo que parece: ese docente es quien devuelve las notas de
 * la comisión al campus con SU cuenta, y es contra quien se valida que un tutor
 * solo toque los exámenes de lo suyo. Una comisión sin docente no puede sincronizar
 * notas (quedan retenidas con el motivo «Falta conectar la cuenta del campus»).
 *
 * El propio docente NO puede autoasignarse: la capacidad `asignar_docente` no lo
 * incluye. Si pudiera, la validación de pertenencia dejaría de ser un control.
 */
import { useEffect, useState } from 'react';
import { adminApi } from '../../../lib/apiAdmin';
import { Button, Icon } from '../../../ui/components';

type Docente = { id: string; nombre: string; legajo: string };

export function AsignarDocenteDialog({
  comisionId,
  comisionNombre,
  docenteActualId,
  onCerrar,
  onAsignado,
}: {
  comisionId: string;
  comisionNombre: string;
  docenteActualId?: string | null;
  onCerrar: () => void;
  onAsignado: (docenteId: string | null, docenteNombre: string | null) => void;
}) {
  const [docentes, setDocentes] = useState<Docente[]>([]);
  const [seleccionado, setSeleccionado] = useState<string>(docenteActualId ?? '');
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
              id_institucional?: string;
            };
            const completo = [x.nombre, x.apellido].filter(Boolean).join(' ').trim();
            return {
              id: x.id,
              legajo: x.id_institucional ?? '',
              // Sin nombre cargado se muestra el legajo: un UUID no le sirve a nadie.
              nombre: completo || (x.id_institucional ?? x.id),
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

  async function guardar() {
    setGuardando(true);
    setError(null);
    try {
      const r = await adminApi.asignarDocenteComision(comisionId, seleccionado || null);
      onAsignado(r.docente_id, r.docente_nombre);
      onCerrar();
    } catch (err) {
      const e = err as { mensaje?: string };
      setError(e.mensaje ?? 'No se pudo asignar el tutor.');
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={`Asignar tutor de ${comisionNombre}`}
    >
      <div className="card w-full max-w-md p-lg">
        <h2 className="text-title-sm font-semibold text-on-surface">Asignar tutor</h2>
        <p className="text-label-sm text-on-surface-variant mt-0.5 mb-md">
          {comisionNombre}
        </p>

        {cargando ? (
          <div className="h-[80px] animate-pulse bg-surface-container-low rounded-md" />
        ) : (
          <>
            <label className="text-label-sm text-on-surface-variant" htmlFor="docente-sel">
              Tutor
            </label>
            <select
              id="docente-sel"
              className="input w-full mt-1"
              value={seleccionado}
              disabled={guardando}
              onChange={(e) => setSeleccionado(e.target.value)}
            >
              <option value="">Sin tutor asignado</option>
              {docentes.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.nombre}
                  {d.legajo ? ` · ${d.legajo}` : ''}
                </option>
              ))}
            </select>
            <p className="text-label-sm text-on-surface-variant mt-1.5">
              Las notas de esta comisión se devuelven al campus con la cuenta de esta
              persona. Sin tutor asignado, las notas no se sincronizan.
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
          <Button variant="ghost" size="sm" onClick={onCerrar} disabled={guardando}>
            Cancelar
          </Button>
          <Button variant="primary" onClick={guardar} disabled={guardando || cargando}>
            {guardando ? 'Guardando…' : 'Guardar'}
          </Button>
        </div>
      </div>
    </div>
  );
}
