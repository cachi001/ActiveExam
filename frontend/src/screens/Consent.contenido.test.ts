/**
 * C-69 sección 7: la sesión de proctoring ANTICIPADA (C-64 D1) que crea Consent.tsx
 * debe nacer vinculada al examen_contenido_id del examen activo.
 *
 * useExamProctoring reutiliza esa sesión vía existingSessionId (store). Si Consent la
 * creara SIN examen_contenido_id, la sesión reusada quedaría con examen_contenido_id =
 * NULL server-side y la nota nunca podría computarse (la cadena de corrección se rompe).
 *
 * Sin @testing-library: source inspection del componente real, mismo patrón que
 * Examen.test.ts (Consent.tsx tiene demasiados colaboradores para montarlo aislado
 * sin valor agregado sobre esta verificación).
 */

import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const here = dirname(fileURLToPath(import.meta.url));
const consentSource = readFileSync(join(here, 'Consent.tsx'), 'utf8');

describe('C-69 §7 — Consent.tsx propaga examen_contenido_id a la sesión anticipada', () => {
  it('crea la sesión anticipada con crearSesionProctoring', () => {
    expect(consentSource).toMatch(/crearSesionProctoring/);
  });

  it('pasa examen.examen_contenido_id a crearSesionProctoring', () => {
    // El 4º argumento (examenContenidoId) debe ser el del examen activo del store.
    expect(consentSource).toMatch(/examen\.examen_contenido_id/);
  });

  it('la llamada anticipada incluye exam_id y examen_contenido_id (vínculo completo)', () => {
    // Recorta el bloque de la llamada para verificar que ambos viajan juntos.
    const idx = consentSource.indexOf('crearSesionProctoring');
    const bloque = consentSource.slice(idx, idx + 200);
    expect(bloque).toMatch(/examen\.id/);
    expect(bloque).toMatch(/examen\.examen_contenido_id/);
  });
});
