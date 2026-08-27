/**
 * Guardia contra volver a escribir a mano los estados de la nota (26/8/2026).
 *
 * Las etiquetas de `estado_moodle` estaban duplicadas en el frontend: el badge
 * de la tabla tenía las suyas y el desplegable del filtro las suyas. Cuando
 * c-78 D14 agregó 'manual' ("cargada a mano en el campus"), el badge lo aprendió
 * y el filtro no: el estado se veía en pantalla pero no se podía filtrar, así que
 * quien marcaba notas a mano no tenía después cómo listarlas.
 *
 * La fuente es el backend (`GET /exam-content/estados-moodle`), que el front
 * consume vía `lib/estadosMoodle.ts`. Este test escanea el código y falla si
 * aparece otro módulo con las etiquetas escritas de nuevo. No prueba
 * comportamiento: prueba que no volvamos a partir la fuente en dos.
 *
 * Mismo patrón que `sinFetchAutenticado.test.ts` y `ui/capas.test.ts`.
 */

import { describe, expect, it } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const RAIZ = join(__dirname, '..');

// Único módulo autorizado a nombrar las etiquetas: ES el respaldo de la API.
const EXENTOS = ['lib/estadosMoodle.ts'];

// Etiquetas que solo pueden salir del backend. Si aparecen escritas en otro
// lado, alguien volvió a armar la lista a mano.
const ETIQUETAS_DEL_BACKEND = [
  'Pendiente de sincronizar',
  'Sincronizado en Moodle',
  'Cargada a mano',
];

function archivosFuente(dir: string): string[] {
  const salida: string[] = [];
  for (const entrada of readdirSync(dir)) {
    const ruta = join(dir, entrada);
    if (statSync(ruta).isDirectory()) {
      salida.push(...archivosFuente(ruta));
      continue;
    }
    if (!/\.(ts|tsx)$/.test(entrada) || /\.test\.tsx?$/.test(entrada)) continue;
    salida.push(ruta);
  }
  return salida;
}

function rutaRelativa(ruta: string): string {
  return ruta.slice(RAIZ.length + 1).replace(/\\/g, '/');
}

/** Quita comentarios: nombrar una etiqueta al EXPLICAR el bug no es repetirla. */
function sinComentarios(codigo: string): string {
  return codigo.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
}

describe('los estados de la nota vienen del backend, no del frontend', () => {
  it('ningún módulo repite las etiquetas de estado_moodle', () => {
    const infractores: string[] = [];

    for (const ruta of archivosFuente(RAIZ)) {
      const relativa = rutaRelativa(ruta);
      if (EXENTOS.includes(relativa)) continue;
      const codigo = sinComentarios(readFileSync(ruta, 'utf8'));
      const repetidas = ETIQUETAS_DEL_BACKEND.filter((e) => codigo.includes(e));
      if (repetidas.length > 0) {
        infractores.push(`${relativa} → ${repetidas.join(', ')}`);
      }
    }

    expect(
      infractores,
      'Estas etiquetas las define el backend. Consumilas con useEstadosMoodle() ' +
        'en vez de escribirlas:\n' +
        infractores.join('\n'),
    ).toEqual([]);
  });

  it('el respaldo local cubre los cinco estados que hoy existen', async () => {
    const { FALLBACK_ESTADOS } = await import('./estadosMoodle');
    expect(FALLBACK_ESTADOS.map((e) => e.valor).sort()).toEqual(
      ['enviado', 'fallido', 'manual', 'pendiente', 'sin_token'].sort(),
    );
  });
});
