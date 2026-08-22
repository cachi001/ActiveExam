import type { CategoriaPregunta } from '../../lib/apiAdmin/bancoPreguntasApi';

export interface CategoriaPlana {
  id: string;
  nombre: string;
  /** 0 = raíz, 1 = subcategoría de una raíz, etc. */
  profundidad: number;
}

/**
 * Aplana el árbol de categorías (padre → hijos, en orden de aparición) para
 * usarlo en un <select> indentado. Una categoría con `categoria_padre_id`
 * apuntando a un id que no está en la lista se trata como raíz (profundidad 0)
 * — evita que un dato inconsistente la haga desaparecer del selector.
 */
export function aplanarArbolCategorias(categorias: CategoriaPregunta[]): CategoriaPlana[] {
  const idsValidos = new Set(categorias.map((c) => c.id));
  const hijosPorPadre = new Map<string | null, CategoriaPregunta[]>();
  for (const c of categorias) {
    const padre = c.categoria_padre_id && idsValidos.has(c.categoria_padre_id) ? c.categoria_padre_id : null;
    if (!hijosPorPadre.has(padre)) hijosPorPadre.set(padre, []);
    hijosPorPadre.get(padre)!.push(c);
  }

  const resultado: CategoriaPlana[] = [];
  function recorrer(padreId: string | null, profundidad: number): void {
    for (const c of hijosPorPadre.get(padreId) ?? []) {
      resultado.push({ id: c.id, nombre: c.nombre, profundidad });
      recorrer(c.id, profundidad + 1);
    }
  }
  recorrer(null, 0);
  return resultado;
}
