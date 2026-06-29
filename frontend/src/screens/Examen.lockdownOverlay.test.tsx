/**
 * Test de COMPONENTE del overlay de lockdown de pantalla completa (C-69, Task 5.4).
 *
 * Monta el componente REAL `Examen` en jsdom (vía react-dom/client, sin
 * @testing-library — no está instalado) y ejercita el flujo de enforcement de
 * pantalla completa de extremo a extremo:
 *
 *   1. Entrar al examen (mount = gesto del alumno) → fuerza requestFullscreen.
 *   2. Al salir de fullscreen aparece un overlay de bloqueo que TAPA las preguntas.
 *   3. El botón "Volver a pantalla completa" RE-INVOCA requestFullscreen.
 *   4. El overlay se OCULTA al volver a fullscreen + pestaña visible.
 *
 * `FullscreenLockdown` y los detectores de contexto se mantienen REALES: la fuente
 * de verdad de fullscreen se controla manipulando `document.fullscreenElement` y
 * disparando `fullscreenchange` en jsdom (mismo espíritu que los deps inyectables
 * de los tests 5.1–5.3, pero contra el DOM real que usa Examen.tsx).
 *
 * Las dependencias pesadas del componente (proctoring/MediaPipe, store, router,
 * UI, chat, pausa, API de rendición) se mockean para aislar el lockdown. NO se
 * mockea la base de datos ni la red (no hay ninguna en juego aquí).
 *
 * TDD: 5.4 — el overlay ya fue integrado en Examen.tsx (5.5), así que este test
 * de componente debe pasar (GREEN) contra el código actual sin tocar Examen.tsx.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, createElement } from 'react';
import { createRoot, type Root } from 'react-dom/client';

// --- Mocks de colaboradores pesados (mantienen FullscreenLockdown REAL) -------

// Proctoring real arrancaría MediaPipe / Web Workers: lo neutralizamos.
vi.mock('../proctoring/useExamProctoring', () => {
  const result = {
    sessionId: null,
    score: 0,
    eventCount: 0,
    activo: false,
    eventos: [] as unknown[],
    extraMonitorActive: false,
    detener: () => {},
  };
  return { useExamProctoring: () => result };
});

// Store: examen activo mínimo para que el componente renderice.
vi.mock('../lib/store', () => {
  const examenActivo = { duracion_min: 60, examen_contenido_id: 'c1', umbral_score: 70 };
  return { useApp: (selector: (s: { examenActivo: typeof examenActivo }) => unknown) => selector({ examenActivo }) };
});

vi.mock('../lib/router', () => ({ useNavigate: () => () => {} }));

vi.mock('../lib/api', () => ({ TIPO_EVENTO_LABEL: {} }));

vi.mock('../config/effectiveConfigCache', () => ({ getEffectiveConfig: () => null }));

vi.mock('../proctoring/scoringWeights', () => ({ pesoEvento: () => 0 }));

// Preguntas de rendición desde la "API" (sin red): dos opciones para tapar con overlay.
vi.mock('../lib/examTakingApi', () => ({
  fetchExamenParaRendir: () =>
    Promise.resolve({
      preguntas: [
        {
          id: 'p1',
          enunciado: 'Pregunta de prueba uno',
          tipo: 'multichoice',
          orden: 0,
          opciones: [
            { id: 'o1', texto: 'Opción A' },
            { id: 'o2', texto: 'Opción B' },
          ],
        },
      ],
    }),
}));

// UI: shells/components reemplazados por equivalentes mínimos que preservan
// onClick y children (necesario para que el botón del overlay sea clickeable).
vi.mock('../ui/shells', async () => {
  const React = await import('react');
  return { StudentShell: ({ children }: { children: unknown }) => React.createElement('div', null, children) };
});

vi.mock('../ui/components', async () => {
  const React = await import('react');
  return {
    Icon: () => null,
    Button: ({ children, onClick }: { children?: unknown; onClick?: () => void }) =>
      React.createElement('button', { onClick }, children),
    Card: ({ children }: { children?: unknown }) => React.createElement('div', null, children),
    SeverityBadge: () => null,
  };
});

vi.mock('../ui/ChatBox', () => ({ ChatBox: () => null }));
vi.mock('./PausaAlumno', () => ({ PausaAlumno: () => null }));

// Import del componente REAL bajo prueba — después de declarar los mocks.
import Examen from './Examen';

// --- Control del API de fullscreen en jsdom ------------------------------------

let fsEl: Element | null = null;
const rfs = vi.fn<[], Promise<void>>().mockResolvedValue(undefined);

let container: HTMLDivElement;
let root: Root;

function overlayDeBloqueo(): HTMLElement | null {
  // El overlay de lockdown es el único [role=alertdialog] que dice "Volver a pantalla completa".
  const dialogs = Array.from(container.querySelectorAll<HTMLElement>('[role="alertdialog"]'));
  return dialogs.find((d) => d.textContent?.includes('Volver a pantalla completa')) ?? null;
}

function botonVolver(): HTMLButtonElement | null {
  return (
    Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Volver a pantalla completa'),
    ) as HTMLButtonElement | undefined
  ) ?? null;
}

beforeEach(() => {
  (globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  rfs.mockClear();
  // Arrancamos EN fullscreen (el alumno acaba de entrar al examen).
  fsEl = document.documentElement;
  Object.defineProperty(document, 'fullscreenElement', { configurable: true, get: () => fsEl });
  (document.documentElement as unknown as { requestFullscreen: () => Promise<void> }).requestFullscreen = rfs;
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

async function montar(): Promise<void> {
  await act(async () => {
    root.render(createElement(Examen));
  });
  // Flush extra para la promesa de fetchExamenParaRendir (setPreguntas).
  await act(async () => {});
}

async function dispararFullscreenChange(enFullscreen: boolean): Promise<void> {
  await act(async () => {
    fsEl = enFullscreen ? document.documentElement : null;
    document.dispatchEvent(new Event('fullscreenchange'));
  });
}

describe('5.4 — Overlay de lockdown de pantalla completa (componente Examen)', () => {
  it('al entrar al examen (mount) se fuerza requestFullscreen', async () => {
    await montar();
    expect(rfs).toHaveBeenCalled();
  });

  it('sin salir de fullscreen NO se muestra el overlay (preguntas visibles)', async () => {
    await montar();
    expect(overlayDeBloqueo()).toBeNull();
    expect(container.textContent).toContain('Pregunta de prueba uno');
  });

  it('al salir de fullscreen aparece el overlay de bloqueo que tapa las preguntas', async () => {
    await montar();
    expect(overlayDeBloqueo()).toBeNull();

    await dispararFullscreenChange(false);

    const overlay = overlayDeBloqueo();
    expect(overlay).not.toBeNull();
    // El overlay cubre toda la pantalla (fixed inset-0) por encima de las preguntas.
    expect(overlay!.className).toMatch(/fixed/);
    expect(overlay!.className).toMatch(/inset-0/);
    // Las preguntas siguen en el DOM: el overlay las TAPA, no las elimina.
    expect(container.textContent).toContain('Pregunta de prueba uno');
  });

  it('el botón "Volver a pantalla completa" re-invoca requestFullscreen', async () => {
    await montar();
    await dispararFullscreenChange(false);

    const llamadasAntes = rfs.mock.calls.length;
    const btn = botonVolver();
    expect(btn).not.toBeNull();
    await act(async () => {
      btn!.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    expect(rfs.mock.calls.length).toBeGreaterThan(llamadasAntes);
  });

  it('el overlay se oculta al volver a fullscreen + pestaña visible', async () => {
    await montar();
    await dispararFullscreenChange(false);
    expect(overlayDeBloqueo()).not.toBeNull();

    // Volver a fullscreen (visibilityState de jsdom = 'visible' por defecto).
    await dispararFullscreenChange(true);

    expect(overlayDeBloqueo()).toBeNull();
    // Las preguntas siguen disponibles tras desbloquear (la sesión nunca se anula — L2.5).
    expect(container.textContent).toContain('Pregunta de prueba uno');
  });
});
