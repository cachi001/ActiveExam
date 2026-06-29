/**
 * Test de COMPONENTE de la entrega del examen (C-69 sección 7).
 *
 * Monta el componente REAL `Examen` en jsdom (vía react-dom/client, sin
 * @testing-library — no está instalado, mismo patrón que Examen.lockdownOverlay.test.tsx)
 * y verifica la cadena de entrega de extremo a extremo:
 *
 *   1. El alumno selecciona una opción.
 *   2. Hace clic en "Finalizar y entregar".
 *   3. Las respuestas se POSTean ANTES de finalizar la sesión (para que el backend
 *      calcule la nota server-side) y ANTES de navegar a /cierre.
 *
 * No se mockea la base de datos ni la red (no hay ninguna en juego: api está mockeado
 * a nivel de módulo). El orden se verifica con un array compartido que cada mock empuja.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, createElement } from 'react';
import { createRoot, type Root } from 'react-dom/client';

// --- Spies compartidos con las factories de vi.mock --------------------------
// vi.mock se hoistea por encima de los imports; vi.hoisted permite que las
// factories referencien estos spies sin el "Cannot access before initialization".
const { order, detener, navigate, enviarRespuestasProctoring } = vi.hoisted(() => {
  const order: string[] = [];
  return {
    order,
    detener: vi.fn(() => {
      order.push('detener');
    }),
    navigate: vi.fn(() => {
      order.push('navigate');
    }),
    enviarRespuestasProctoring: vi.fn(async () => {
      order.push('respuestas');
      return null;
    }),
  };
});

// --- Mocks de colaboradores pesados --------------------------------------------

vi.mock('../proctoring/useExamProctoring', () => ({
  useExamProctoring: () => ({
    sessionId: 'sess-1',
    score: 0,
    eventCount: 0,
    activo: false,
    eventos: [] as unknown[],
    extraMonitorActive: false,
    detener,
  }),
}));

// Store: examen activo + principal (identidad del alumno para el write-back).
vi.mock('../lib/store', () => {
  const state = {
    examenActivo: { id: 'ex1', nombre: 'Final', duracion_min: 60, examen_contenido_id: 'c1', umbral_score: 70 },
    principal: { id_institucional: 'LU-123', email: 'alumno@uni.edu', nombre: 'Ana', roles: [] },
  };
  return { useApp: (selector: (s: typeof state) => unknown) => selector(state) };
});

// Router: navigate registra su invocación.
vi.mock('../lib/router', () => ({ useNavigate: () => navigate }));

// api: enviarRespuestasProctoring es el SUT — async, registra orden y argumentos.
vi.mock('../lib/api', () => ({
  TIPO_EVENTO_LABEL: {},
  api: { enviarRespuestasProctoring },
}));

vi.mock('../config/effectiveConfigCache', () => ({ getEffectiveConfig: () => null, loadEffectiveConfig: () => Promise.resolve(null), resetEffectiveConfigCache: () => {} }));
vi.mock('../proctoring/scoringWeights', () => ({ pesoEvento: () => 0 }));

// Una sola pregunta con dos opciones: deja el botón "Finalizar y entregar" visible
// (no hay "Siguiente" en la última/única pregunta).
vi.mock('../lib/examTakingApi', () => ({
  fetchExamenParaRendir: () =>
    Promise.resolve({
      preguntas: [
        {
          id: 'p1',
          enunciado: 'Pregunta uno',
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

// Lockdown neutralizado (no nos interesa el enforcement de fullscreen acá).
vi.mock('../proctoring/fullscreenLockdown', () => ({
  FullscreenLockdown: class {
    iniciar() {
      return Promise.resolve();
    }
    detener() {}
    volverAPantallaCompleta() {}
  },
  soportaFullscreen: () => true,
  MENSAJE_LIMITE_FULLSCREEN: '',
}));

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
vi.mock('./alumno/components/QuestionNavigator', () => ({ QuestionNavigator: () => null }));

// Import del componente REAL bajo prueba — después de declarar los mocks.
import Examen from './Examen';

let container: HTMLDivElement;
let root: Root;

function botonFinalizar(): HTMLButtonElement | null {
  return (
    Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Finalizar y entregar'),
    ) as HTMLButtonElement | undefined
  ) ?? null;
}

beforeEach(() => {
  (globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  order.length = 0;
  detener.mockClear();
  navigate.mockClear();
  enviarRespuestasProctoring.mockClear();
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

async function seleccionarPrimeraOpcion(): Promise<void> {
  const radio = container.querySelector<HTMLInputElement>('input[type="radio"]');
  expect(radio).not.toBeNull();
  await act(async () => {
    radio!.click();
  });
}

async function clickFinalizar(): Promise<void> {
  const btn = botonFinalizar();
  expect(btn).not.toBeNull();
  await act(async () => {
    btn!.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  });
  // Flush microtasks del finalizar async (await del POST → detener → navigate).
  await act(async () => {});
}

describe('C-69 §7 — entrega: respuestas antes de finalizar', () => {
  it('al finalizar, POSTea las respuestas seleccionadas antes de detener y navegar', async () => {
    await montar();
    await seleccionarPrimeraOpcion();
    await clickFinalizar();

    expect(enviarRespuestasProctoring).toHaveBeenCalledTimes(1);
    const [sid, items] = enviarRespuestasProctoring.mock.calls[0];
    expect(sid).toBe('sess-1');
    expect(items).toEqual([{ pregunta_id: 'p1', opcion_elegida_id: 'o1' }]);

    // ORDEN: respuestas → detener → navigate.
    expect(order).toEqual(['respuestas', 'detener', 'navigate']);
  });

  it('H4 (seguridad): NO envía identidad del cliente — el backend usa la del JWT', async () => {
    await montar();
    await seleccionarPrimeraOpcion();
    await clickFinalizar();

    // El submit se llama solo con (sessionId, items). La identidad del alumno la
    // resuelve el backend desde la sesión (persistida del JWT al crearla); mandar
    // alumno_idnumber/email desde el cliente sería superficie de spoofing y ahora
    // el schema lo rechaza (extra='forbid').
    const args = enviarRespuestasProctoring.mock.calls[0];
    expect(args).toHaveLength(2);
    expect(args[2]).toBeUndefined();
  });

  it('navega a /cierre tras la entrega', async () => {
    await montar();
    await seleccionarPrimeraOpcion();
    await clickFinalizar();

    expect(navigate).toHaveBeenCalledWith('/cierre');
  });
});
