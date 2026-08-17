/**
 * Vuln reload/restart — test de COMPONENTE de la reanudación de examen.
 *
 * Antes del fix: recargar la página a mitad del examen perdía las respuestas
 * (React state) y reseteaba el timer a la duración completa (arrancaba a contar
 * desde el montaje, no desde la sesión original). Este archivo prueba, montando
 * el componente REAL `Examen` (mismo patrón que Examen.finalizar.test.tsx, sin
 * @testing-library):
 *
 *   1. Al montar con una sesión REANUDADA (creada_en en el pasado), el timer
 *      arranca YA descontado el tiempo transcurrido (no desde cero).
 *   2. Las respuestas ya guardadas server-side (GET .../respuestas) se restauran
 *      en el estado — la opción aparece pre-seleccionada.
 *   3. Seleccionar una opción dispara un submit incremental (debounced) de las
 *      respuestas, sin esperar a "Terminar intento".
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, createElement } from 'react';
import { createRoot, type Root } from 'react-dom/client';

const { obtenerRespuestasProctoring, enviarRespuestasProctoring } = vi.hoisted(() => ({
  obtenerRespuestasProctoring: vi.fn(async () => [] as { pregunta_id: string; opcion_elegida_id: string }[]),
  enviarRespuestasProctoring: vi.fn(async () => ({ session_id: 'sess-1', respuestas_guardadas: 1 })),
}));

// creada_en 5 minutos (300s) en el PASADO: simula una sesión REANUDADA tras un F5.
const CREADA_EN_HACE_5_MIN = new Date(Date.now() - 5 * 60 * 1000).toISOString();

vi.mock('../proctoring/useExamProctoring', () => ({
  useExamProctoring: () => ({
    sessionId: 'sess-1',
    sessionCreadaEn: CREADA_EN_HACE_5_MIN,
    score: 0,
    eventCount: 0,
    activo: false,
    eventos: [] as unknown[],
    extraMonitorActive: false,
    detener: vi.fn(),
  }),
}));

vi.mock('../lib/store', () => {
  const state = {
    examenActivo: { id: 'ex1', nombre: 'Final', duracion_min: 60, examen_contenido_id: 'c1', umbral_score: 70 },
    principal: { username: 'LU-123', email: 'alumno@uni.edu', nombre: 'Ana', roles: [] },
  };
  return { useApp: (selector: (s: typeof state) => unknown) => selector(state) };
});

// Auth: el principal (identidad del alumno) es fuente única en useAuth (C-73).
vi.mock('../lib/authStore', () => {
  const authState = {
    principal: { username: 'LU-123', email: 'alumno@uni.edu', nombre: 'Ana', roles: [] },
  };
  return { useAuth: (selector: (s: typeof authState) => unknown) => selector(authState) };
});

vi.mock('../lib/router', () => ({ useNavigate: () => vi.fn() }));

vi.mock('../lib/api', () => ({
  TIPO_EVENTO_LABEL: {},
  api: { obtenerRespuestasProctoring, enviarRespuestasProctoring },
}));

vi.mock('../config/effectiveConfigCache', () => ({
  getEffectiveConfig: () => null,
  loadEffectiveConfig: () => Promise.resolve(null),
  resetEffectiveConfigCache: () => {},
}));
vi.mock('../proctoring/scoringWeights', () => ({ pesoEvento: () => 0 }));

// Examen con tiempo_limite_min=30 y 1 pregunta con 2 opciones.
vi.mock('../lib/examTakingApi', () => ({
  fetchExamenParaRendir: () =>
    Promise.resolve({
      tiempo_limite_min: 30,
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

import Examen from './Examen';

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  (globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  obtenerRespuestasProctoring.mockClear();
  enviarRespuestasProctoring.mockClear();
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.useRealTimers();
});

async function montar(): Promise<void> {
  await act(async () => {
    root.render(createElement(Examen));
  });
  await act(async () => {});
  await act(async () => {});
}

function timerTexto(): string | null {
  const el = Array.from(container.querySelectorAll('span')).find((s) => /\d{2}:\d{2}/.test(s.textContent ?? ''));
  const match = el?.textContent?.match(/(\d{2}):(\d{2})/);
  return match ? `${match[1]}:${match[2]}` : null;
}

describe('Vuln reload — timer anclado a la creada_en de la sesión', () => {
  it('al reanudar una sesión creada hace 5 minutos, el timer YA arranca descontado (no en 30:00)', async () => {
    await montar();

    const texto = timerTexto();
    expect(texto).not.toBeNull();
    // tiempo_limite_min=30 (1800s) - 300s transcurridos = 1500s = 25:00, con margen
    // de unos segundos por el tiempo de ejecución del test.
    const [mm] = (texto as string).split(':').map(Number);
    expect(mm).toBeLessThanOrEqual(25);
    expect(mm).toBeGreaterThanOrEqual(24);
  });
});

describe('Vuln reload — restauración de respuestas ya guardadas', () => {
  it('restaura la opción ya contestada server-side (no arranca en blanco)', async () => {
    obtenerRespuestasProctoring.mockResolvedValueOnce([{ pregunta_id: 'p1', opcion_elegida_id: 'o2' }]);

    await montar();

    expect(obtenerRespuestasProctoring).toHaveBeenCalledWith('sess-1');
    const radios = Array.from(container.querySelectorAll<HTMLInputElement>('input[type="radio"]'));
    const marcada = radios.find((r) => r.checked);
    expect(marcada?.value ?? marcada?.id).toBeTruthy();
    // La opción B (o2, la restaurada) debe quedar marcada.
    const labelDeMarcada = marcada?.closest('label')?.textContent ?? '';
    expect(labelDeMarcada).toContain('Opción B');
  });
});

describe('Vuln reload — submit incremental (debounced) de respuestas', () => {
  it('seleccionar una opción dispara un submit incremental tras el debounce, sin esperar a "Terminar intento"', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await montar();

    const radio = container.querySelector<HTMLInputElement>('input[type="radio"]');
    expect(radio).not.toBeNull();
    await act(async () => {
      radio!.click();
    });

    // Antes de que venza el debounce: todavía no se envió.
    expect(enviarRespuestasProctoring).not.toHaveBeenCalled();

    await act(async () => {
      vi.advanceTimersByTime(900);
    });

    expect(enviarRespuestasProctoring).toHaveBeenCalledTimes(1);
    const [sid, items] = enviarRespuestasProctoring.mock.calls[0];
    expect(sid).toBe('sess-1');
    expect(items).toEqual([{ pregunta_id: 'p1', opcion_elegida_id: 'o1' }]);
  });
});
