/**
 * Cómo se arma el sorteo de un examen a partir del banco (27/8/2026).
 *
 * Tres cosas estaban mal y son la razón de este módulo:
 *
 * 1. El modal contaba solo las preguntas DIRECTAS de cada categoría, pero el
 *    backend sortea con `incluir_subcategorias` en true, o sea sobre la rama
 *    entera. Los números que veía el docente no eran los del sorteo real.
 *
 * 2. Una categoría padre cuyas preguntas viven en sus hijas contaba cero y ni
 *    siquiera se listaba. Justo esa es la forma de sortear sobre varias
 *    categorías a la vez (el equivalente al "incluir subcategorías" de Moodle),
 *    y era inalcanzable desde la UI.
 *
 * 3. La repetición entre alumnos se estimaba con un promedio global
 *    (total² / pool). Ese promedio TAPA el caso que importa: pedir 1 de una
 *    categoría que tiene 1 le da esa pregunta a todos, y el promedio lo diluía
 *    contra el resto. Con 4 de 30 + 1 de 1 + 1 de 1 mostraba "Buena variedad"
 *    cuando 2 de las 6 preguntas son idénticas para todo el curso.
 *
 * La cuenta correcta es por tramo y se suma: para k sorteadas de n, dos alumnos
 * comparten k²/n en promedio. Con k = n da n, que es justamente "se la llevan
 * todos" — el caso fijo sale solo, sin tratarlo aparte.
 */
import { describe, expect, it } from 'vitest';
import {
  construirTramos,
  disponiblesDelTramo,
  estadoDeInclusion,
  estimarRepeticion,
  poolDelExamen,
  preguntasVisibles,
} from './tramosDelBanco';
import type { CategoriaPregunta, PreguntaBanco } from '../../lib/apiAdmin/bancoPreguntasApi';

function cat(id: string, nombre: string, padre: string | null = null): CategoriaPregunta {
  return {
    id,
    nombre,
    materia_id: 'mat-1',
    categoria_padre_id: padre,
    creada_en: '2026-01-01T00:00:00Z',
  };
}

function preg(id: string, categoriaId: string | null, tipo = 'cloze'): PreguntaBanco {
  return {
    id,
    enunciado: `Enunciado ${id}`,
    tipo,
    orden: 0,
    seleccionada: true,
    categoria_id: categoriaId,
    categoria_manual: false,
  };
}

// Unidad 1 no tiene preguntas propias: las tiene su hija Bloque A. Es la forma
// natural de organizar un banco y la que rompía el conteo viejo.
const CATEGORIAS = [
  cat('u1', 'Unidad 1'),
  cat('bloque-a', 'Bloque A', 'u1'),
  cat('u2', 'Unidad 2'),
];

const PREGUNTAS = [
  preg('p1', 'bloque-a'),
  preg('p2', 'bloque-a'),
  preg('p3', 'u2'),
  preg('p4', null), // sin clasificar
];

describe('construirTramos', () => {
  it('lista la categoría padre aunque no tenga preguntas propias', () => {
    const tramos = construirTramos(CATEGORIAS, PREGUNTAS);
    const u1 = tramos.find((t) => t.categoria_id === 'u1');
    expect(u1, 'Unidad 1 tiene que aparecer: es la manera de sortear sobre toda su rama').toBeDefined();
  });

  it('cuenta la rama entera en el padre y solo las propias como directas', () => {
    const tramos = construirTramos(CATEGORIAS, PREGUNTAS);
    const u1 = tramos.find((t) => t.categoria_id === 'u1')!;
    expect(u1.disponibles_rama).toBe(2); // p1 y p2, que están en la hija
    expect(u1.disponibles_directas).toBe(0);
  });

  it('en una categoría sin hijas la rama y las directas coinciden', () => {
    const tramos = construirTramos(CATEGORIAS, PREGUNTAS);
    const u2 = tramos.find((t) => t.categoria_id === 'u2')!;
    expect(u2.disponibles_rama).toBe(1);
    expect(u2.disponibles_directas).toBe(1);
  });

  it('un tramo aporta solo sus preguntas propias, no las de sus hijas', () => {
    // Antes se podía pedirle a la madre su rama entera, y como las hijas se
    // eligen aparte en la misma lista, la misma pregunta entraba dos veces.
    const tramos = construirTramos(CATEGORIAS, PREGUNTAS);
    const u1 = tramos.find((t) => t.categoria_id === 'u1')!;
    const bloqueA = tramos.find((t) => t.categoria_id === 'bloque-a')!;
    expect(disponiblesDelTramo(u1)).toBe(0);
    expect(disponiblesDelTramo(bloqueA)).toBe(2);
  });

  it('sumar las directas de todos los tramos cuenta cada pregunta una sola vez', () => {
    // Es el total que se le muestra al docente cuando pide N contra el banco:
    // si sumara ramas, "de las N que hay" mentiría contando repetido.
    const tramos = construirTramos(CATEGORIAS, PREGUNTAS);
    const total = tramos.reduce((s, t) => s + t.disponibles_directas, 0);
    expect(total).toBe(PREGUNTAS.length);
  });

  it('incluye las preguntas sin clasificar como su propio tramo', () => {
    const tramos = construirTramos(CATEGORIAS, PREGUNTAS);
    const sinCat = tramos.find((t) => t.categoria_id === null)!;
    expect(sinCat.disponibles_rama).toBe(1);
  });

  it('una categoría con tipos mezclados es UNA fila, no una por tipo', () => {
    // Partir por tipo mostraba "Unidad 2 / Cloze" y "Unidad 2 / Opción múltiple"
    // como si fueran dos categorías, y el árbol dejaba de parecerse al banco.
    const mixtas = [preg('p1', 'u2', 'cloze'), preg('p2', 'u2', 'multichoice')];
    const tramos = construirTramos([cat('u2', 'Unidad 2')], mixtas);
    expect(tramos).toHaveLength(1);
    expect(tramos[0].disponibles_directas).toBe(2);
  });

  it('lleva el desglose por tipo, para decir de qué está hecha la categoría', () => {
    const mixtas = [
      preg('p1', 'u2', 'cloze'),
      preg('p2', 'u2', 'multichoice'),
      preg('p3', 'u2', 'multichoice'),
    ];
    const tramos = construirTramos([cat('u2', 'Unidad 2')], mixtas);
    expect(tramos[0].por_tipo).toEqual({ cloze: 1, multichoice: 2 });
  });

  it('deja fuera las categorías dadas de baja', () => {
    const conBaja = [...CATEGORIAS, { ...cat('vieja', 'Vieja'), eliminada_en: '2026-08-01T00:00:00Z' }];
    const tramos = construirTramos(conBaja, PREGUNTAS);
    expect(tramos.some((t) => t.categoria_id === 'vieja')).toBe(false);
  });

  it('la profundidad ubica a la hija debajo del padre para poder indentarla', () => {
    const tramos = construirTramos(CATEGORIAS, PREGUNTAS);
    expect(tramos.find((t) => t.categoria_id === 'u1')!.profundidad).toBe(0);
    expect(tramos.find((t) => t.categoria_id === 'bloque-a')!.profundidad).toBe(1);
  });
});

describe('estimarRepeticion', () => {
  it('marca como fijo el tramo que se lleva todas las disponibles', () => {
    // Pedir 1 de 1 no es un sorteo: esa pregunta le toca a todo el curso.
    const r = estimarRepeticion([{ cantidad: 1, disponibles: 1 }]);
    expect(r.fijas).toBe(1);
    expect(r.sorteadas).toBe(0);
  });

  it('no cuenta como fijo el tramo que deja preguntas afuera', () => {
    const r = estimarRepeticion([{ cantidad: 4, disponibles: 30 }]);
    expect(r.fijas).toBe(0);
    expect(r.sorteadas).toBe(4);
  });

  it('el caso del dueño: 4 de 30 + 1 de 1 + 1 de 1 comparte mucho más que el promedio global', () => {
    const r = estimarRepeticion([
      { cantidad: 4, disponibles: 30 },
      { cantidad: 1, disponibles: 1 },
      { cantidad: 1, disponibles: 1 },
    ]);
    expect(r.total).toBe(6);
    expect(r.fijas).toBe(2);
    // Por tramo: 16/30 + 1 + 1 = 2,53. El promedio global daba 6²/32 = 1,1 y
    // rotulaba "Buena variedad" con dos preguntas iguales para todos.
    expect(r.compartidas).toBeCloseTo(2.53, 1);
    expect(r.compartidas).toBeGreaterThan((6 * 6) / 32);
  });

  it('con un banco holgado la repetición es baja', () => {
    const r = estimarRepeticion([{ cantidad: 10, disponibles: 200 }]);
    expect(r.compartidas).toBeCloseTo(0.5, 1);
    expect(r.fijas).toBe(0);
  });

  it('ignora los tramos en cero: no forman parte del examen', () => {
    const r = estimarRepeticion([
      { cantidad: 0, disponibles: 50 },
      { cantidad: 5, disponibles: 50 },
    ]);
    expect(r.total).toBe(5);
  });
});

describe('poolDelExamen', () => {
  it('sin nada destildado, el pool es el banco entero', () => {
    const pool = poolDelExamen(PREGUNTAS, new Set());
    expect(pool).toHaveLength(4);
  });

  it('una pregunta destildada no puede tocarle a nadie', () => {
    const pool = poolDelExamen(PREGUNTAS, new Set(['p1']));
    expect(pool.map((p) => p.id)).not.toContain('p1');
    expect(pool).toHaveLength(3);
  });
});

describe('estadoDeInclusion', () => {
  // El tilde de una categoría tiene tres estados y el del medio es el que
  // importa: si se dibuja como "incluida" a secas, el docente no ve que sacó
  // preguntas de ahí y arma el examen creyendo que entran todas.
  it('marca "todas" cuando no hay ninguna destildada', () => {
    expect(estadoDeInclusion(['p1', 'p2'], new Set())).toBe('todas');
  });

  it('marca "ninguna" cuando están todas destildadas', () => {
    expect(estadoDeInclusion(['p1', 'p2'], new Set(['p1', 'p2']))).toBe('ninguna');
  });

  it('marca "algunas" cuando quedó una sí y otra no', () => {
    expect(estadoDeInclusion(['p1', 'p2'], new Set(['p1']))).toBe('algunas');
  });

  it('una categoría sin preguntas propias no dice "todas incluidas"', () => {
    // Es la categoría que solo agrupa: dibujarle un tilde lleno haría creer
    // que aporta algo al examen.
    expect(estadoDeInclusion([], new Set())).toBe('ninguna');
  });
});

describe('preguntasVisibles', () => {
  // El chip de tipo no es solo cosmético: si el docente filtra "Cloze" y crea,
  // el examen no puede sortear una multichoice que no llegó a ver.
  it('sin filtro devuelve el banco entero', () => {
    expect(preguntasVisibles(PREGUNTAS, null)).toHaveLength(4);
  });

  it('con filtro deja solo las de ese tipo', () => {
    const mixtas = [preg('p1', 'u2', 'cloze'), preg('p2', 'u2', 'multichoice')];
    const soloCloze = preguntasVisibles(mixtas, 'cloze');
    expect(soloCloze.map((p) => p.id)).toEqual(['p1']);
  });
});
