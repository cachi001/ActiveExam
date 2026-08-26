/**
 * Repara `localStorage` en los tests con DOM (c-78).
 *
 * ## El problema, medido
 *
 * Node 22+ define su PROPIO `localStorage` en `globalThis`, como getter
 * experimental que devuelve `undefined` si no se arrancó con
 * `--localstorage-file`. Ese getter **pisa** al que instala jsdom, así que en un
 * test con `@vitest-environment jsdom` queda `typeof window === 'object'` pero
 * `localStorage === undefined` — y `window.localStorage` también.
 *
 * Se veía como 4 tests rojos en `useUiPrefs.test.ts` (`Cannot read properties of
 * undefined (reading 'clear')`), diagnosticados antes como "jsdom 25 no expone
 * localStorage bajo Node 26" y dados por ajenos al proyecto. No son ajenos: es
 * una colisión de globals que se arregla acá, sin tocar la versión de Node ni la
 * de jsdom.
 *
 * ## Qué hace
 *
 * Instala un `Storage` en memoria, conforme al contrato del DOM, SOLO cuando hay
 * `window` (entorno jsdom) y no hay un `localStorage` usable. Los tests que
 * corren en entorno `node` quedan intactos a propósito: ahí `localStorage` NO
 * existe en el navegador real tampoco, y el código de producción que pregunta
 * `typeof localStorage !== 'undefined'` tiene que seguir viendo lo mismo.
 */

class AlmacenamientoEnMemoria implements Storage {
  private datos = new Map<string, string>();

  get length(): number {
    return this.datos.size;
  }

  clear(): void {
    this.datos.clear();
  }

  getItem(clave: string): string | null {
    return this.datos.get(String(clave)) ?? null;
  }

  key(indice: number): string | null {
    return [...this.datos.keys()][indice] ?? null;
  }

  removeItem(clave: string): void {
    this.datos.delete(String(clave));
  }

  setItem(clave: string, valor: string): void {
    this.datos.set(String(clave), String(valor));
  }
}

/** ¿El `localStorage` actual sirve para algo? El de Node devuelve undefined. */
function almacenamientoUsable(candidato: unknown): candidato is Storage {
  return (
    typeof candidato === 'object' &&
    candidato !== null &&
    typeof (candidato as Storage).getItem === 'function'
  );
}

function instalar(destino: object, nombre: 'localStorage' | 'sessionStorage'): void {
  const actual = (destino as Record<string, unknown>)[nombre];
  if (almacenamientoUsable(actual)) return;
  Object.defineProperty(destino, nombre, {
    value: new AlmacenamientoEnMemoria(),
    configurable: true,
    writable: true,
  });
}

// Solo en entorno con DOM: en `node` se deja tal cual estaba.
if (typeof window !== 'undefined') {
  for (const nombre of ['localStorage', 'sessionStorage'] as const) {
    instalar(globalThis, nombre);
    instalar(window, nombre);
  }
}
