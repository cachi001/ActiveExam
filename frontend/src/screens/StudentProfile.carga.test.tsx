/**
 * "Mi perfil" no puede saltar mientras carga (c-78, reporte del dueño).
 *
 * EL SÍNTOMA: al tocar "Mi perfil" en la barra lateral, la barra desaparecía y
 * el "Cargando…" salía centrado en toda la pantalla; un segundo después la barra
 * volvía y el contenido se corría a la derecha. Ninguna otra pantalla del alumno
 * hace eso.
 *
 * LA CAUSA: el estado de carga se renderizaba con `<StudentShell ocultarNavegacion>`
 * mientras que la vista final del perfil usa `<StudentShell>` normal. O sea que la
 * propia pantalla cambiaba de layout entre "cargando" y "listo".
 *
 * `ocultarNavegacion` existe para el flujo de enrollment (consentimiento, foto,
 * biometría, DNI), donde el alumno NO tiene que poder irse a otro lado hasta
 * terminar. Eso sigue igual. Lo que no corresponde es ocultarla mientras se
 * averigua en qué paso está: ahí todavía no se sabe si hay algo que bloquear, y
 * el shell ya bloquea solo cuando el perfil está incompleto
 * (`perfilBloqueado` en StudentShell).
 */
import { describe, expect, it, vi, afterEach, beforeEach } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';

vi.mock('../lib/api', () => ({
  api: {
    obtenerEstadoEnrollment: vi.fn(() => new Promise(() => {})), // nunca resuelve: se queda cargando
    obtenerConfiguracionSistema: vi.fn(() => new Promise(() => {})),
    obtenerFotoPerfil: vi.fn(() => new Promise(() => {})),
  },
  API_BASE: 'http://test',
}));

vi.mock('../lib/router', () => ({
  useNavigate: () => vi.fn(),
  Link: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const shellProps: { ocultarNavegacion?: boolean }[] = [];
vi.mock('../ui/shells', () => ({
  StudentShell: (props: { children: React.ReactNode; ocultarNavegacion?: boolean }) => {
    shellProps.push({ ocultarNavegacion: props.ocultarNavegacion });
    return (
      <div data-testid="shell" data-oculta={String(Boolean(props.ocultarNavegacion))}>
        {props.children}
      </div>
    );
  },
}));

beforeEach(() => {
  shellProps.length = 0;
});

afterEach(() => {
  cleanup();
});

describe('StudentProfile mientras carga', () => {
  it('no oculta la navegación: la barra lateral no puede desaparecer y volver', async () => {
    const { default: StudentProfile } = await import('./StudentProfile');
    render(<StudentProfile />);

    await waitFor(() => expect(screen.getByTestId('shell')).toBeTruthy());

    expect(screen.getByTestId('shell').getAttribute('data-oculta')).toBe('false');
    expect(shellProps.every((p) => !p.ocultarNavegacion)).toBe(true);
  });

  it('muestra el cartel de carga', async () => {
    const { default: StudentProfile } = await import('./StudentProfile');
    render(<StudentProfile />);

    await waitFor(() => expect(screen.getByText(/Cargando perfil/i)).toBeTruthy());
  });
});
