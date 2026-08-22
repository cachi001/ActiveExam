/**
 * TDD: RED → GREEN
 *
 * Guardia contra la familia de bugs del token vencido (22/8/2026).
 *
 * El access token vive 15 minutos. Cualquier módulo que arme el header
 * `Authorization` a mano y llame a `fetch` crudo NO se recupera cuando vence:
 * el request sale sin credencial y el backend responde 401 "Falta el Bearer
 * token.". Le pasó al guardado del destino de la nota y a la pantalla de
 * materias y comisiones, que además mostraba "No hay materias registradas"
 * como si los datos no existieran.
 *
 * Este test escanea el código fuente y falla si aparece un módulo nuevo con el
 * patrón viejo. No prueba comportamiento: prueba que no volvamos a introducir
 * la deuda. El comportamiento está cubierto en `examContentAdmin.auth.test.ts`.
 */

import { describe, expect, it } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const RAIZ = join(__dirname, '..');

// Únicos módulos autorizados a llamar `fetch` con un Bearer propio:
// - `fetchAutenticado`: ES el wrapper (llamar fetch es su trabajo).
// - `apiCore`: `realFetch` ya implementa 401 → refresh → reintento.
// - `auth/adapters/jwt`: hace login y refresh; envolverlo sería recursión, y un
//   401 ahí significa "credencial incorrecta", no "token vencido".
const EXENTOS = [
  'lib/fetchAutenticado.ts',
  'lib/apiCore.ts',
  'lib/auth/adapters/jwt.ts',
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

function esExento(ruta: string): boolean {
  const normalizada = ruta.replace(/\\/g, '/');
  return EXENTOS.some((e) => normalizada.endsWith(e));
}

describe('ningún módulo llama fetch crudo con un Bearer armado a mano', () => {
  it('todo request autenticado pasa por fetchAutenticado o realFetch', () => {
    const infractores: string[] = [];

    for (const ruta of archivosFuente(RAIZ)) {
      if (esExento(ruta)) continue;
      const fuente = readFileSync(ruta, 'utf8');
      // Solo interesa el que arma la credencial a mano.
      if (!/Authorization:\s*(`Bearer|\{)/.test(fuente) && !/Bearer \$\{/.test(fuente)) {
        continue;
      }
      // `fetch(` que NO sea `fetchAutenticado(` ni `realFetch(`.
      const crudo = /(?<![A-Za-z])fetch\(/.test(fuente);
      if (crudo) infractores.push(ruta.replace(/\\/g, '/').split('/src/')[1]);
    }

    expect(infractores).toEqual([]);
  });
});
