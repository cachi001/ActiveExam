/**
 * RequireAuth — Guard de ruta por autenticación y rol.
 *
 * - status 'loading'        → loader (provider todavía inicializando)
 * - status 'unauthenticated'→ redirige a /login (la pantalla con el botón de ingreso)
 * - autenticado sin el rol  → pantalla "sin permiso" (403), NUNCA sanciona ni filtra datos
 * - autenticado con rol     → renderiza el contenido protegido
 *
 * Uso: <RequireAuth roles={['admin_sistema']}><AdminDashboard /></RequireAuth>
 * Sin `roles` → solo exige sesión iniciada (cualquier rol).
 */
import { lazy, Suspense, useEffect } from 'react';
import type { ReactNode } from 'react';
import type { Rol } from '../types';
import { useAuth } from '../authStore';
import { useNavigate } from '../router';
import { Icon, Button } from '../../ui/components';

// Pantalla bloqueante de primer login (clave temporal). Lazy para no cargarla
// en el bundle inicial de todas las rutas protegidas.
const CambioClaveObligatorio = lazy(() => import('../../screens/CambioClaveObligatorio'));

export function RequireAuth({ roles, children }: { roles?: Rol[]; children: ReactNode }) {
  const status = useAuth((s) => s.status);
  const principal = useAuth((s) => s.principal);
  const navigate = useNavigate();

  useEffect(() => {
    if (status === 'unauthenticated') navigate('/login');
  }, [status, navigate]);

  if (status === 'loading' || status === 'unauthenticated') {
    return <PantallaCarga />;
  }

  // Primer login con clave temporal: bloquea TODAS las rutas protegidas hasta que
  // el usuario defina su propia contraseña (antes incluso del check de rol).
  if (principal?.debe_cambiar_password) {
    return (
      <Suspense fallback={<PantallaCarga />}>
        <CambioClaveObligatorio />
      </Suspense>
    );
  }

  const tieneRol =
    !roles || roles.length === 0 || (principal != null && roles.some((r) => principal.roles.includes(r)));

  if (!tieneRol) return <SinPermiso />;

  return <>{children}</>;
}

function PantallaCarga() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-md bg-surface text-on-surface-variant">
      <Icon name="progress_activity" className="ae-spin text-[32px] text-primary" />
      <p className="text-label-md">Verificando tu sesión…</p>
    </div>
  );
}

function SinPermiso() {
  const navigate = useNavigate();
  const logout = useAuth((s) => s.logout);
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-md bg-surface px-lg text-center">
      <div className="w-14 h-14 rounded-2xl bg-error-container text-error flex items-center justify-center">
        <Icon name="block" className="text-[28px]" fill />
      </div>
      <div>
        <h1 className="font-headline text-headline-md text-on-surface">Sin permisos</h1>
        <p className="text-body-md text-on-surface-variant mt-base max-w-sm">
          Tu cuenta no tiene el rol necesario para acceder a esta sección.
        </p>
      </div>
      <div className="flex items-center gap-sm">
        <Button variant="outline" icon="arrow_back" onClick={() => navigate('/login')}>
          Volver al inicio
        </Button>
        <Button variant="ghost" icon="logout" onClick={() => logout()}>
          Cerrar sesión
        </Button>
      </div>
    </div>
  );
}

export default RequireAuth;
