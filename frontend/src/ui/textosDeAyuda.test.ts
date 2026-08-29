/**
 * Los textos de ayuda no pueden describir cosas que el sistema no hace.
 *
 * Es la misma clase de defecto que ya se corrigió en el consentimiento
 * (`backend/tests/test_consentimiento_dice_lo_que_hacemos.py`): un texto que se
 * escribió cuando la función existía y quedó ahí después de que dejara de
 * existir. Nadie lo nota, porque nada falla.
 *
 * Los 26 `<HelpButton>` se auditaron a mano el 28/8/2026 y aparecieron cinco
 * mentiras: inscripciones que no existen, un escaneo de DNI que está apagado,
 * tres decisiones de revisión cuando el modelo tiene dos, un rol faltante y una
 * referencia interna de diseño ("D11") a la vista del usuario.
 *
 * Este test lee el FUENTE, no el DOM: cubre las 26 pantallas de una sin tener
 * que montarlas, que es lo que hace viable la guarda.
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fg from 'fast-glob';
import { describe, expect, it } from 'vitest';

const raiz = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

/** Contenido de cada `<HelpButton>` de la app, sin etiquetas JSX. */
function textosDeAyuda(): { archivo: string; texto: string }[] {
  const archivos = fg.sync('**/*.tsx', {
    cwd: raiz,
    absolute: true,
    ignore: ['**/*.test.tsx', '**/HelpButton.tsx'],
  });
  const encontrados: { archivo: string; texto: string }[] = [];
  for (const archivo of archivos) {
    const fuente = readFileSync(archivo, 'utf8');
    let desde = 0;
    for (;;) {
      const abre = fuente.indexOf('<HelpButton', desde);
      if (abre === -1) break;
      const cierra = fuente.indexOf('</HelpButton>', abre);
      if (cierra === -1) break;
      const cuerpo = fuente
        .slice(abre, cierra)
        // Los comentarios JSX explican POR QUÉ se sacó cada mentira y nombran
        // justamente las palabras prohibidas: no son texto visible.
        .replace(/\{\/\*[\s\S]*?\*\/\}/g, '')
        .replace(/<[^>]*>/g, ' ');
      encontrados.push({
        archivo: path.relative(raiz, archivo),
        texto: cuerpo.replace(/\s+/g, ' ').trim(),
      });
      desde = cierra + 1;
    }
  }
  return encontrados;
}

const AYUDAS = textosDeAyuda();

/** Falla nombrando el archivo, para no tener que buscarlo a mano entre 26. */
function ningunaAyudaDice(patron: RegExp, porque: string) {
  const culpables = AYUDAS.filter((a) => patron.test(a.texto)).map((a) => a.archivo);
  expect(culpables, `${porque}\nArchivos: ${culpables.join(', ')}`).toEqual([]);
}

describe('textos de ayuda', () => {
  it('encuentra las ayudas de la app (si esto falla, el scan se rompió)', () => {
    expect(AYUDAS.length).toBeGreaterThan(20);
  });

  it('no habla de inscribirse a un examen', () => {
    ningunaAyudaDice(
      /inscribirte|inscripcion(es)?\b|inscripción/i,
      'No existe el modelo de inscripción: `misInscripciones()` devuelve [] siempre y los exámenes de la comisión aparecen solos.',
    );
  });

  it('no ofrece el escaneo de DNI', () => {
    ningunaAyudaDice(
      /escaneo de DNI|escanear (tu )?DNI/i,
      'El escaneo de DNI está detrás de ENABLE_DNI_SCAN (apagado) y la sección ni se renderiza.',
    );
  });

  it('no menciona una tercera decisión de revisión', () => {
    ningunaAyudaDice(
      /revisión formal|segunda instancia|caso abierto/i,
      'DecisionSesion tiene DOS decisiones terminales (aprobado/anulado), sin segunda instancia.',
    );
  });

  it('no filtra referencias internas de diseño al usuario', () => {
    ningunaAyudaDice(
      /\((?:D|DD|RN|ADR|C)-?\d+\)/,
      'Códigos como "(D11)" o "(C-69)" son notas internas: al usuario no le dicen nada.',
    );
  });

  it('no cita normativa', () => {
    // Misma decisión que rige el consentimiento: el sistema describe lo que
    // hace, no invoca leyes.
    ningunaAyudaDice(/ley\s|25\.?326/i, 'Decisión del dueño: no se menciona normativa en texto visible.');
  });

  it('no afirma que se captura la pantalla del alumno', () => {
    // No hay una sola llamada a getDisplayMedia en el front: las capturas son
    // frames de la cámara. De la pantalla se registran señales, sin imagen.
    ningunaAyudaDice(
      /captura[s]? de (tu |la )?pantalla|graba(r|ción)? (de )?(tu |la )?pantalla/i,
      'La pantalla NO se captura: solo se registran señales del navegador.',
    );
  });
});
