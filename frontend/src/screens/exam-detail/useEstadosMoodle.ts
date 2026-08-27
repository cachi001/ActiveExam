/**
 * Hook que expone los estados de la nota que define el BACKEND.
 *
 * Arranca con el respaldo local para que la pantalla pinte sin esperar la
 * respuesta, y lo reemplaza apenas llega la lista real. Así ni el filtro ni el
 * badge tienen su propia copia de los estados: hay una sola, y viene del backend.
 */
import { useEffect, useState } from 'react';
import {
  cargarEstadosMoodle,
  FALLBACK_ESTADOS,
  type EstadoMoodleInfo,
} from '../../lib/estadosMoodle';

export function useEstadosMoodle(): EstadoMoodleInfo[] {
  const [estados, setEstados] = useState<EstadoMoodleInfo[]>(FALLBACK_ESTADOS);

  useEffect(() => {
    let vigente = true;
    cargarEstadosMoodle().then((lista) => {
      if (vigente) setEstados(lista);
    });
    return () => {
      vigente = false;
    };
  }, []);

  return estados;
}
