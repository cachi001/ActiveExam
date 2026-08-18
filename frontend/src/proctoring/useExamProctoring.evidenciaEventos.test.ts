/**
 * C-76 (15.6): evento cambio_pestana / copiar_pegar ahora dispara captura.
 *
 * El gate real que decide si un evento discreto adjunta screenshot en el examen
 * del alumno es `EVENTOS_CON_EVIDENCIA_VISUAL` (useExamProctoring.ts) — el flag
 * `trigger_evidence` de `stateTransitionRules.ts` no llega hasta `sink.sendEvent`
 * (ver `visionPipeline.ts::emit`, que NO reenvía ese campo en el payload al sink),
 * así que la cobertura de "ahora captura" tiene que verificar este Set, no solo
 * el flag de las reglas (ya cubierto en `stateTransitionRules.test.ts`).
 *
 * Se testea el Set REAL exportado (no una copia) — mismo criterio que el resto
 * de este archivo de tests (`obtenerOCrearSesion`, `crearControladorCapturaPausa`):
 * montar el hook completo para esto requeriría mockear MediaPipe/video/IndexedDB
 * sin aportar cobertura adicional sobre ESTA decisión (membresía del Set).
 */
import { describe, expect, it } from 'vitest';
import { EVENTOS_CON_EVIDENCIA_VISUAL } from './useExamProctoring';

describe('EVENTOS_CON_EVIDENCIA_VISUAL — C-76 15.1/15.6', () => {
  it('incluye cambio_pestana (antes NO capturaba, decidido con el dueño)', () => {
    expect(EVENTOS_CON_EVIDENCIA_VISUAL.has('cambio_pestana')).toBe(true);
  });

  it('incluye copiar_pegar (antes NO capturaba, decidido con el dueño)', () => {
    expect(EVENTOS_CON_EVIDENCIA_VISUAL.has('copiar_pegar')).toBe(true);
  });

  it('sigue sin incluir eventos de sistema donde el registro YA es la evidencia', () => {
    // perdida_de_foco / salida_pantalla_completa no cambian con este change: el
    // registro del evento + timestamp sigue siendo suficiente, sin imagen.
    expect(EVENTOS_CON_EVIDENCIA_VISUAL.has('perdida_de_foco')).toBe(false);
    expect(EVENTOS_CON_EVIDENCIA_VISUAL.has('salida_pantalla_completa')).toBe(false);
  });

  it('conserva los eventos de visión pre-existentes (re-inferidos server-side)', () => {
    expect(EVENTOS_CON_EVIDENCIA_VISUAL.has('rostro_ausente')).toBe(true);
    expect(EVENTOS_CON_EVIDENCIA_VISUAL.has('multiples_rostros')).toBe(true);
  });
});
