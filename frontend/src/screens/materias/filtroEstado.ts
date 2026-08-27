/**
 * Filtro de baja lógica para materias y comisiones.
 *
 * Las dos se dan de baja de forma LÓGICA (`activa = false`): no se borra nada y
 * se pueden reactivar. Pero la pantalla no tenía cómo filtrarlas: las inactivas
 * aparecían mezcladas con las vigentes, con un cartel, y no había manera de
 * aislarlas ni de esconderlas. Con varias materias dadas de baja, encontrar la
 * que se quiere reactivar era leer la lista entera.
 *
 * Mismo vocabulario que el filtro del catálogo de exámenes, que ya lo tenía
 * ('activo' | 'inactivo' | 'todos'), para que las dos pantallas se operen igual.
 */

export type EstadoBajaFiltro = 'activa' | 'inactiva' | 'todas';

/** Lo mínimo que necesita el filtro. `activa` ausente = vigente (respuestas viejas). */
export interface ConEstadoActiva {
  activa?: boolean;
}

export const OPCIONES_ESTADO_BAJA: { valor: EstadoBajaFiltro; label: string }[] = [
  { valor: 'activa', label: 'Activas' },
  { valor: 'inactiva', label: 'Dadas de baja' },
  { valor: 'todas', label: 'Todas' },
];

/** true si está dada de baja. `undefined` cuenta como vigente, no como baja. */
export function estaDeBaja(x: ConEstadoActiva): boolean {
  return x.activa === false;
}

/**
 * Filtra por estado de baja. El default de la pantalla es 'activa': quien entra
 * a gestionar materias quiere ver las vigentes, no el historial.
 */
export function filtrarPorEstado<T extends ConEstadoActiva>(
  items: T[],
  estado: EstadoBajaFiltro,
): T[] {
  if (estado === 'todas') return items;
  if (estado === 'inactiva') return items.filter(estaDeBaja);
  return items.filter((x) => !estaDeBaja(x));
}

/** Cuántas hay dadas de baja, para poder avisar que existen sin mostrarlas. */
export function contarDeBaja(items: ConEstadoActiva[]): number {
  return items.filter(estaDeBaja).length;
}
