/**
 * El filtro de Auditoría tiene que cubrir TODAS las acciones que el backend registra.
 *
 * `ACCIONES_POR_MODULO` es una curación manual: alguien tradujo a mano cada valor
 * de `AccionAuditoria` (backend/app/application/audit/acciones.py) a una opción
 * del desplegable. Nada obliga a actualizarla cuando el backend suma una acción,
 * y el síntoma es mudo: la acción se registra, aparece en el listado sin filtrar,
 * pero no hay forma de acotar la búsqueda a ella. En una pantalla de auditoría
 * eso es grave: quien investiga algo puntual no encuentra el camino.
 *
 * Auditado el 28/8/2026: faltaban las bajas del banco de preguntas, las de
 * categorías, el volver a borrador de un examen y el marcado manual de nota.
 *
 * El backend filtra con `ilike('%valor%')` (ver `audit/service.py`), así que una
 * opción cubre una acción cuando su valor es SUBCADENA de la acción. Por eso
 * `retention.` cubre las cuatro acciones de retención con una sola opción.
 */

import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const ACCIONES_PY = path.resolve(AQUI, '../../../backend/app/application/audit/acciones.py');
const AUDITORIA_TSX = path.resolve(AQUI, 'Auditoria.tsx');

/** Valores del enum `AccionAuditoria` del backend. */
function accionesDelBackend(): string[] {
  const fuente = readFileSync(ACCIONES_PY, 'utf8');
  const clase = /class AccionAuditoria\b[\s\S]*?(?=\nclass |$)/.exec(fuente);
  if (!clase) throw new Error('No se encontró la clase AccionAuditoria');
  return [...clase[0].matchAll(/^\s+[A-Z_0-9]+\s*=\s*"([^"]+)"/gm)].map((m) => m[1]);
}

/** Valores de filtro declarados en el desplegable de la pantalla. */
function patronesDelFiltro(): string[] {
  const fuente = readFileSync(AUDITORIA_TSX, 'utf8');
  const catalogo = /const ACCIONES_POR_MODULO[\s\S]*?\n};/.exec(fuente);
  if (!catalogo) throw new Error('No se encontró ACCIONES_POR_MODULO');
  return [...catalogo[0].matchAll(/accion:\s*'([^']+)'/g)]
    .flatMap((m) => m[1].split(','))
    .map((p) => p.trim())
    .filter(Boolean);
}

// Sin el backend en disco (un checkout solo del front) el test no puede opinar.
const hayBackend = existsSync(ACCIONES_PY);

describe.skipIf(!hayBackend)('filtro de acciones de Auditoría', () => {
  it('toda acción registrada por el backend se puede filtrar', () => {
    const patrones = patronesDelFiltro();
    const sinCubrir = accionesDelBackend().filter(
      (accion) => !patrones.some((p) => accion.includes(p)),
    );
    expect(
      sinCubrir,
      `Estas acciones se registran pero no hay opción en el filtro:\n  ${sinCubrir.join('\n  ')}\n` +
        'Agregá una opción en ACCIONES_POR_MODULO (Auditoria.tsx).',
    ).toEqual([]);
  });

  it('ninguna opción del filtro busca algo que el backend nunca registra', () => {
    // Una opción que no matchea ninguna acción devuelve siempre cero resultados,
    // y quien la usa concluye que no pasó nada — cuando en realidad no existe.
    const acciones = accionesDelBackend();
    const muertos = patronesDelFiltro().filter((p) => !acciones.some((a) => a.includes(p)));
    expect(
      muertos,
      `Estas opciones del filtro no matchean ninguna acción real: ${muertos.join(', ')}`,
    ).toEqual([]);
  });
});
