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
  tipo: string;
  /** Preguntas de este tipo en la categoría Y toda su descendencia. */
  disponibles_rama: number;
  /** Preguntas de este tipo SOLO en esta categoría. */
  disponibles_directas: number;
  /** Arranca en true, igual que el default del backend. */
  incluir_subcategorias: boolean;
  cantidad: number;
  /** Cuántos niveles cuelga del raíz, para indentar el árbol. */
  profundidad: number;
}

/** Las que realmente entran al sorteo según el tilde de subcategorías. */
export function disponiblesDelTramo(t: TramoSorteo): number {
  return t.incluir_subcategorias ? t.disponibles_rama : t.disponibles_directas;
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
 * Un tramo por cada par (categoría, tipo) que exista en la RAMA de la categoría.
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

  const tramos: TramoSorteo[] = [];

  // Sin clasificar primero: no cuelga de ninguna rama y es fácil de olvidar.
  for (const [tipo, cantidad] of contarPorTipo([null])) {
    tramos.push({
      categoria_id: null,
      categoria_nombre: 'Sin clasificar',
      tipo,
      disponibles_rama: cantidad,
      disponibles_directas: cantidad,
      incluir_subcategorias: true,
      cantidad: 0,
      profundidad: 0,
    });
  }

  // El árbol en orden de lectura: cada categoría seguida de su descendencia, para
  // que indentar alcance para entender de quién cuelga cada una.
  const enOrden = (padre: string | null, profundidad: number): void => {
    for (const c of hijasDe.get(padre) ?? []) {
      const idsDeLaRama = rama(c.id, hijasDe);
      const enRama = contarPorTipo(idsDeLaRama);
      const directas = contarPorTipo([c.id]);
      for (const [tipo, cantidadEnRama] of enRama) {
        tramos.push({
          categoria_id: c.id,
          categoria_nombre: c.nombre,
          tipo,
          disponibles_rama: cantidadEnRama,
          disponibles_directas: directas.get(tipo) ?? 0,
          incluir_subcategorias: true,
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

/**
 * Categorías cuyo pool ya se lo lleva otro tramo de la misma selección.
 *
 * Si se sortea de un padre con subcategorías y además de una de sus hijas, el
 * backend descuenta lo ya sorteado y el segundo tramo puede quedarse sin pool:
 * responde 422 y no se crea nada. Avisarlo antes evita el viaje.
 *
 * Devuelve los `categoria_id` de los tramos que quedan tapados.
 */
export function tramosQueSeSolapan(
  seleccionados: {
    categoria_id: string | null;
    cantidad: number;
    incluir_subcategorias: boolean;
  }[],
  categorias: CategoriaPregunta[],
): string[] {
  const padreDe = new Map<string, string | null>();
  for (const c of categorias) padreDe.set(c.id, c.categoria_padre_id);

  const ancestros = (id: string): string[] => {
    const salida: string[] = [];
    let actual = padreDe.get(id) ?? null;
    while (actual) {
      salida.push(actual);
      actual = padreDe.get(actual) ?? null;
    }
    return salida;
  };

  const activos = seleccionados.filter((t) => t.cantidad > 0 && t.categoria_id);
  // Padres que se llevan su rama entera.
  const conRama = new Set(
    activos.filter((t) => t.incluir_subcategorias).map((t) => t.categoria_id as string),
  );

  const tapados = new Set<string>();
  for (const t of activos) {
    const id = t.categoria_id as string;
    if (ancestros(id).some((a) => conRama.has(a))) tapados.add(id);
  }
  return [...tapados];
}
