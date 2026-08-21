/**
 * Test de COMPONENTE del overlay de calibración de mirada (pentest 2026-08-21,
 * miedo del usuario: "si la webcam está descentrada, mirar bien a la pantalla
 * me podría detectar mirada desviada"). La lógica de calibración en sí
 * (capturarBaselineGaze, StateTransitionRules.calibrarGaze) ya está cubierta en
 * stateTransitionRules.test.ts y useExamProctoring.calibracionGaze.test.ts —
 * este test cubre SOLO el cableado: que Examen.tsx muestra/oculta
 * <CalibracionMirada /> según el `calibrando` que devuelve useExamProctoring.
 *
 * Monta el componente REAL `Examen` en jsdom (mismo patrón que
 * Examen.finalizar.test.tsx: sin @testing-library, no está instalado).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, createElement } from 'react';
import { createRoot, type Root } from 'react-dom/client';

const { useExamProctoringMock } = vi.hoisted(() => {
  let calibrando = false;
  return {
    useExamProctoringMock: {
      setCalibrando: (v: boolean) => {
        calibrando = v;
      },
      hook: () => ({
        sessionId: 'sess-1',
        score: 0,
        eventCount: 0,
        activo: false,
        eventos: [] as unknown[],
        extraMonitorActive: false,
        calibrando,
        detener: () => {},
      }),
    },
  };
});

vi.mock('../proctoring/useExamProctoring', () => ({
  useExamProctoring: () => useExamProctoringMock.hook(),
}));

vi.mock('../lib/store', () => {
  const state = {
    examenActivo: { id: 'ex1', nombre: 'Final', duracion_min: 60, examen_contenido_id: 'c1', umbral_score: 70 },
    principal: { username: 'LU-123', email: 'alumno@uni.edu', nombre: 'Ana', roles: [] },
  };
  return { useApp: (selector: (s: typeof state) => unknown) => selector(state) };
});

vi.mock('../lib/authStore', () => {
  const authState = {
    principal: { username: 'LU-123', email: 'alumno@uni.edu', nombre: 'Ana', roles: [] },
  };
  return { useAuth: (selector: (s: typeof authState) => unknown) => selector(authState) };
});

vi.mock('../lib/router', () => ({ useNavigate: () => vi.fn() }));

vi.mock('../lib/api', () => ({
  TIPO_EVENTO_LABEL: {},
  api: { enviarRespuestasProctoring: vi.fn(async () => null), obtenerRespuestasProctoring: vi.fn(async () => []) },
}));

vi.mock('../config/effectiveConfigCache', () => ({
  getEffectiveConfig: () => null,
  loadEffectiveConfig: () => Promise.resolve(null),
  resetEffectiveConfigCache: () => {},
}));
vi.mock('../proctoring/scoringWeights', () => ({ pesoEvento: () => 0 }));

vi.mock('../lib/examTakingApi', () => ({
  fetchExamenParaRendir: () => Promise.resolve({ preguntas: [] }),
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
  useExamProctoringMock.setCalibrando(false);
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
  await act(async () => {});
}

describe('Examen — overlay de calibración de mirada', () => {
  it('muestra el overlay "Mirá al centro" mientras calibrando es true', async () => {
    useExamProctoringMock.setCalibrando(true);
    await montar();
    expect(container.textContent).toContain('Mirá al centro de la pantalla');
  });

  it('NO muestra el overlay cuando calibrando es false', async () => {
    useExamProctoringMock.setCalibrando(false);
    await montar();
    expect(container.textContent).not.toContain('Mirá al centro de la pantalla');
  });
});
