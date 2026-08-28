/**
 * Cómo se arma el sorteo de un examen a partir del banco de preguntas.
 *
 * El modelo es el de Moodle: cada tramo pide N preguntas aleatorias de UNA
 * categoría, con la opción de incluir sus subcategorías. Elegir una categoría
 * padre con esa opción prendida es la forma de sortear sobre varias categorías a
 * la vez, y el pool es la rama entera.
 *
 * Todo esto vive acá y no dentro del modal porque es la parte que decide si el
 * examen sortea de verdad, y eso merece tests propios. Ver `tramosDelBanco.test.ts`
 * para los tres bugs que originaron el módulo.
 */
import type { CategoriaPregunta, PreguntaBanco } from '../../lib/apiAdmin/bancoPreguntasApi';

export interface TramoSorteo {
  /** null = las preguntas sin clasificar. */
  categoria_id: string | null;
  categoria_nombre: string;
  /** Cuántas de cada tipo tiene la categoría, para decir de qué está hecha. */
  por_tipo: Record<string, number>;
  /** Preguntas en la categoría Y toda su descendencia. */
  disponibles_rama: number;
  /** Preguntas SOLO en esta categoría. */
  disponibles_directas: number;
  cantidad: number;
  /** Cuántos niveles cuelga del raíz, para indentar el árbol. */
  profundidad: number;
}

/**
 * Las que puede aportar el tramo: SOLO las propias de la categoría.
 *
 * Antes había un tilde para sortear también de las subcategorías, y era una
 * trampa: las hijas se eligen aparte en la misma lista, así que pedirle a la
 * madre su rama entera hacía que la misma pregunta pudiera entrar dos veces.
 */
export function disponiblesDelTramo(t: TramoSorteo): number {
  return t.disponibles_directas;
}

/** ids de una categoría y toda su descendencia. */
function rama(categoriaId: string, hijasDe: Map<string | null, CategoriaPregunta[]>): string[] {
  const ids: string[] = [];
  const pendientes = [categoriaId];
  while (pendientes.length > 0) {
    const actual = pendientes.pop()!;
    ids.push(actual);
    for (const h of hijasDe.get(actual) ?? []) pendientes.push(h.id);
  }
  return ids;
}

/**
 * Un tramo por cada categoría que tenga preguntas en su RAMA.
 *
 * Se recorren las ramas y no las preguntas directas a propósito: una categoría
 * padre cuyas preguntas viven en sus hijas tiene que aparecer igual, porque
 * sortear desde ahí es lo que da un pool grande. Contándola por sus preguntas
 * propias daba cero y desaparecía de la lista.
 *
 * Las categorías dadas de baja quedan fuera: el backend tampoco sortea sus
 * preguntas.
 */
export function construirTramos(
  categorias: CategoriaPregunta[],
  preguntas: PreguntaBanco[],
): TramoSorteo[] {
  const vigentes = categorias.filter((c) => !c.eliminada_en);

  const hijasDe = new Map<string | null, CategoriaPregunta[]>();
  for (const c of vigentes) {
    const lista = hijasDe.get(c.categoria_padre_id) ?? [];
    lista.push(c);
    hijasDe.set(c.categoria_padre_id, lista);
  }

  // Preguntas por categoría y tipo, para contar sin recorrer todo cada vez.
  const porCategoria = new Map<string | null, PreguntaBanco[]>();
  for (const p of preguntas) {
    const lista = porCategoria.get(p.categoria_id) ?? [];
    lista.push(p);
    porCategoria.set(p.categoria_id, lista);
  }

  const contarPorTipo = (ids: (string | null)[]): Map<string, number> => {
    const conteos = new Map<string, number>();
    for (const id of ids) {
      for (const p of porCategoria.get(id) ?? []) {
        conteos.set(p.tipo, (conteos.get(p.tipo) ?? 0) + 1);
      }
    }
    return conteos;
  };

  const total = (conteos: Map<string, number>): number =>
    [...conteos.values()].reduce((s, n) => s + n, 0);

  const tramos: TramoSorteo[] = [];

  // Sin clasificar primero: no cuelga de ninguna rama y es fácil de olvidar.
  const sinClasificar = contarPorTipo([null]);
  if (sinClasificar.size > 0) {
    tramos.push({
      categoria_id: null,
      categoria_nombre: 'Sin clasificar',
      por_tipo: Object.fromEntries(sinClasificar),
      disponibles_rama: total(sinClasificar),
      disponibles_directas: total(sinClasificar),
      cantidad: 0,
      profundidad: 0,
    });
  }

  // El árbol en orden de lectura: cada categoría seguida de su descendencia, para
  // que indentar alcance para entender de quién cuelga cada una.
  const enOrden = (padre: string | null, profundidad: number): void => {
    for (const c of hijasDe.get(padre) ?? []) {
      const enRama = contarPorTipo(rama(c.id, hijasDe));
      const directas = contarPorTipo([c.id]);
      if (enRama.size > 0) {
        tramos.push({
          categoria_id: c.id,
          categoria_nombre: c.nombre,
          por_tipo: Object.fromEntries(directas),
          disponibles_rama: total(enRama),
          disponibles_directas: total(directas),
          cantidad: 0,
          profundidad,
        });
      }
      enOrden(c.id, profundidad + 1);
    }
  };
  enOrden(null, 0);

  return tramos;
}

/**
 * Las preguntas que el docente está mirando: el banco, o solo un tipo.
 *
 * El chip de tipo no es cosmético. Si filtra "Cloze" y crea el examen, el pool
 * tiene que ser el que vio: sortear una multichoice que nunca estuvo en pantalla
 * es una sorpresa el día del examen.
 */
export function preguntasVisibles(
  preguntas: PreguntaBanco[],
  tipo: string | null,
): PreguntaBanco[] {
  return tipo === null ? preguntas : preguntas.filter((p) => p.tipo === tipo);
}

export interface ResumenRepeticion {
  /** Preguntas que rinde cada alumno. */
  total: number;
  /** Las que salen de un sorteo con preguntas de sobra. */
  sorteadas: number;
  /** Las que se lleva todo el curso porque el tramo agota su categoría. */
  fijas: number;
  /** Cuántas comparten dos alumnos cualesquiera, en promedio. */
  compartidas: number;
}

/**
 * Cuánto se parecen entre sí dos exámenes sorteados.
 *
 * Para k preguntas sorteadas de n, dos alumnos comparten k²/n en promedio, y eso
 * se SUMA por tramo. La cuenta vieja hacía total²/pool sobre todo junto, que es
 * otra cosa: diluía los tramos flacos contra los grandes y por eso llamaba
 * "buena variedad" a un examen con dos preguntas iguales para todos.
 *
 * Con k = n la fórmula da n, o sea el tramo entero compartido. El caso fijo sale
 * de la misma cuenta, no hace falta tratarlo aparte.
 */
export function estimarRepeticion(
  tramos: { cantidad: number; disponibles: number }[],
): ResumenRepeticion {
  const activos = tramos.filter((t) => t.cantidad > 0 && t.disponibles > 0);
  let total = 0;
  let fijas = 0;
  let compartidas = 0;
  for (const t of activos) {
    total += t.cantidad;
    compartidas += (t.cantidad * t.cantidad) / t.disponibles;
    if (t.cantidad >= t.disponibles) fijas += t.cantidad;
  }
  return { total, sorteadas: total - fijas, fijas, compartidas };
}


/** Las preguntas que se copian al examen: el banco menos las destildadas. */
export function poolDelExamen(
  preguntas: PreguntaBanco[],
  excluidas: Set<string>,
): PreguntaBanco[] {
  return preguntas.filter((p) => !excluidas.has(p.id));
}

/** Si un grupo de preguntas entra entero, a medias o nada. */
export type EstadoInclusion = 'todas' | 'algunas' | 'ninguna';

/**
 * En qué estado va el tilde de una categoría.
 *
 * El grupo vacío cuenta como 'ninguna': una categoría que solo agrupa a sus
 * hijas no aporta preguntas, y dibujarle el tilde lleno haría creer que sí.
 */
export function estadoDeInclusion(
  idsDelGrupo: string[],
  excluidas: Set<string>,
): EstadoInclusion {
  if (idsDelGrupo.length === 0) return 'ninguna';
  const fuera = idsDelGrupo.filter((id) => excluidas.has(id)).length;
  if (fuera === 0) return 'todas';
  if (fuera === idsDelGrupo.length) return 'ninguna';
  return 'algunas';
}
