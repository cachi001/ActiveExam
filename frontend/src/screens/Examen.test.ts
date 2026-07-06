/**
 * Tests de Examen.tsx y módulos auxiliares — Secciones 4.1–4.10 (C-69).
 *
 * Sin @testing-library/react (no instalado en el proyecto).
 * Combina:
 *  - Source inspection: verifica ausencia/presencia de código específico en Examen.tsx.
 *  - Logic tests: funciones puras de ExamenLogic.ts (navegación prev/next).
 *  - API client tests: fetchExamenParaRendir de examTakingApi.ts.
 *
 * TDD: 4.1 RED (toast) -> 4.2 GREEN -> 4.3 TRIANGULATE
 *      4.4 RED (PREGUNTA) -> 4.5 GREEN -> 4.6 TRIANGULATE
 *      4.7 RED (nav) -> 4.8 GREEN
 *      4.9 RED (finalizar) -> 4.10 GREEN
 */

import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it, vi, afterEach } from 'vitest';

import {
  puedeIrAnterior,
  puedeIrSiguiente,
  avanzarPregunta,
  retrocederPregunta,
  preguntaEnIndice,
} from './ExamenLogic';
import type { PreguntaRendicion } from '../lib/examTakingApi';

const here = dirname(fileURLToPath(import.meta.url));
const examenSource = readFileSync(join(here, 'Examen.tsx'), 'utf8');
const apiSource = readFileSync(join(here, '..', 'lib', 'examTakingApi.ts'), 'utf8');
// El panel de señales de integridad se componentizó a examen/IntegridadPanel.tsx:
// ahí viven SEV_CARD/SEV_ICON y el render de eventos.
const panelSource = readFileSync(join(here, 'examen', 'IntegridadPanel.tsx'), 'utf8');

// ---------------------------------------------------------------------------
// 4.1 RED: toast.show NO se llama ante eventos de proctoring
// ---------------------------------------------------------------------------

describe('4.1-4.3 — Eliminación de toast por evento de proctoring', () => {
  it('Examen.tsx no llama a toast.show para eventos de proctoring', () => {
    // El useEffect que llamaba toast.show por cada evento fue eliminado (D5).
    expect(examenSource).not.toMatch(/toast\.show\s*\(/);
  });

  it('SEV_TOAST map fue eliminado (filtraba la detección al alumno)', () => {
    // El mapa SEV_TOAST: Record<string, ToastTipo> fue eliminado.
    expect(examenSource).not.toMatch(/SEV_TOAST/);
  });

  it('toastedIds ref fue eliminado (trackeaba ids ya notificados)', () => {
    expect(examenSource).not.toMatch(/toastedIds/);
  });

  it('useToast ya no se importa ni usa (4.2 GREEN)', () => {
    // Si useToast desaparece del source, el toast fue quitado completamente.
    expect(examenSource).not.toMatch(/useToast/);
  });

  // 4.3 TRIANGULATE: la detección/score sigue intacta
  it('eventos del panel lateral siguen presentes (detección intacta)', () => {
    // SEV_CARD y SEV_ICON se mantienen (panel lateral "Señales de integridad").
    expect(panelSource).toMatch(/SEV_CARD/);
    expect(panelSource).toMatch(/SEV_ICON/);
  });

  it('el panel de señales sigue renderizando eventos (map sobre los últimos)', () => {
    expect(panelSource).toMatch(/eventos\.slice\(-4\)/);
    expect(panelSource).toMatch(/ultimosEventos\.map/);
  });

  it('useExamProctoring sigue importado y en uso (score/streaming intactos)', () => {
    expect(examenSource).toMatch(/useExamProctoring/);
  });
});

// ---------------------------------------------------------------------------
// 4.4 RED: PREGUNTA hardcodeada eliminada → API real
// ---------------------------------------------------------------------------

describe('4.4-4.6 — Reemplazo de PREGUNTA hardcodeada por API real', () => {
  it('la constante PREGUNTA hardcodeada ya no existe en Examen.tsx', () => {
    // La const PREGUNTA con el enunciado fijo fue reemplazada por la API.
    expect(examenSource).not.toMatch(/const PREGUNTA\s*=/);
  });

  it('Examen.tsx importa el cliente de API de rendición', () => {
    expect(examenSource).toMatch(/examTakingApi|fetchExamenParaRendir/);
  });

  it('examTakingApi.ts expone fetchExamenParaRendir', () => {
    expect(apiSource).toMatch(/fetchExamenParaRendir/);
  });

  it('examTakingApi.ts llama al endpoint correcto', () => {
    expect(apiSource).toMatch(/\/api\/v1\/exam-content\//);
  });

  // 4.6 TRIANGULATE: D3 — es_correcta no aparece en el cliente
  it('examTakingApi.ts no incluye es_correcta en sus interfaces', () => {
    expect(apiSource).not.toMatch(/es_correcta/);
  });
});

// ---------------------------------------------------------------------------
// 4.7 RED / 4.8 GREEN: navegación prev/next (lógica pura)
// ---------------------------------------------------------------------------

describe('4.7-4.8 — Navegación prev/next de preguntas', () => {
  it('no hay "anterior" en la primera pregunta (indice 0)', () => {
    expect(puedeIrAnterior(0)).toBe(false);
  });

  it('hay "anterior" cuando el índice es > 0', () => {
    expect(puedeIrAnterior(1)).toBe(true);
    expect(puedeIrAnterior(4)).toBe(true);
  });

  it('no hay "siguiente" en la última pregunta', () => {
    expect(puedeIrSiguiente(4, 5)).toBe(false);
  });

  it('hay "siguiente" cuando el índice no está en el límite', () => {
    expect(puedeIrSiguiente(0, 5)).toBe(true);
    expect(puedeIrSiguiente(3, 5)).toBe(true);
  });

  it('avanzarPregunta incrementa el índice', () => {
    expect(avanzarPregunta(0, 5)).toBe(1);
    expect(avanzarPregunta(3, 5)).toBe(4);
  });

  it('avanzarPregunta clampa en el límite superior', () => {
    expect(avanzarPregunta(4, 5)).toBe(4);
  });

  it('retrocederPregunta decrementa el índice', () => {
    expect(retrocederPregunta(3)).toBe(2);
    expect(retrocederPregunta(1)).toBe(0);
  });

  it('retrocederPregunta clampa en 0', () => {
    expect(retrocederPregunta(0)).toBe(0);
  });

  // TRIANGULATE: selección conservada implícitamente por el mapa de respuestas
  it('preguntaEnIndice devuelve la pregunta correcta', () => {
    const preguntas: PreguntaRendicion[] = [
      { id: 'p1', enunciado: 'Q1', tipo: 'multichoice', orden: 0, opciones: [] },
      { id: 'p2', enunciado: 'Q2', tipo: 'truefalse', orden: 1, opciones: [] },
    ];
    expect(preguntaEnIndice(preguntas, 0)?.id).toBe('p1');
    expect(preguntaEnIndice(preguntas, 1)?.id).toBe('p2');
  });

  it('preguntaEnIndice devuelve null para lista vacía', () => {
    expect(preguntaEnIndice([], 0)).toBeNull();
  });

  it('Examen.tsx incluye navegación anterior/siguiente', () => {
    // El componente debe tener botones/acciones de navegación.
    expect(examenSource).toMatch(/anterior|Anterior|puedeIrAnterior/i);
    expect(examenSource).toMatch(/siguiente|Siguiente|puedeIrSiguiente/i);
  });
});

// NOTA: la acción de finalizar (llama a enviarRespuestasProctoring → detener →
// navega a /cierre, en ese orden; mapea respuestas; NO propaga identidad del
// cliente — H4) está probada por COMPORTAMIENTO real en Examen.finalizar.test.tsx,
// que monta el componente. Acá antes había bloques de source-inspection que
// duplicaban esa cobertura de forma frágil; se removieron (quedan los chequeos de
// remoción 4.1-4.6 y la lógica pura de navegación 4.7-4.8 arriba).
