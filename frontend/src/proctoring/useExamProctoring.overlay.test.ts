/**
 * Test de regresión (C-53, vision-overlay-canvas) — el flujo de EXAMEN del alumno
 * NO instancia `VisionOverlay`.
 *
 * La spec exige que el examen corra el pipeline de visión SIN montar el overlay
 * de canvas: ningún punto de mesh ni box sobre la cara del alumno. El overlay de
 * diagnóstico queda restringido al harness de staff. Este test es estático:
 * inspecciona el fuente de `useExamProctoring.ts` y verifica que no importa ni
 * referencia `VisionOverlay` (más allá del comentario-guardia que lo prohíbe).
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { describe, expect, it } from "vitest";

const here = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(here, "useExamProctoring.ts"), "utf8");

describe("useExamProctoring — sin overlay sobre la cara del alumno", () => {
  it("no importa VisionOverlay", () => {
    // No debe existir un import de VisionOverlay (ni default ni nombrado/dinámico).
    expect(source).not.toMatch(/import[^\n]*VisionOverlay/);
    expect(source).not.toMatch(/import\([^)]*VisionOverlay/);
  });

  it("no instancia el componente <VisionOverlay>", () => {
    expect(source).not.toMatch(/<VisionOverlay[\s/>]/);
  });

  it("contiene el comentario-guardia que prohíbe montar overlay en el examen", () => {
    expect(source).toMatch(/GUARDIA DE OVERLAY/);
  });
});
