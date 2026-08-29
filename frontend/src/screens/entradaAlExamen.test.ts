/**
 * Los pasos previos al examen ocultan la navegación lateral.
 *
 * ## Por qué
 *
 * Entrar a rendir es un wizard de tres pasos: requisitos del equipo →
 * verificación biométrica → sala de espera. Mostraban la sidebar y la bottom-nav,
 * así que el alumno podía irse a «Mis materias» en el medio.
 *
 * No es un agujero de seguridad — verificado con el dueño: al salir, la
 * verificación se pierde y hay que rehacerla. El problema es que **el progreso
 * se descarta en silencio**: el alumno vuelve y tiene que verificar su identidad
 * de nuevo sin que nada le explique por qué. Un menú que borra tu avance sin
 * avisar es peor que un menú que no está.
 *
 * Además contradecía el patrón que el propio proyecto ya fijó: `StudentShell`
 * tiene `ocultarNavegacion` documentada para "los pasos intermedios del
 * enrollment", y el wizard de enrollment (`StudentProfile`) sí la usa.
 *
 * El botón «Volver» SE MANTIENE: `ocultarNavegacion` no toca la barra superior
 * (a diferencia de `locked`, que es el lockdown del examen ya en curso). Queda
 * exactamente una salida, y es explícita.
 *
 * El test lee el FUENTE en vez de montar las tres pantallas: cada una arrastra
 * cámara, store y router, y lo que hay que fijar es una sola línea por archivo.
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const AQUI = path.dirname(fileURLToPath(import.meta.url));

/** Los tres pasos entre "Comenzar examen" y la rendición. */
const PASOS_PREVIOS = ['EquipmentCheck.tsx', 'Biometria.tsx', 'SalaEspera.tsx'];

const fuente = (archivo: string) => readFileSync(path.join(AQUI, archivo), 'utf8');

describe('pasos previos al examen', () => {
  it.each(PASOS_PREVIOS)('%s oculta la navegación lateral', (archivo) => {
    expect(fuente(archivo)).toMatch(/<StudentShell[^>]*ocultarNavegacion/s);
  });

  it.each(PASOS_PREVIOS)('%s conserva una salida visible', (archivo) => {
    // `ocultarNavegacion` deja la barra superior; lo que NO puede pasar es que
    // alguien use `locked`, que la saca y dejaría al alumno sin forma de salir
    // antes de haber empezado a rendir.
    expect(fuente(archivo)).not.toMatch(/<StudentShell[^>]*\blocked\b/s);
  });

  it('el examen en curso SÍ usa el lockdown, que es otra cosa', () => {
    // Contraste deliberado: una vez que arrancó la rendición no hay salida, y
    // eso es correcto. Si esto falla, alguien confundió los dos modos.
    expect(fuente('Examen.tsx')).toMatch(/locked/);
  });
});

// ---------------------------------------------------------------------------
// El contenido va centrado
// ---------------------------------------------------------------------------
//
// Al ocultar la sidebar quedó a la vista un problema que antes disimulaba: el
// contenedor de estas pantallas tiene `max-w-*` pero le faltaba `mx-auto`, así
// que el contenido quedaba anclado a la izquierda con todo el espacio libre a la
// derecha. Con la sidebar puesta, ese hueco lo llenaba el menú y no se notaba.

describe('centrado del contenido', () => {
  it.each(PASOS_PREVIOS)('%s centra su contenedor con ancho máximo', (archivo) => {
    const contenedores = fuente(archivo).match(/className="[^"]*\bmax-w-[^"]*"/g) ?? [];
    // Se ignoran los `max-w` chicos de elementos internos (etiquetas del
    // stepper, textos): el que tiene que centrarse es el contenedor de la
    // pantalla, que además trae el espaciado vertical.
    const principales = contenedores.filter((c) => /space-y-/.test(c));
    expect(principales.length).toBeGreaterThan(0);
    for (const c of principales) {
      expect(c, `falta mx-auto en: ${c}`).toMatch(/\bmx-auto\b/);
    }
  });
});
