/**
 * Tests — UsuarioCreate (c-76, tarea 1.5)
 *
 * Cubre:
 *  a) acceso denegado sin capacidad `gestionar_usuarios`
 *  b) modal aparece solo cuando hay `password_generada` en la respuesta
 *  c) sin `password_generada` no hay modal de clave
 *
 * TDD Cycle: RED → GREEN → TRIANGULATE → REFACTOR
 * Framework: vitest + @testing-library/react
 * Regla #4: sin mocks de DB (no aplica aquí — es front puro).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, fireEvent, waitFor } from '@testing-library/react';

// ---------------------------------------------------------------------------
// Mocks de dependencias de contexto
// ---------------------------------------------------------------------------

// StaffShell: passthrough — evita router/auth del chrome
vi.mock('../../ui/shells', () => ({
  StaffShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

// HelpButton: passthrough
vi.mock('../../ui/HelpButton', () => ({
  HelpButton: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

// useNavigate: capturamos las navegaciones
const mockNavigate = vi.fn();
vi.mock('../../lib/router', () => ({
  useNavigate: () => mockNavigate,
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}));

// useToast: capturamos toasts
const mockToast = { success: vi.fn(), error: vi.fn() };
vi.mock('../../ui/toast', () => ({
  useToast: () => mockToast,
}));

// useAuth: por defecto usuario con rol admin_sistema (tiene gestionar_usuarios)
let mockPrincipal: { roles: string[] } | null = { roles: ['admin_sistema'] };
vi.mock('../../lib/authStore', () => ({
  useAuth: (selector: (s: { principal: typeof mockPrincipal }) => unknown) =>
    selector({ principal: mockPrincipal }),
}));

// tieneCapacidad: usamos la implementación real (no mockeamos lógica de dominio)
// El mock de authStore es suficiente para que el componente tome la decisión.

// api: solo crearUsuario nos importa en estos tests
const mockCrearUsuario = vi.fn();
vi.mock('../../lib/api', () => ({
  api: {
    crearUsuario: (...args: unknown[]) => mockCrearUsuario(...args),
  },
}));

// ---------------------------------------------------------------------------
import UsuarioCreate from './UsuarioCreate';

// ---------------------------------------------------------------------------
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  mockPrincipal = { roles: ['admin_sistema'] };
});

// ---------------------------------------------------------------------------
// Helper: rellena el formulario con datos mínimos válidos y lo envía
// ---------------------------------------------------------------------------
async function llenarYEnviar() {
  fireEvent.change(screen.getByLabelText(/email/i), {
    target: { value: 'nuevo@uni.edu.ar' },
  });
  fireEvent.change(screen.getByLabelText(/^usuario$/i), {
    target: { value: 'nuevo.uni' },
  });
  // Seleccionar al menos un rol (el primero disponible)
  const checkboxes = screen.getAllByRole('checkbox');
  if (checkboxes.length > 0) fireEvent.click(checkboxes[0]);

  fireEvent.click(screen.getByRole('button', { name: /crear usuario/i }));
}

// ===========================================================================
describe('UsuarioCreate — acceso sin gestionar_usuarios (tarea 1.5.a)', () => {
  it('muestra mensaje de acceso denegado cuando el usuario no tiene gestionar_usuarios', () => {
    mockPrincipal = { roles: ['estudiante'] };
    render(<UsuarioCreate />);

    // El componente debe renderizar un bloqueo / mensaje de acceso denegado
    // en vez del formulario de alta
    expect(screen.queryByRole('button', { name: /crear usuario/i })).toBeNull();
    // Hay dos nodos con texto de "sin permiso": el título y el cuerpo.
    // Verificamos que al menos uno existe (getAllByText lanza si no hay ninguno).
    expect(screen.getAllByText(/sin permiso|acceso denegado|no tenés permiso/i).length).toBeGreaterThan(0);
  });

  it('el formulario SÍ aparece con rol admin_sistema (tiene gestionar_usuarios)', () => {
    mockPrincipal = { roles: ['admin_sistema'] };
    render(<UsuarioCreate />);

    expect(screen.getByRole('button', { name: /crear usuario/i })).toBeTruthy();
  });
});

// ===========================================================================
describe('UsuarioCreate — modal de clave temporal (tarea 1.5.b y 1.5.c)', () => {
  beforeEach(() => {
    mockPrincipal = { roles: ['admin_sistema'] };
  });

  it('el modal aparece cuando la respuesta incluye password_generada', async () => {
    mockCrearUsuario.mockResolvedValueOnce({
      id: 'u-1',
      username: 'FRM-23-0001',
      email: 'nuevo@uni.edu.ar',
      nombre: null,
      apellido: null,
      roles: ['estudiante'],
      auth_provider: 'local',
      password_generada: 'Temp@1234',
    });

    render(<UsuarioCreate />);
    await llenarYEnviar();

    // Modal debe aparecer con la clave
    await waitFor(() =>
      expect(screen.getByRole('dialog')).toBeTruthy(),
    );
    expect(screen.getByText('Temp@1234')).toBeTruthy();
    expect(screen.getByText(/guardala ahora|no la vas a volver a ver/i)).toBeTruthy();
  });

  it('el modal NO aparece cuando la respuesta NO tiene password_generada', async () => {
    mockCrearUsuario.mockResolvedValueOnce({
      id: 'u-2',
      username: 'FRM-23-0002',
      email: 'otro@uni.edu.ar',
      nombre: null,
      apellido: null,
      roles: ['estudiante'],
      auth_provider: 'local',
      password_generada: null,
    });

    render(<UsuarioCreate />);
    await llenarYEnviar();

    // Sin clave generada, el modal de clave NO debe aparecer
    await waitFor(() =>
      expect(screen.queryByRole('dialog')).toBeNull(),
    );
  });

  it('el botón copiar ejecuta navigator.clipboard.writeText con la clave', async () => {
    mockCrearUsuario.mockResolvedValueOnce({
      id: 'u-3',
      username: 'FRM-23-0003',
      email: 'copiar@uni.edu.ar',
      nombre: null,
      apellido: null,
      roles: ['estudiante'],
      auth_provider: 'local',
      password_generada: 'SecureXYZ99!',
    });

    // Espiamos clipboard
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: writeTextMock },
      writable: true,
    });

    render(<UsuarioCreate />);
    await llenarYEnviar();

    await screen.findByRole('dialog');

    fireEvent.click(screen.getByRole('button', { name: /copiar/i }));

    await waitFor(() =>
      expect(writeTextMock).toHaveBeenCalledWith('SecureXYZ99!'),
    );
  });

  it('el botón "Entendido" navega a /admin/usuarios', async () => {
    mockCrearUsuario.mockResolvedValueOnce({
      id: 'u-4',
      username: 'FRM-23-0004',
      email: 'ent@uni.edu.ar',
      nombre: null,
      apellido: null,
      roles: ['admin_sistema'],
      auth_provider: 'local',
      password_generada: 'Go@Home99',
    });

    render(<UsuarioCreate />);
    await llenarYEnviar();

    await screen.findByRole('dialog');

    fireEvent.click(
      screen.getByRole('button', { name: /entendido|ir a usuarios/i }),
    );

    expect(mockNavigate).toHaveBeenCalledWith('/admin/usuarios');
  });
});
