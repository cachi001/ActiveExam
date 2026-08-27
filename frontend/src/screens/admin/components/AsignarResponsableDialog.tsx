/**
 * AsignarResponsableDialog — agrega o quita responsables a cargo de una materia.
 *
 * Cubre los DOS roles de materia con un solo componente:
 *   - COORDINADOR (c-79): además de lo académico, emite el veredicto de integridad.
 *   - PROFESOR (c-78): arma exámenes y banco de la materia, sin veredicto.
 *
 * Por qué uno y no dos: los diálogos serían idénticos salvo el rol que filtran y
 * el texto. Dos archivos casi iguales divergen — es la misma clase de problema
 * que este change vino a corregir en los contadores. Lo que cambia entre roles
 * está declarado abajo, en un solo lugar (`CONFIG_ROL`).
 *
 * Nadie puede autoasignarse una materia ajena: el backend exige `asignar_docente`
 * y, si quien llama es coordinador, valida que la materia sea suya. Acá el botón
 * se muestra solo a quien administra la estructura.
 */
import { useEffect, useState } from 'react';
import { adminApi } from '../../../lib/apiAdmin';
import { Button, Icon } from '../../../ui/components';
import { ChipMultiSelect } from '../../../ui/ChipMultiSelect';
import { ModalOverlay } from '../../../ui/ModalOverlay';

type Candidato = { id: string; nombre: string; legajo: string };
export type ResponsableInfo = { id: string; nombre: string };

export type RolResponsable = 'coordinador' | 'profesor';

interface ConfigRol {
  /** Rol por el que se filtran los candidatos (mismo valor que usa el backend). */
  rolBackend: RolResponsable;
  tituloDialogo: string;
  etiquetaAgregar: string;
  sinAsignados: string;
  sinDisponibles: string;
  errorCargar: string;
  errorAgregar: string;
  errorQuitar: string;
  /** Explicación del alcance real del rol, en lenguaje llano. */
  ayuda: string;
  agregar: (materiaId: string, usuarioId: string) => Promise<ResponsableInfo[]>;
  quitar: (materiaId: string, usuarioId: string) => Promise<ResponsableInfo[]>;
}

const CONFIG_ROL: Record<RolResponsable, ConfigRol> = {
  coordinador: {
    rolBackend: 'coordinador',
    tituloDialogo: 'Coordinadores a cargo',
    etiquetaAgregar: 'Agregar coordinador',
    sinAsignados: 'Sin coordinadores asignados todavía.',
    sinDisponibles: 'No hay más coordinadores disponibles',
    errorCargar: 'No se pudo cargar la lista de coordinadores.',
    errorAgregar: 'No se pudo agregar el coordinador.',
    errorQuitar: 'No se pudo quitar el coordinador.',
    ayuda:
      'El coordinador ve y revisa únicamente las materias que tiene asignadas, y ' +
      'es el único que puede anular una nota por fraude. Sin ninguna materia ' +
      'asignada, entra al sistema y no ve contenido.',
    agregar: async (materiaId, usuarioId) =>
      (await adminApi.agregarCoordinadorMateria(materiaId, usuarioId)).coordinadores,
    quitar: async (materiaId, usuarioId) =>
      (await adminApi.quitarCoordinadorMateria(materiaId, usuarioId)).coordinadores,
  },
  profesor: {
    rolBackend: 'profesor',
    tituloDialogo: 'Profesores a cargo',
    etiquetaAgregar: 'Agregar profesor',
    sinAsignados: 'Sin profesores asignados todavía.',
    sinDisponibles: 'No hay más profesores disponibles',
    errorCargar: 'No se pudo cargar la lista de profesores.',
    errorAgregar: 'No se pudo agregar el profesor.',
    errorQuitar: 'No se pudo quitar el profesor.',
    ayuda:
      'El profesor arma los exámenes y el banco de preguntas de las materias que ' +
      'tiene asignadas, y supervisa en vivo. NO decide si hubo fraude: esa ' +
      'decisión es del coordinador. Sin materias asignadas no ve contenido.',
    agregar: async (materiaId, usuarioId) =>
      (await adminApi.agregarProfesorMateria(materiaId, usuarioId)).profesores,
    quitar: async (materiaId, usuarioId) =>
      (await adminApi.quitarProfesorMateria(materiaId, usuarioId)).profesores,
  },
};

export function AsignarResponsableDialog({
  rol,
  materiaId,
  materiaNombre,
  actuales,
  onCerrar,
  onCambiado,
}: {
  rol: RolResponsable;
  materiaId: string;
  materiaNombre: string;
  actuales: ResponsableInfo[];
  onCerrar: () => void;
  onCambiado: (responsables: ResponsableInfo[]) => void;
}) {
  const cfg = CONFIG_ROL[rol];

  const [candidatos, setCandidatos] = useState<Candidato[]>([]);
  const [asignados, setAsignados] = useState<ResponsableInfo[]>(actuales);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    adminApi
      // OJO con la firma: es (limit, offset, filtros). Invertirlos pide 1 resultado
      // salteando los primeros 200, y el selector queda vacío sin ningún error.
      .listarUsuarios(200, 0, { rol: cfg.rolBackend, estado: 'activo' })
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
      .catch(() => vivo && setError(cfg.errorCargar))
      .finally(() => vivo && setCargando(false));
    return () => {
      vivo = false;
    };
  }, [cfg]);

  const disponibles = candidatos.filter((c) => !asignados.some((x) => x.id === c.id));

  async function agregar(usuarioId: string) {
    setGuardando(true);
    setError(null);
    try {
      const lista = await cfg.agregar(materiaId, usuarioId);
      setAsignados(lista);
      onCambiado(lista);
    } catch (err) {
      const e = err as { mensaje?: string };
      setError(e.mensaje ?? cfg.errorAgregar);
    } finally {
      setGuardando(false);
    }
  }

  async function quitar(usuarioId: string) {
    setGuardando(true);
    setError(null);
    try {
      const lista = await cfg.quitar(materiaId, usuarioId);
      setAsignados(lista);
      onCambiado(lista);
    } catch (err) {
      const e = err as { mensaje?: string };
      setError(e.mensaje ?? cfg.errorQuitar);
    } finally {
      setGuardando(false);
    }
  }

  const selectId = `responsable-sel-${rol}`;

  return (
    <ModalOverlay
      etiqueta={`${cfg.tituloDialogo} de ${materiaNombre}`}
      onCerrar={guardando ? undefined : onCerrar}
    >
      <div className="card w-full max-w-md p-lg">
        <h2 className="text-title-sm font-semibold text-on-surface">
          {cfg.tituloDialogo}
        </h2>
        <p className="text-label-sm text-on-surface-variant mt-0.5 mb-md">
          {materiaNombre}
        </p>

        {cargando ? (
          <div className="h-[80px] animate-pulse bg-surface-container-low rounded-md" />
        ) : (
          <>
            {asignados.length === 0 && (
              <p className="text-label-sm text-on-surface-variant mb-md">
                {cfg.sinAsignados}
              </p>
            )}

            <label className="text-label-sm text-on-surface-variant" htmlFor={selectId}>
              {cfg.etiquetaAgregar}
            </label>
            <div className="mt-1">
              <ChipMultiSelect
                id={selectId}
                className="input w-full"
                disabled={guardando || disponibles.length === 0}
                seleccionados={asignados.map((c) => ({ id: c.id, textoOpcion: c.nombre }))}
                disponibles={disponibles.map((c) => ({
                  id: c.id,
                  textoOpcion: c.legajo ? `${c.nombre} · ${c.legajo}` : c.nombre,
                  textoChip: c.nombre,
                }))}
                onAgregar={agregar}
                onQuitar={quitar}
                textoOpcionVacia={disponibles.length === 0 ? cfg.sinDisponibles : 'Elegir…'}
              />
            </div>
            <p className="text-label-sm text-on-surface-variant mt-1.5">{cfg.ayuda}</p>
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
    </ModalOverlay>
  );
}
