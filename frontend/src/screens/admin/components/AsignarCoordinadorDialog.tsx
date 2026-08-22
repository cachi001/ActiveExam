/**
 * AsignarCoordinadorDialog — agrega o quita coordinadores a cargo de una materia
 * (c-79, N:M). Gemelo de AsignarDocenteDialog, un nivel más arriba: el tutor se
 * asigna a una COMISIÓN, el coordinador a la MATERIA entera.
 *
 * Por qué existe: hasta c-79 el coordinador tenía alcance institucional (veía y
 * tocaba todo, igual que un admin). Ahora queda acotado a las materias donde
 * figura asignado, así que sin esta pantalla el rol quedaba inutilizable — un
 * coordinador sin materias asignadas NO VE NADA, y no había forma de asignárselas
 * desde la aplicación.
 *
 * Los coordinadores NO pueden autoasignarse una materia ajena: el backend exige
 * `asignar_docente` y, si quien llama es coordinador, valida que la materia sea
 * suya. Acá el botón se muestra solo a quien administra la estructura.
 */
import { useEffect, useState } from 'react';
import { adminApi } from '../../../lib/apiAdmin';
import { Button, Icon } from '../../../ui/components';

type Candidato = { id: string; nombre: string; legajo: string };
type CoordinadorInfo = { id: string; nombre: string };

export function AsignarCoordinadorDialog({
  materiaId,
  materiaNombre,
  coordinadoresActuales,
  onCerrar,
  onCambiado,
}: {
  materiaId: string;
  materiaNombre: string;
  coordinadoresActuales: CoordinadorInfo[];
  onCerrar: () => void;
  onCambiado: (coordinadores: CoordinadorInfo[]) => void;
}) {
  const [candidatos, setCandidatos] = useState<Candidato[]>([]);
  const [coordinadores, setCoordinadores] =
    useState<CoordinadorInfo[]>(coordinadoresActuales);
  const [paraAgregar, setParaAgregar] = useState<string>('');
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    adminApi
      // OJO con la firma: es (limit, offset, filtros). Invertirlos pide 1 resultado
      // salteando los primeros 200, y el selector queda vacío sin ningún error.
      .listarUsuarios(200, 0, { rol: 'coordinador', estado: 'activo' })
      .then((r) => {
        if (!vivo) return;
        const items = (r as { items?: unknown[] }).items ?? [];
        setCandidatos(
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
      .catch(() => vivo && setError('No se pudo cargar la lista de coordinadores.'))
      .finally(() => vivo && setCargando(false));
    return () => {
      vivo = false;
    };
  }, []);

  const disponibles = candidatos.filter(
    (c) => !coordinadores.some((x) => x.id === c.id),
  );

  async function agregar() {
    if (!paraAgregar) return;
    setGuardando(true);
    setError(null);
    try {
      const r = await adminApi.agregarCoordinadorMateria(materiaId, paraAgregar);
      setCoordinadores(r.coordinadores);
      onCambiado(r.coordinadores);
      setParaAgregar('');
    } catch (err) {
      const e = err as { mensaje?: string };
      setError(e.mensaje ?? 'No se pudo agregar el coordinador.');
    } finally {
      setGuardando(false);
    }
  }

  async function quitar(coordinadorId: string) {
    setGuardando(true);
    setError(null);
    try {
      const r = await adminApi.quitarCoordinadorMateria(materiaId, coordinadorId);
      setCoordinadores(r.coordinadores);
      onCambiado(r.coordinadores);
    } catch (err) {
      const e = err as { mensaje?: string };
      setError(e.mensaje ?? 'No se pudo quitar el coordinador.');
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={`Coordinadores de ${materiaNombre}`}
    >
      <div className="card w-full max-w-md p-lg">
        <h2 className="text-title-sm font-semibold text-on-surface">
          Coordinadores a cargo
        </h2>
        <p className="text-label-sm text-on-surface-variant mt-0.5 mb-md">
          {materiaNombre}
        </p>

        {cargando ? (
          <div className="h-[80px] animate-pulse bg-surface-container-low rounded-md" />
        ) : (
          <>
            {coordinadores.length > 0 ? (
              <ul className="flex flex-col gap-1.5 mb-md">
                {coordinadores.map((c) => (
                  <li
                    key={c.id}
                    className="flex items-center justify-between rounded-md bg-surface-container-low px-3 py-1.5"
                  >
                    <span className="text-label-md text-on-surface">{c.nombre}</span>
                    <button
                      type="button"
                      className="text-on-surface-variant hover:text-error disabled:opacity-50"
                      disabled={guardando}
                      onClick={() => quitar(c.id)}
                      aria-label={`Quitar a ${c.nombre}`}
                    >
                      <Icon name="close" className="text-[16px]" />
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-label-sm text-on-surface-variant mb-md">
                Sin coordinadores asignados todavía.
              </p>
            )}

            <label
              className="text-label-sm text-on-surface-variant"
              htmlFor="coordinador-sel"
            >
              Agregar coordinador
            </label>
            <div className="flex gap-2 mt-1">
              <select
                id="coordinador-sel"
                className="input w-full"
                value={paraAgregar}
                disabled={guardando || disponibles.length === 0}
                onChange={(e) => setParaAgregar(e.target.value)}
              >
                <option value="">
                  {disponibles.length === 0
                    ? 'No hay más coordinadores disponibles'
                    : 'Elegir…'}
                </option>
                {disponibles.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nombre}
                    {c.legajo ? ` · ${c.legajo}` : ''}
                  </option>
                ))}
              </select>
              <Button
                variant="secondary"
                size="sm"
                onClick={agregar}
                disabled={guardando || !paraAgregar}
              >
                Agregar
              </Button>
            </div>
            <p className="text-label-sm text-on-surface-variant mt-1.5">
              El coordinador ve y revisa únicamente las materias que tiene asignadas.
              Sin ninguna asignada, entra al sistema y no ve contenido.
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
