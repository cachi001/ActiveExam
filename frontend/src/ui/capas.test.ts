/**
 * Ningún modal puede quedar por debajo del header o la sidebar.
 *
 * ## El bug
 *
 * Encontrado mirando la pantalla el 26/8/2026: varios diálogos oscurecían el
 * contenido pero **dejaban el header y la sidebar iluminados por encima**. Se veía
 * como si el modal estuviera "detrás" del marco de la aplicación.
 *
 * La causa: el header es `z-50` y la sidebar `z-40`, y esos cuatro modales también
 * usaban `z-50`. Con el mismo z-index gana el que viene después en el DOM, y como
 * no usan portal quedan anidados dentro del contenido — que se pinta antes que el
 * header fijo.
 *
 * ## Por qué un test de arquitectura y no solo cambiar los cuatro números
 *
 * Había **diez** valores distintos de z-index para overlays (30, 40, 50, 60, 90,
 * 95, 100, 110, 200, 1000), elegidos a ojo uno por uno. Con esa dispersión, el
 * próximo modal que alguien escriba vuelve a caer en el mismo pozo. Este test
 * escanea el código y falla si aparece un overlay a la altura del marco o por
 * debajo. No prueba comportamiento: prueba que no volvamos a introducir la deuda.
 *
 * Es el mismo patrón que `sinFetchAutenticado.test.ts`, que ya cuida la familia de
 * bugs del token vencido.
 */
import { describe, expect, it } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { CAPAS } from './capas';

const RAIZ = join(__dirname, '..');

/** Overlays que NO son modales: son parte del marco o quedan por debajo a propósito. */
const EXENTOS = [
  // El propio marco: header (50), sidebar (40) y su backdrop mobile (30).
  'ui/StaffShell.tsx',
  // Menú contextual anclado a un botón: vive dentro de la página, no sobre ella.
  'ui/ActionMenu.tsx',
  // Overlays DENTRO del examen: se apilan entre sí con su propia escala y no
  // conviven con el shell de staff (el alumno rinde sin sidebar ni header).
  'screens/Examen.tsx',
  'screens/PausaAlumno.tsx',
  'ui/biometric/CaptureOverlay.tsx',
  'ui/BiometricCapture.tsx',
  'ui/CameraSnapshotCapture.tsx',
];

function archivosFuente(dir: string): string[] {
  const salida: string[] = [];
  for (const entrada of readdirSync(dir)) {
    const ruta = join(dir, entrada);
    if (statSync(ruta).isDirectory()) {
      salida.push(...archivosFuente(ruta));
      continue;
    }
    if (/\.tsx$/.test(entrada) && !/\.test\.tsx$/.test(entrada)) salida.push(ruta);
  }
  return salida;
}

/** z-index de cada overlay `fixed inset-0` de un archivo. */
function zDeOverlays(contenido: string): number[] {
  const zs: number[] = [];
  for (const linea of contenido.split('\n')) {
    if (!linea.includes('fixed inset-0')) continue;
    const m = linea.match(/z-\[?(\d+)\]?/);
    if (m) zs.push(Number(m[1]));
  }
  return zs;
}

describe('capas de la interfaz', () => {
  it('el header y la sidebar están por debajo de los modales', () => {
    // Si esto se rompe, la escala perdió su sentido: revisar `capas.ts`.
    expect(CAPAS.modal).toBeGreaterThan(CAPAS.header);
    expect(CAPAS.header).toBeGreaterThan(CAPAS.sidebar);
  });

  it('el toast se ve por encima de los modales', () => {
    // Un aviso de "no se pudo guardar" que quede tapado por el diálogo que lo
    // provocó es un aviso que nadie lee.
    expect(CAPAS.toast).toBeGreaterThan(CAPAS.modal);
  });

  it('ningún overlay tapa al toast', () => {
    // El toast estaba en z-120 y los diálogos de asignar responsable y los paneles
    // de ayuda en z-200 y z-1000: un "no se pudo guardar" disparado DESDE esos
    // diálogos quedaba tapado por el diálogo que lo provocó.
    const porEncima: string[] = [];

    for (const ruta of archivosFuente(RAIZ)) {
      const relativa = ruta.slice(RAIZ.length + 1).replace(/\\/g, '/');
      if (relativa === 'ui/toast/ToastProvider.tsx') continue;

      for (const z of zDeOverlays(readFileSync(ruta, 'utf8'))) {
        if (z >= CAPAS.toast) porEncima.push(`${relativa} (z-${z})`);
      }
    }

    expect(porEncima,
      `Estos overlays se dibujan por encima del toast (z-${CAPAS.toast}), así que ` +
      `un aviso disparado desde ellos queda tapado:\n  ${porEncima.join('\n  ')}`,
    ).toEqual([]);
  });

  it('ningún overlay a pantalla completa queda a la altura del marco o debajo', () => {
    const infractores: string[] = [];

    for (const ruta of archivosFuente(RAIZ)) {
      const relativa = ruta.slice(RAIZ.length + 1).replace(/\\/g, '/');
      if (EXENTOS.includes(relativa)) continue;

      for (const z of zDeOverlays(readFileSync(ruta, 'utf8'))) {
        if (z <= CAPAS.header) infractores.push(`${relativa} (z-${z})`);
      }
    }

    expect(infractores,
      `Estos overlays quedan por debajo del header (z-${CAPAS.header}), así que la ` +
      `sidebar y la barra superior se ven POR ENCIMA del diálogo. Usá la escala de ` +
      `\`ui/capas.ts\`:\n  ${infractores.join('\n  ')}`,
    ).toEqual([]);
  });
});
