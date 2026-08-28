/**
 * Hooks de los catálogos que define el BACKEND: resultados y retenciones.
 *
 * Mismo patrón que `useEstadosMoodle`: arranca con el respaldo para que la
 * pantalla pinte sin esperar, y lo reemplaza apenas llega la lista real.
 */
import { useEffect, useState } from 'react';
import {
  cargarDecisiones,
  cargarResultados,
  cargarRetenciones,
  type ItemCatalogo,
} from '../../lib/catalogosNota';

function useCatalogo(cargar: () => Promise<ItemCatalogo[]>): Map<string, ItemCatalogo> {
  const [items, setItems] = useState<ItemCatalogo[]>([]);
  useEffect(() => {
    let vigente = true;
    cargar().then((lista) => {
      if (vigente) setItems(lista);
    });
    return () => {
      vigente = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `cargar` es estable
  }, []);
  return new Map(items.map((i) => [i.valor, i]));
}

export const useResultados = () => useCatalogo(cargarResultados);
export const useRetenciones = () => useCatalogo(cargarRetenciones);
export const useDecisiones = () => useCatalogo(cargarDecisiones);
