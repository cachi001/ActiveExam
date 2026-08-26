/**
 * Test de COMPONENTE de StudentShell — bug real (2026-08-21): la sidebar del
 * alumno aparecía "de la nada" en medio del wizard de enrollment (paso DNI),
 * porque el backend marca `perfil_completo=true` apenas termina la biometría
 * (el DNI es opcional y no lo bloquea) — ANTES de que el alumno termine/salte
 * ese paso. `ocultarNavegacion` fuerza ocultar sidebar/bottom-nav aunque
 * `isProfileComplete` ya sea `true`, sin tocar el header (a diferencia de `locked`).
 *
 * Monta el componente REAL en jsdom (sin @testing-library, no está instalado —
 * mismo patrón que Examen.finalizar.test.tsx).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, createElement } from 'react';
import { createRoot, type Root } from 'react-dom/client';

const { storeState } = vi.hoisted(() => ({
  storeState: {
    enrollmentStatus: { perfil_completo: true } as { perfil_completo: boolean },
    isProfileComplete: true,
  },
}));

vi.mock('../lib/store', () => ({
  useApp: (selector: (s: typeof storeState & { setEnrollmentStatus: () => void }) => unknown) =>
    selector({ ...storeState, setEnrollmentStatus: () => {} }),
}));

vi.mock('../lib/authStore', () => ({
  useAuth: (selector: (s: { principal: null; logout: () => void; setFotoPerfil: () => void }) => unknown) =>
    selector({ principal: null, logout: () => {}, setFotoPerfil: () => {} }),
}));

vi.mock('../lib/router', () => ({
  useRouter: () => ({ path: '/alumno/perfil' }),
  useNavigate: () => vi.fn(),
  Link: ({ children }: { children?: unknown }) => createElement('a', null, children),
}));

vi.mock('../lib/api', () => ({
  api: { getEnrollment: vi.fn(async () => ({ perfil_completo: true })), obtenerFotoPerfil: vi.fn(async () => null) },
}));

import { StudentShell } from './StudentShell';

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  (globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 1280 });
  storeState.isProfileComplete = true;
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

async function montar(props: { ocultarNavegacion?: boolean }): Promise<void> {
  await act(async () => {
    root.render(createElement(StudentShell, props, createElement('div', null, 'contenido')));
  });
  await act(async () => {});
}

function tieneSidebar(): boolean {
  return container.querySelectorAll('aside').length > 0;
}

describe('StudentShell — ocultarNavegacion', () => {
  it('con isProfileComplete=true y SIN ocultarNavegacion, la sidebar se muestra (comportamiento normal)', async () => {
    await montar({});
    expect(tieneSidebar()).toBe(true);
  });

  it('con isProfileComplete=true PERO ocultarNavegacion=true, la sidebar NO se muestra (fix del bug)', async () => {
    await montar({ ocultarNavegacion: true });
    expect(tieneSidebar()).toBe(false);
  });
});
